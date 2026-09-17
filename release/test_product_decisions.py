"""Synthetic proposal validation only. Fixture choices are not owner decisions."""

from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from execution.contracts import ExecutionBlocked, ExecutionGrant
from release import product_decisions as decisions


def complete_fixture():
    value = decisions.source_contract()
    fields = value["decisions"]
    fields["free_thinking"] = {"handling": "retain_legacy_only", "route_id": None,
                               "rationale": "Synthetic test proposal, not a decision."}
    for tier, routes in fields["work_tiers"].items():
        for route in routes:
            routes[route] = tier == "pro"
    for route, conditions in fields["completed_answer_targets"].items():
        for condition in conditions:
            conditions[condition] = {"kind": "no_fixed_target", "milliseconds": None,
                "statistic": None, "rationale": "Synthetic review input only."}
    for route in fields["maximum_active_execution"]:
        fields["maximum_active_execution"][route] = {"maximum_ms": 123456,
            "measurement_definition": "Fixture definition only; no clock is implemented here."}
    fields["extra_high_semantics"] = "Synthetic explanation, not an approved policy reconciliation."
    return value


class ProductDecisionsTests(unittest.TestCase):
    def test_actual_source_is_valid_and_does_not_close_any_item(self):
        report = decisions.validate_checked_in()
        self.assertEqual(report["phase_a_total"], 40)
        self.assertEqual(report["routes"], 25)
        self.assertEqual(report["work_combinations"], 18)
        self.assertEqual(report["missing_field_count"], 131)
        self.assertEqual(report["closed_checklist_ids"], [])
        self.assertFalse(report["phase_b_ready"])

    def test_fully_populated_proposal_never_authenticates_an_owner_or_becomes_ready(self):
        report = decisions.validate_proposal(complete_fixture())
        self.assertTrue(report["proposal_fully_populated"])
        for flag in ("owner_approval_verified", "runtime_policy_changed", "phase_b_ready"):
            self.assertIs(report[flag], False)
        self.assertEqual(report["closed_checklist_ids"], [])
        self.assertEqual(len(report["blockers"]), 3)

    def test_missing_routes_tiers_or_fields_are_rejected_not_removed_from_coverage(self):
        for section in ("work_tiers", "completed_answer_targets", "maximum_active_execution"):
            template = decisions.source_contract()
            for key in template["decisions"][section]:
                value = deepcopy(template)
                del value["decisions"][section][key]
                with self.subTest(section=section, key=key), self.assertRaises(decisions.DecisionRejected):
                    decisions.validate_proposal(value)

    def test_all_54_work_cells_distinguish_unknown_from_explicit_denial(self):
        for tier in decisions.TIERS:
            for route in decisions.source_contract()["decisions"]["work_tiers"][tier]:
                value = decisions.source_contract()
                value["decisions"]["work_tiers"][tier][route] = False
                report = decisions.validate_proposal(value)
                self.assertEqual(report["missing_field_count"], 130)
                self.assertFalse(report["owner_approval_verified"])

    def test_bool_lookalikes_cannot_become_work_permissions(self):
        for bad in (0, 1, "true", "false", [], {}, 1.0):
            value = decisions.source_contract()
            value["decisions"]["work_tiers"]["free"]["work:cosmo:light"] = bad
            with self.subTest(bad=bad), self.assertRaises(decisions.DecisionRejected):
                decisions.validate_proposal(value)

    def test_pro_gate_is_necessary_not_automatic_work_entitlement(self):
        for tier in ("free", "plus"):
            for family in ("cosmo", "orion", "nova"):
                value = decisions.source_contract()
                value["decisions"]["work_tiers"][tier][f"work:{family}:ultra"] = True
                with self.assertRaises(decisions.DecisionRejected):
                    decisions.validate_proposal(value)
        template = decisions.source_contract()
        self.assertIsNone(template["decisions"]["work_tiers"]["pro"]["work:cosmo:ultra"])

    def test_custom_thinking_proposal_does_not_modify_current_free_execution_grant(self):
        value = decisions.source_contract()
        value["decisions"]["free_thinking"] = {"handling": "custom_chat_route", "route_id": "high",
                                               "rationale": "Unapproved fixture only."}
        self.assertFalse(decisions.validate_proposal(value)["runtime_policy_changed"])
        grant = ExecutionGrant("fixture-owner", "free", frozenset(("high",)), True)
        with self.assertRaises(ExecutionBlocked):
            grant.authorize("fixture-owner", "high")

    def test_thinking_mapping_cannot_use_unknown_auto_work_or_ultra_route(self):
        for route in ("thinking", "auto", "kova-auto", "work:cosmo:light", "ultra", [], None):
            value = decisions.source_contract()
            value["decisions"]["free_thinking"] = {"handling": "custom_chat_route", "route_id": route,
                                                   "rationale": "Fixture only."}
            with self.subTest(route=route), self.assertRaises(decisions.DecisionRejected):
                decisions.validate_proposal(value)

    def test_retained_legacy_handling_cannot_secretly_select_a_custom_route(self):
        value = complete_fixture()
        value["decisions"]["free_thinking"]["route_id"] = "instant"
        with self.assertRaises(decisions.DecisionRejected):
            decisions.validate_proposal(value)

    def test_no_fixed_average_is_a_valid_unapproved_proposal_not_an_invented_number(self):
        value = complete_fixture()
        result = decisions.validate_proposal(value)
        self.assertTrue(result["proposal_fully_populated"])
        self.assertIsNone(value["decisions"]["completed_answer_targets"]["instant"]["warm"]["milliseconds"])
        self.assertIs(result["owner_approval_verified"], False)

    def test_numeric_target_requires_explicit_statistic_and_positive_integer(self):
        for bad in (None, True, 0, -1, 1.0, "10", 2**53):
            value = complete_fixture()
            value["decisions"]["completed_answer_targets"]["instant"]["cold"] = {
                "kind": "target", "milliseconds": bad, "statistic": "mean", "rationale": "Fixture."}
            with self.subTest(bad=bad), self.assertRaises(decisions.DecisionRejected):
                decisions.validate_proposal(value)
        for statistic in (None, "acknowledgement", "mean-or-p95", [], 1):
            value = complete_fixture()
            value["decisions"]["completed_answer_targets"]["instant"]["cold"] = {
                "kind": "target", "milliseconds": 500, "statistic": statistic, "rationale": "Fixture."}
            with self.assertRaises(decisions.DecisionRejected):
                decisions.validate_proposal(value)

    def test_no_fixed_target_cannot_smuggle_a_number_or_statistic(self):
        for field, new in (("milliseconds", 200), ("statistic", "p95")):
            value = complete_fixture()
            value["decisions"]["completed_answer_targets"]["instant"]["warm"][field] = new
            with self.assertRaises(decisions.DecisionRejected):
                decisions.validate_proposal(value)

    def test_cold_warm_and_clocks_are_not_interchangeable_or_artificial_minimums(self):
        value = decisions.source_contract()
        value["decisions"]["completed_answer_targets"]["instant"]["warm"] = {
            "kind": "target", "milliseconds": 500, "statistic": "mean", "rationale": "Fixture faster than reference."}
        report = decisions.validate_proposal(value)
        self.assertIn("decisions.completed_answer_targets.instant.cold", report["missing_fields"])
        self.assertIn("decisions.maximum_active_execution.instant", report["missing_fields"])
        self.assertTrue(value["preserved"]["cosmo_goal"]["faster_allowed"])
        self.assertEqual(value["preserved"]["cosmo_goal"]["ideal_reference_ms"], [1000, 3000])

    def test_every_active_limit_requires_finite_positive_milliseconds_and_definition(self):
        for bad in (None, True, 0, -1, "unlimited", 1.0, 2**53):
            value = complete_fixture()
            value["decisions"]["maximum_active_execution"]["instant"]["maximum_ms"] = bad
            with self.assertRaises(decisions.DecisionRejected):
                decisions.validate_proposal(value)
        value = complete_fixture()
        value["decisions"]["maximum_active_execution"]["instant"]["measurement_definition"] = " "
        with self.assertRaises(decisions.DecisionRejected):
            decisions.validate_proposal(value)

    def test_source_identity_original_rubric_and_known_facts_cannot_be_edited_in_a_proposal(self):
        mutations = (
            lambda v: v.update(schema_version=True),
            lambda v: v["source"].update(commit="a" * 40),
            lambda v: v["phase_a"].update(total=41),
            lambda v: v["phase_a"].update(items=["A36"]),
            lambda v: v["preserved"].update(ultra_requires_pro=1),
            lambda v: v["preserved"]["application_chat_modes"].update(free=["instant", "high"]),
            lambda v: v["preserved"]["cosmo_goal"].update(measured_on_azure=True),
            lambda v: v["preserved"]["cosmo_goal"].update(hard_limit=True),
            lambda v: v["preserved"]["extra_high"].update(current_chat_passes=[2, 4, 2, 2]),
        )
        for mutate in mutations:
            value = complete_fixture()
            mutate(value)
            with self.assertRaises(decisions.DecisionRejected):
                decisions.validate_proposal(value)

    def test_caller_approval_execution_and_completion_flags_are_rejected(self):
        for flag in ("approved", "approved_by", "execution_authorized", "phase_b_ready", "completed_ids"):
            for parent in (None, "decisions"):
                value = complete_fixture()
                target = value if parent is None else value[parent]
                target[flag] = True
                with self.assertRaises(decisions.DecisionRejected):
                    decisions.validate_proposal(value)

    def test_source_templates_and_validation_do_not_mutate_caller_data(self):
        first = decisions.source_contract()
        original = deepcopy(first)
        decisions.validate_proposal(first)
        self.assertEqual(first, original)
        first["preserved"]["application_chat_modes"]["free"].append("high")
        self.assertEqual(decisions.source_contract(), original)

    def test_check_in_cannot_promote_even_a_fully_populated_unapproved_proposal(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            for path in decisions.PROTECTED_PATHS:
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((decisions.ROOT / path).read_bytes())
            (root / "config/product-decisions.v1.json").write_text(json.dumps(complete_fixture()))
            with patch.object(decisions, "ROOT", root), self.assertRaises(decisions.DecisionRejected):
                decisions.validate_checked_in()

    def test_protected_source_drift_is_detected_before_proposal_validation(self):
        with patch.object(decisions, "SOURCE_HASHES", {**decisions.SOURCE_HASHES,
                  "config/identity.v1.json": "a" * 64}), self.assertRaises(decisions.DecisionRejected):
            decisions.validate_checked_in()

    def test_reports_omit_proposed_rationale_and_arbitrary_text(self):
        value = complete_fixture()
        marker = "PRIVATE-FIXTURE-NOT-A-SECRET"
        value["decisions"]["extra_high_semantics"] = marker
        value["decisions"]["free_thinking"]["rationale"] = marker
        self.assertNotIn(marker, json.dumps(decisions.validate_proposal(value)))

    def test_duplicate_keys_nonfinite_and_float_json_are_rejected(self):
        for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}', b'{"x":1e999}', b'{"x":1.0}'):
            with self.assertRaises(decisions.DecisionRejected):
                decisions.parse_document(raw)

    def test_invalid_unicode_overlimit_depth_nodes_and_cycles_are_rejected(self):
        for raw in (b'"\xff"', b'"\\ud800"', b'[' * 1100, b' ' * (decisions.MAX_BYTES + 1)):
            with self.assertRaises(decisions.DecisionRejected):
                decisions.parse_document(raw)
        cyclic = []
        cyclic.append(cyclic)
        for value in (cyclic, [None] * (decisions.MAX_NODES + 1)):
            with self.assertRaises(decisions.DecisionRejected):
                decisions.finite_document(value)

    def test_validation_does_not_invoke_network_or_model_or_cloud_tools(self):
        with patch("socket.socket", side_effect=AssertionError("network")), \
             patch("subprocess.Popen", side_effect=AssertionError("execution")):
            self.assertFalse(decisions.validate_checked_in()["runtime_policy_changed"])
            self.assertFalse(decisions.validate_proposal(complete_fixture())["phase_b_ready"])

    def test_cli_source_success_is_distinct_from_explicit_readiness_block(self):
        for args, expected in (([], 0), (["--require-ready"], 78)):
            result = subprocess.run([sys.executable, "-m", "release.product_decisions", *args],
                cwd=decisions.ROOT, capture_output=True, timeout=10)
            self.assertEqual(result.returncode, expected, result.stderr.decode())
            self.assertFalse(json.loads(result.stdout)["phase_b_ready"])
            self.assertEqual(result.stderr, b"")

    def test_cli_proposals_are_read_only_and_execution_approval_flags_do_not_exist(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "proposal.json"
            path.write_text(json.dumps(complete_fixture()))
            before = path.read_bytes()
            result = subprocess.run([sys.executable, "-m", "release.product_decisions", "--proposal", str(path)],
                cwd=decisions.ROOT, capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            self.assertFalse(json.loads(result.stdout)["owner_approval_verified"])
            self.assertEqual(path.read_bytes(), before)
        for args in (["--execute"], ["--approve"], ["--apply"], ["--proposal"], ["--require-ready", "--approve"]):
            out, err = io.StringIO(), io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                self.assertEqual(decisions.main(args), 1)
            self.assertEqual(out.getvalue(), "")
            self.assertEqual(err.getvalue(), "product decision document rejected\n")

    def test_cli_read_errors_do_not_echo_input_paths_or_payloads(self):
        with TemporaryDirectory() as directory:
            for raw in (b'"\xffPRIVATE"', b'"\\ud800"', b'{"approved":true}'):
                path = Path(directory) / "PRIVATE-NAME.json"
                path.write_bytes(raw)
                out, err = io.StringIO(), io.StringIO()
                with redirect_stdout(out), redirect_stderr(err):
                    self.assertEqual(decisions.main(["--proposal", str(path)]), 1)
                self.assertEqual(out.getvalue(), "")
                self.assertEqual(err.getvalue(), "product decision document rejected\n")


if __name__ == "__main__":
    unittest.main()
