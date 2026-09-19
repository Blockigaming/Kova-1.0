"""Offline regression checks for the bounded Cosmo pilot runtime guard."""
from copy import deepcopy
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import hashlib
import json
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from training import cosmo_runtime_guard as guard
from training import kova_cosmo_sft as recipe


NOW = datetime(2026, 9, 19, 12, 0, 0, tzinfo=timezone.utc)


class CosmoRuntimeGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "repo"
        (self.root / "config").mkdir(parents=True)
        self.policy = deepcopy(guard.load_policy())
        self.write_policy()

    def write_policy(self):
        (self.root / "config/kova-cosmo-runtime-guard.v1.json").write_text(
            json.dumps(self.policy), encoding="utf-8"
        )

    def release(self):
        self.policy["status"] = "operator_preflight_required"
        self.policy["owner_approvals"]["resource_creation_release"] = True
        self.policy["owner_approvals"]["spending_release"] = True
        self.write_policy()

    def evidence(self, **changes):
        value = {
            "schema_version": 1,
            "captured_at_utc": "2026-09-19T11:55:00Z",
            "subscription_id": "00000000-0000-0000-0000-000000000000",
            "resource_group": "kova-cosmo-pilot",
            "vm_name": "kova-cosmo-pilot-1",
            "region": "eastus",
            "vm_size": "Standard_NC4as_T4_v3",
            "family_quota_limit_vcpus": 4,
            "capacity_confirmed": True,
            "compute_usd_per_hour": "0.5260",
            "ancillary_cost_bound_usd": "1.4740",
            "preflight_power_state": "deallocated",
            "public_ip_attached": False,
            "control_plane_deallocation_deadline_utc":
                "2026-09-19T13:00:00Z",
            "control_plane_deallocation_rule_id": "rule-1",
            "watchdog_principal": "watchdog-1",
            "watchdog_permission_tested_at_utc": "2026-09-19T11:50:00Z",
            "watchdog_test_result": "passed",
        }
        value.update(changes)
        path = self.base / "runtime-evidence.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        return path, value

    def test_checked_in_policy_records_budget_but_withholds_spending(self):
        report = guard.dry_run()
        self.assertEqual(report["approved_all_in_budget_usd"], "2.0000")
        self.assertEqual(report["maximum_allocated_minutes"], 60)
        self.assertEqual(report["blockers"], [
            "resource_creation_release_withheld",
            "spending_release_withheld",
            "runtime_evidence_missing",
        ])
        self.assertFalse(report["resource_created"])
        self.assertFalse(report["spending_started"])

    def test_budget_math_and_rate_are_exact(self):
        policy = guard.load_policy()
        self.assertEqual(policy["pricing"]["maximum_compute_cost_usd"],
                         "0.5260")
        self.assertEqual(policy["pricing"]["minimum_ancillary_reserve_usd"],
                         "1.4740")
        self.policy["pricing"]["minimum_ancillary_reserve_usd"] = "1.4739"
        self.write_policy()
        with self.assertRaises(guard.RuntimeGuardError):
            guard.load_policy(self.root)

    def test_runtime_policy_and_sft_approvals_cannot_silently_diverge(self):
        policy = guard.load_policy()
        configured = recipe.load_recipe()
        approvals = policy["owner_approvals"]
        self.assertEqual(
            f'{configured["account_gates"]["approved_budget_usd"]:.4f}',
            policy["pricing"]["approved_all_in_budget_usd"],
        )
        self.assertIs(
            configured["execution"]["model_download_authorized"],
            approvals["model_download_approved"],
        )
        self.assertIs(
            configured["execution"]["training_authorized"],
            approvals["bounded_training_pilot_approved"],
        )
        self.assertIs(
            configured["execution"]["deployment_authorized"],
            approvals["deployment_authorized"],
        )

    def test_release_still_requires_fresh_external_evidence(self):
        self.release()
        with self.assertRaises(guard.RuntimeGuardError):
            guard.require_ready(root=self.root, now=NOW)

    def test_fresh_evidence_allows_only_one_bounded_preflight(self):
        self.release()
        path, _ = self.evidence()
        report = guard.require_ready(root=self.root, evidence_path=path, now=NOW)
        self.assertEqual(report["status"], "ready_for_single_bounded_pilot")
        self.assertEqual(report["deadline_utc"], "2026-09-19T13:00:00Z")
        self.assertFalse(report["deployment_authorized"])
        self.assertFalse(report["phase_b_ready"])
        self.assertEqual(report["runtime_evidence_sha256"],
                         hashlib.sha256(path.read_bytes()).hexdigest())

    def test_deadline_cannot_exceed_sixty_minutes(self):
        self.release()
        path, _ = self.evidence(
            control_plane_deallocation_deadline_utc="2026-09-19T13:00:01Z"
        )
        with self.assertRaises(guard.RuntimeGuardError):
            guard.require_ready(root=self.root, evidence_path=path, now=NOW)

    def test_stale_quota_capacity_snapshot_is_rejected(self):
        self.release()
        path, _ = self.evidence(captured_at_utc="2026-09-19T11:44:59Z")
        with self.assertRaises(guard.RuntimeGuardError):
            guard.require_ready(root=self.root, evidence_path=path, now=NOW)

    def test_rate_drift_and_oversized_ancillary_bound_are_rejected(self):
        self.release()
        for changes in (
            {"compute_usd_per_hour": "0.5261"},
            {"ancillary_cost_bound_usd": "1.4741"},
        ):
            with self.subTest(changes=changes):
                path, _ = self.evidence(**changes)
                with self.assertRaises(guard.RuntimeGuardError):
                    guard.require_ready(root=self.root, evidence_path=path,
                                        now=NOW)

    def test_public_ip_or_unverified_watchdog_is_rejected(self):
        self.release()
        for changes in (
            {"public_ip_attached": True},
            {"watchdog_test_result": "not-tested"},
            {"preflight_power_state": "running"},
        ):
            with self.subTest(changes=changes):
                path, _ = self.evidence(**changes)
                with self.assertRaises(guard.RuntimeGuardError):
                    guard.require_ready(root=self.root, evidence_path=path,
                                        now=NOW)

    def test_runtime_evidence_must_not_be_checked_into_repository(self):
        self.release()
        path, value = self.evidence()
        checked_in = self.root / "runtime-evidence.json"
        checked_in.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaises(guard.RuntimeGuardError):
            guard.require_ready(root=self.root, evidence_path=checked_in,
                                now=NOW)

    def test_runtime_evidence_rejects_duplicate_json_keys(self):
        self.release()
        path, value = self.evidence()
        raw = json.dumps(value).replace(
            '"region": "eastus"',
            '"region": "westus", "region": "eastus"',
        )
        path.write_text(raw, encoding="utf-8")
        with self.assertRaises(guard.RuntimeGuardError):
            guard.require_ready(root=self.root, evidence_path=path, now=NOW)

    def test_post_run_requires_deallocated_state_and_inventory(self):
        _, preflight = self.evidence()
        post = {
            "schema_version": 1,
            "observed_at_utc": "2026-09-19T12:40:00Z",
            "allocation_started_at_utc": "2026-09-19T12:00:00Z",
            "deallocated_at_utc": "2026-09-19T12:40:00Z",
            "subscription_id": preflight["subscription_id"],
            "resource_group": preflight["resource_group"],
            "vm_name": preflight["vm_name"],
            "deallocation_deadline_utc":
                preflight["control_plane_deallocation_deadline_utc"],
            "power_state": "deallocated",
            "public_ip_attached": False,
            "allocated_seconds": 2400,
            "compute_cost_upper_bound_usd": "0.3507",
            "ancillary_cost_observed_or_bound_usd": "0.1000",
            "all_in_cost_upper_bound_usd": "0.4507",
            "residual_resources": [{
                "resource_id": "disk-1",
                "resource_type": "managed_disk",
                "billable": True,
                "disposition": "retained_within_approved_budget",
                "evidence": "cost bound checked",
            }],
        }
        path = self.base / "post-run.json"
        path.write_text(json.dumps(post), encoding="utf-8")
        report = guard.verify_post_run(preflight, path)
        self.assertEqual(report["status"], "deallocation_verified")
        self.assertEqual(report["billable_residual_resource_count"], 1)
        self.assertEqual(report["allocated_seconds"], 2400)
        self.assertEqual(report["all_in_cost_upper_bound_usd"], "0.4507")
        self.assertTrue(report["within_approved_budget"])
        self.assertEqual(report["post_run_evidence_sha256"],
                         hashlib.sha256(path.read_bytes()).hexdigest())
        post["power_state"] = "stopped"
        path.write_text(json.dumps(post), encoding="utf-8")
        with self.assertRaises(guard.RuntimeGuardError):
            guard.verify_post_run(preflight, path)

    def test_post_run_duration_and_cost_reconciliation_fail_closed(self):
        _, preflight = self.evidence()
        base = {
            "schema_version": 1,
            "observed_at_utc": "2026-09-19T12:40:00Z",
            "allocation_started_at_utc": "2026-09-19T12:00:00Z",
            "deallocated_at_utc": "2026-09-19T12:40:00Z",
            "subscription_id": preflight["subscription_id"],
            "resource_group": preflight["resource_group"],
            "vm_name": preflight["vm_name"],
            "deallocation_deadline_utc":
                preflight["control_plane_deallocation_deadline_utc"],
            "power_state": "deallocated",
            "public_ip_attached": False,
            "allocated_seconds": 2400,
            "compute_cost_upper_bound_usd": "0.3507",
            "ancillary_cost_observed_or_bound_usd": "0.1000",
            "all_in_cost_upper_bound_usd": "0.4507",
            "residual_resources": [],
        }
        mutations = [
            {"allocated_seconds": 2399},
            {"compute_cost_upper_bound_usd": "0.3506"},
            {"ancillary_cost_observed_or_bound_usd": "1.4741",
             "all_in_cost_upper_bound_usd": "1.8248"},
            {"all_in_cost_upper_bound_usd": "0.4508"},
            {"allocation_started_at_utc": "2026-09-19T12:10:00Z",
             "deallocated_at_utc": "2026-09-19T13:01:00Z",
             "observed_at_utc": "2026-09-19T13:01:00Z",
             "allocated_seconds": 3060,
             "compute_cost_upper_bound_usd": "0.4471",
             "all_in_cost_upper_bound_usd": "0.5471"},
            {"deallocated_at_utc": "2026-09-19T13:01:00Z",
             "observed_at_utc": "2026-09-19T13:01:00Z",
             "allocated_seconds": 3660,
             "compute_cost_upper_bound_usd": "0.5350",
             "all_in_cost_upper_bound_usd": "0.6350"},
        ]
        path = self.base / "post-cost.json"
        for changes in mutations:
            value = dict(base)
            value.update(changes)
            path.write_text(json.dumps(value), encoding="utf-8")
            with self.subTest(changes=changes), self.assertRaises(
                guard.RuntimeGuardError
            ):
                guard.verify_post_run(preflight, path)

    def test_post_run_cli_binds_both_external_evidence_files(self):
        preflight_path, preflight = self.evidence()
        post = {
            "schema_version": 1,
            "observed_at_utc": "2026-09-19T12:40:00Z",
            "allocation_started_at_utc": "2026-09-19T12:00:00Z",
            "deallocated_at_utc": "2026-09-19T12:40:00Z",
            "subscription_id": preflight["subscription_id"],
            "resource_group": preflight["resource_group"],
            "vm_name": preflight["vm_name"],
            "deallocation_deadline_utc":
                preflight["control_plane_deallocation_deadline_utc"],
            "power_state": "deallocated",
            "public_ip_attached": False,
            "allocated_seconds": 2400,
            "compute_cost_upper_bound_usd": "0.3507",
            "ancillary_cost_observed_or_bound_usd": "0.1000",
            "all_in_cost_upper_bound_usd": "0.4507",
            "residual_resources": [],
        }
        post_path = self.base / "post-cli.json"
        post_path.write_text(json.dumps(post), encoding="utf-8")
        output = io.StringIO()
        with redirect_stdout(output):
            code = guard.main([
                "--verify-post-run", str(post_path),
                "--preflight-evidence", str(preflight_path),
            ])
        self.assertEqual(code, 0)
        report = json.loads(output.getvalue())
        self.assertEqual(report["status"], "deallocation_verified")
        self.assertEqual(
            report["preflight_evidence_sha256"],
            hashlib.sha256(preflight_path.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            report["post_run_evidence_sha256"],
            hashlib.sha256(post_path.read_bytes()).hexdigest(),
        )

        error = io.StringIO()
        with redirect_stderr(error):
            self.assertEqual(guard.main(["--verify-post-run", str(post_path)]), 1)
        self.assertEqual(error.getvalue(),
                         "kova cosmo runtime guard rejected\n")

    def test_training_entrypoint_calls_runtime_guard_before_dependencies(self):
        value = deepcopy(recipe.load_recipe())
        value["account_gates"] = {
            "microsoft_quota_provider_registration_authorized": True,
            "eastus_ncast4_quota_verified": True,
            "runtime_compatibility_verified": True,
            "approved_budget_usd": 2,
        }
        value["execution"] = {
            "model_download_authorized": True,
            "training_authorized": True,
            "deployment_authorized": False,
        }
        with patch.object(recipe, "load_recipe", return_value=value), \
             patch.dict("os.environ", {"KOVA_CONFIRM_PAID_TRAINING": "YES"}), \
             patch.object(recipe, "require_runtime_ready",
                          side_effect=guard.RuntimeGuardError("guard called")):
            with self.assertRaisesRegex(guard.RuntimeGuardError, "guard called"):
                recipe.execute()

    def test_training_rehashes_external_snapshot_before_heavy_imports(self):
        value = deepcopy(recipe.load_recipe())
        value["account_gates"] = {
            "microsoft_quota_provider_registration_authorized": True,
            "eastus_ncast4_quota_verified": True,
            "runtime_compatibility_verified": True,
            "approved_budget_usd": 2,
        }
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(recipe, "load_recipe", return_value=value), \
             patch.object(recipe, "require_runtime_ready", return_value={}), \
             patch.object(recipe, "verify_installed_software"), \
             patch.object(recipe, "verify_snapshot",
                          side_effect=recipe.ArtifactError("changed snapshot")), \
             patch.dict("os.environ", {
                 "KOVA_CONFIRM_PAID_TRAINING": "YES",
                 "KOVA_COSMO_VERIFIED_SNAPSHOT": directory,
             }), \
             patch.dict("sys.modules", {
                 "torch": None, "datasets": None, "peft": None, "trl": None,
             }):
            with self.assertRaises(recipe.RecipeError):
                recipe.execute()


if __name__ == "__main__":
    unittest.main()
