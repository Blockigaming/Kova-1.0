import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from execution.contracts import ExecutionBlocked, ExecutionGrant, ExecutionLimits
from release import product_policy
from router.application import SELECTION_SCHEMA, resolve_application_selection
from router.entitlements import ALL_WORK_ROUTES, PLUS_WORK_ROUTES, WORK_ALLOWED_BY_TIER


class ProductPolicyTests(unittest.TestCase):
    def test_checked_in_policy_closes_only_a36_a37_and_not_phase_b(self):
        report = product_policy.validate_checked_in()
        self.assertEqual(report["closed_checklist_ids"], ["A36", "A37"])
        self.assertEqual(report["phase_a_total"], 40)
        self.assertEqual(report["work_routes_by_tier"], {"free": 0, "plus": 9, "pro": 18})
        self.assertTrue(report["product_policy_ready"])
        self.assertFalse(report["phase_b_ready"])

    def test_work_matrix_is_exact_0_9_18(self):
        self.assertEqual(WORK_ALLOWED_BY_TIER["free"], frozenset())
        self.assertEqual(WORK_ALLOWED_BY_TIER["plus"], PLUS_WORK_ROUTES)
        self.assertEqual(WORK_ALLOWED_BY_TIER["pro"], ALL_WORK_ROUTES)
        self.assertEqual((len(WORK_ALLOWED_BY_TIER["free"]), len(WORK_ALLOWED_BY_TIER["plus"]),
                          len(WORK_ALLOWED_BY_TIER["pro"])), (0, 9, 18))

    def test_free_thinking_resolves_to_orion_without_unlocking_direct_medium(self):
        grant = ExecutionGrant("owner", "free", frozenset(("instant", "medium")), True)
        thinking = {"schema_version": SELECTION_SCHEMA, "surface": "chat", "mode_id": "thinking"}
        resolved = resolve_application_selection(thinking, grant=grant)
        self.assertEqual((resolved.route_id, resolved.application_mode_id), ("medium", "thinking"))
        with self.assertRaises(ExecutionBlocked):
            resolve_application_selection({**thinking, "mode_id": "medium"}, grant=grant)

    def test_policy_does_not_create_global_timing_or_dollar_promises(self):
        policy = product_policy.PRODUCT_POLICY
        self.assertEqual(policy["timing"]["completed_answer"]["policy"], "no_fixed_product_target")
        self.assertIsNone(policy["timing"]["maximum_active_execution"]["fixed_product_maximum_ms"])
        self.assertFalse(policy["budget_policy"]["fixed_dollar_promise_created"])
        self.assertFalse(policy["timing"]["cosmo_warm_first_visible_answer_token"]["hard_limit"])

    def test_execution_still_requires_finite_server_bounds(self):
        baseline = ExecutionLimits(1, 1, 1, 1, 1)
        self.assertEqual(baseline.as_dict()["deadline_unix_ms"], 1)
        for changes in (
            {"deadline_unix_ms": 0}, {"token_limit": 0}, {"cost_limit_microusd": 0},
            {"max_parallel": 0}, {"stage_timeout_seconds": 240},
        ):
            values = baseline.as_dict() | changes
            with self.assertRaises(ValueError):
                ExecutionLimits(**values)

    def test_extra_high_current_passes_are_authoritative(self):
        semantics = product_policy.PRODUCT_POLICY["extra_high_semantics"]
        self.assertEqual(semantics["chat_passes"], [2, 2, 2, 2])
        self.assertEqual(semantics["work_passes"], [2, 3, 2, 2])
        self.assertEqual(semantics["historical_reasoning_range"], [4, 6])
        self.assertFalse(semantics["historical_reasoning_range_is_execution_pass_count"])

    def test_validator_fails_closed_on_policy_drift(self):
        mutated = json.loads(json.dumps(product_policy.PRODUCT_POLICY))
        mutated["work_entitlements"]["free"] = ["work:cosmo:light"]
        with patch.object(product_policy, "PRODUCT_POLICY", mutated), self.assertRaises(product_policy.ProductPolicyError):
            product_policy.validate_checked_in()

    def test_cli_ready_means_a36_a37_only_and_never_phase_b(self):
        root = Path(__file__).resolve().parents[1]
        for args in ([], ["--require-ready"]):
            result = subprocess.run([sys.executable, "-m", "release.product_policy", *args],
                                    cwd=root, capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            report = json.loads(result.stdout)
            self.assertTrue(report["product_policy_ready"])
            self.assertFalse(report["phase_b_ready"])


if __name__ == "__main__":
    unittest.main()
