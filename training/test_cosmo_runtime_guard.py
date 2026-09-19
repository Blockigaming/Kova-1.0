"""Offline regression checks for the bounded Cosmo pilot runtime guard."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
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
            "cleanup_scope_resource_group_id": (
                "/subscriptions/00000000-0000-0000-0000-000000000000/"
                "resourceGroups/kova-cosmo-pilot"
            ),
            "resource_group_exclusive_to_pilot": True,
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
            "control_plane_cleanup_rule_id": "cleanup-rule-1",
            "watchdog_principal": "watchdog-1",
            "watchdog_permission_tested_at_utc": "2026-09-19T11:50:00Z",
            "watchdog_test_result": "passed",
            "cleanup_permission_tested_at_utc": "2026-09-19T11:50:00Z",
            "cleanup_test_result": "passed",
        }
        value.update(changes)
        path = self.base / "runtime-evidence.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        return path, value

    def post_run(self, preflight, **changes):
        value = {
            "schema_version": 1,
            "observed_at_utc": "2026-09-19T12:45:00Z",
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
            "automatic_deallocation_execution": {
                "mechanism": "azure_control_plane",
                "rule_id": preflight["control_plane_deallocation_rule_id"],
                "execution_id": "deallocation-execution-1",
                "principal": preflight["watchdog_principal"],
                "trigger": "deadline_rule",
                "status": "succeeded",
                "completed_at_utc": "2026-09-19T12:40:00Z",
                "evidence": "immutable control-plane execution record",
            },
            "automatic_cleanup_execution": {
                "mechanism": "azure_control_plane",
                "rule_id": preflight["control_plane_cleanup_rule_id"],
                "execution_id": "cleanup-execution-1",
                "principal": preflight["watchdog_principal"],
                "trigger": "post_run_automatic_cleanup",
                "status": "succeeded",
                "scope_resource_group_id":
                    preflight["cleanup_scope_resource_group_id"],
                "completed_at_utc": "2026-09-19T12:42:00Z",
                "evidence": "immutable control-plane cleanup execution record",
            },
            "scoped_inventory": {
                "scope_resource_group_id":
                    preflight["cleanup_scope_resource_group_id"],
                "query_id": "resource-graph-query-1",
                "query_succeeded": True,
                "queried_at_utc": "2026-09-19T12:44:00Z",
                "resource_group_state": "deleted",
                "remaining_resource_ids": [],
                "evidence": "scoped control-plane query returned group absent",
            },
        }
        value.update(changes)
        return value

    def training_authorization(self):
        state = self.base / "training-authorization-state"
        state.mkdir(mode=0o700)
        output = self.base / "single-training-output"
        value = {
            "schema_version": 1,
            "kind": "kova_cosmo_single_training_authorization",
            "pilot_id": guard.PILOT_ID,
            "output_directory": str(output),
            "state_directory": str(state),
            "maximum_training_runs": 1,
            "issued_at_utc": "2026-09-19T11:55:00Z",
            "expires_at_utc": "2026-09-20T11:55:00Z",
        }
        path = state / guard.TRAINING_AUTHORIZATION_NAME
        path.write_text(json.dumps(value), encoding="utf-8")
        path.chmod(0o600)
        self.policy["pilot"]["training_run_authorization"] = {
            "status": "single_manifest_pinned",
            "manifest_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "environment_variable": guard.TRAINING_AUTHORIZATION_ENV,
        }
        self.write_policy()
        return path, output

    def test_checked_in_policy_records_budget_but_withholds_spending(self):
        report = guard.dry_run()
        self.assertEqual(report["approved_all_in_budget_usd"], "2.0000")
        self.assertEqual(report["maximum_allocated_minutes"], 60)
        self.assertEqual(report["maximum_training_runs"], 1)
        self.assertTrue(report["automatic_deallocation_required"])
        self.assertTrue(report["automatic_cleanup_required"])
        self.assertFalse(report["deployment_authorized"])
        self.assertFalse(report["production_integration_authorized"])
        self.assertEqual(report["blockers"], [
            "resource_creation_release_withheld",
            "spending_release_withheld",
            "single_training_run_authorization_unpinned",
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

    def test_single_training_authorization_is_consumed_atomically_once(self):
        authorization, output = self.training_authorization()

        def consume():
            return guard.consume_training_authorization(
                source_commit="a" * 40,
                output_directory=output,
                runtime_evidence_sha256="e" * 64,
                runtime_deadline_utc="2026-09-19T13:00:00Z",
                root=self.root,
                authorization_path=authorization,
                now=NOW,
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(consume) for _ in range(2)]
        successes = []
        failures = []
        for future in futures:
            try:
                successes.append(future.result())
            except guard.RuntimeGuardError as error:
                failures.append(error)
        self.assertEqual((len(successes), len(failures)), (1, 1))
        self.assertEqual(
            successes[0]["status"],
            "single_training_run_authorization_consumed",
        )
        marker = authorization.parent / guard.TRAINING_CONSUMPTION_NAME
        self.assertTrue(marker.is_file())
        self.assertEqual(marker.stat().st_mode & 0o077, 0)
        consumed = json.loads(marker.read_text())
        self.assertEqual(consumed["source_commit"], "a" * 40)
        self.assertEqual(consumed["runtime_evidence_sha256"], "e" * 64)
        self.assertEqual(
            successes[0]["training_run_consumption_sha256"],
            hashlib.sha256(marker.read_bytes()).hexdigest(),
        )

    def test_training_authorization_rejects_copy_and_binding_drift(self):
        authorization, output = self.training_authorization()
        copied_state = self.base / "copied-authorization-state"
        copied_state.mkdir(mode=0o700)
        copied = copied_state / guard.TRAINING_AUTHORIZATION_NAME
        copied.write_bytes(authorization.read_bytes())
        copied.chmod(0o600)
        cases = (
            {"authorization_path": copied},
            {"source_commit": "B" * 40},
            {"runtime_evidence_sha256": "F" * 64},
            {"output_directory": self.base / "different-output"},
        )
        for changes in cases:
            arguments = {
                "source_commit": "a" * 40,
                "output_directory": output,
                "runtime_evidence_sha256": "e" * 64,
                "runtime_deadline_utc": "2026-09-19T13:00:00Z",
                "root": self.root,
                "authorization_path": authorization,
                "now": NOW,
            }
            arguments.update(changes)
            with self.subTest(changes=changes), self.assertRaises(
                guard.RuntimeGuardError
            ):
                guard.consume_training_authorization(**arguments)

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
        post = self.post_run(preflight)
        path = self.base / "post-run.json"
        path.write_text(json.dumps(post), encoding="utf-8")
        report = guard.verify_post_run(preflight, path)
        self.assertEqual(report["status"], "lifecycle_cleanup_verified")
        self.assertEqual(report["billable_residual_resource_count"], 0)
        self.assertTrue(report["automatic_deallocation_verified"])
        self.assertTrue(report["automatic_cleanup_verified"])
        self.assertTrue(report["resource_group_deleted"])
        self.assertEqual(report["allocated_seconds"], 2400)
        self.assertEqual(report["all_in_cost_upper_bound_usd"], "0.4507")
        self.assertTrue(report["within_approved_budget"])
        self.assertEqual(report["post_run_evidence_sha256"],
                         hashlib.sha256(path.read_bytes()).hexdigest())
        post["power_state"] = "stopped"
        path.write_text(json.dumps(post), encoding="utf-8")
        with self.assertRaises(guard.RuntimeGuardError):
            guard.verify_post_run(preflight, path)

        post["power_state"] = "deallocated"
        post["scoped_inventory"]["resource_group_state"] = "present"
        path.write_text(json.dumps(post), encoding="utf-8")
        with self.assertRaises(guard.RuntimeGuardError):
            guard.verify_post_run(preflight, path)

    def test_post_run_rejects_fake_or_incomplete_cleanup_provenance(self):
        _, preflight = self.evidence()
        path = self.base / "post-cleanup.json"
        mutations = (
            lambda value: value.pop("automatic_cleanup_execution"),
            lambda value: value["automatic_cleanup_execution"].update(
                trigger="manual_cleanup"
            ),
            lambda value: value["automatic_cleanup_execution"].update(
                rule_id="different-rule"
            ),
            lambda value: value["scoped_inventory"].update(
                scope_resource_group_id="/subscriptions/fake/resourceGroups/fake"
            ),
            lambda value: value["scoped_inventory"].update(
                query_succeeded=False
            ),
            lambda value: value["scoped_inventory"].update(
                remaining_resource_ids=["surviving-disk"]
            ),
        )
        for mutate in mutations:
            value = self.post_run(preflight)
            mutate(value)
            path.write_text(json.dumps(value), encoding="utf-8")
            with self.subTest(mutate=mutate), self.assertRaises(
                guard.RuntimeGuardError
            ):
                guard.verify_post_run(preflight, path)

    def test_post_run_duration_and_cost_reconciliation_fail_closed(self):
        _, preflight = self.evidence()
        base = self.post_run(preflight)
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
        post = self.post_run(preflight)
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
        self.assertEqual(report["status"], "lifecycle_cleanup_verified")
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

    def test_training_consumes_single_run_claim_before_heavy_imports(self):
        value = deepcopy(recipe.load_recipe())
        value["account_gates"].update({
            "eastus_ncast4_quota_verified": True,
            "runtime_compatibility_verified": True,
        })
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = root / "snapshot"
            snapshot.mkdir()
            output = root / "output"
            environment = {
                "KOVA_CONFIRM_PAID_TRAINING": "YES",
                "KOVA_COSMO_VERIFIED_SNAPSHOT": str(snapshot),
                "KOVA_COSMO_OUTPUT_DIR": str(output),
                "KOVA_SOURCE_COMMIT": "a" * 40,
            }
            with patch.object(recipe, "load_recipe", return_value=value), \
                 patch.object(recipe, "require_runtime_ready", return_value={
                     "runtime_evidence_sha256": "e" * 64,
                     "deadline_utc": "2026-09-19T13:00:00Z",
                 }), \
                 patch.object(recipe, "verify_installed_software"), \
                 patch.object(recipe, "verify_snapshot"), \
                 patch.object(recipe, "verify_source_checkout"), \
                 patch.object(
                     recipe, "consume_training_authorization",
                     side_effect=guard.RuntimeGuardError("claim called"),
                 ) as consume, \
                 patch.dict("os.environ", environment, clear=True), \
                 patch.dict("sys.modules", {
                     "torch": None, "datasets": None,
                     "peft": None, "trl": None,
                 }):
                with self.assertRaisesRegex(
                    guard.RuntimeGuardError, "claim called"
                ):
                    recipe.execute()
            consume.assert_called_once_with(
                source_commit="a" * 40,
                output_directory=output,
                runtime_evidence_sha256="e" * 64,
                runtime_deadline_utc="2026-09-19T13:00:00Z",
            )


if __name__ == "__main__":
    unittest.main()
