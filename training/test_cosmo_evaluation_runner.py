"""Source-only tests for the guarded three-way Cosmo generation runner."""
from contextlib import redirect_stderr
from copy import deepcopy
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from training import cosmo_evaluation_runner as runner


class CosmoEvaluationRunnerTests(unittest.TestCase):
    def setUp(self):
        self.plan, self.cases, _ = runner.evaluation.load_plan()
        _, self.prompt, _ = runner.pilot.load()

    def test_current_runner_is_blocked_before_runtime_or_dependencies(self):
        with patch.object(runner, "require_ready",
                          side_effect=AssertionError("runtime called")), \
             patch.object(runner, "verify_installed_software",
                          side_effect=AssertionError("dependencies called")):
            with self.assertRaises(runner.EvaluationRunnerError):
                runner.authorize()

    def test_environment_confirmation_cannot_override_source_gates(self):
        with patch.dict(os.environ, {runner.CONFIRMATION_ENV: "YES"}), \
             patch.object(runner, "require_ready",
                          side_effect=AssertionError("runtime called")):
            with self.assertRaises(runner.EvaluationRunnerError):
                runner.authorize()

    def test_released_source_still_requires_fresh_runtime_evidence(self):
        recipe = deepcopy(runner.load_recipe())
        recipe["account_gates"]["eastus_ncast4_quota_verified"] = True
        recipe["account_gates"]["runtime_compatibility_verified"] = True
        with patch.object(runner, "load_recipe", return_value=recipe), \
             patch.dict(os.environ, {runner.CONFIRMATION_ENV: "YES",
                                     runner.SOURCE_COMMIT_ENV: "a" * 40}), \
             patch.object(runner, "verify_source_checkout"), \
             patch.object(runner, "require_ready",
                          side_effect=runner.EvaluationRunnerError("runtime")), \
             patch.object(runner, "verify_installed_software",
                          side_effect=AssertionError("dependencies called")):
            with self.assertRaisesRegex(runner.EvaluationRunnerError, "runtime"):
                runner.authorize()

    def test_variants_apply_only_the_declared_system_prompt(self):
        ordinary = self.cases["validation-001"]
        base = runner.messages_for_variant(ordinary, "base", self.prompt)
        configured = runner.messages_for_variant(
            ordinary, "configured_base", self.prompt
        )
        trained = runner.messages_for_variant(
            ordinary, "trained_adapter", self.prompt
        )
        self.assertEqual([item["role"] for item in base], ["user"])
        self.assertEqual([item["role"] for item in configured], ["system", "user"])
        self.assertEqual(configured, trained)
        self.assertEqual(configured[0]["content"], self.prompt)

        provenance = self.cases["validation-011"]
        messages = runner.messages_for_variant(
            provenance, "trained_adapter", self.prompt
        )
        self.assertIn("Offline evaluation fixture only", messages[0]["content"])

    def test_attempt_records_are_schema_compatible_and_scores_stay_pending(self):
        case = self.cases["validation-001"]
        runtime = {
            "base_model": self.plan["base_model"],
            "base_revision": self.plan["base_revision"],
            "adapter_sha256": None,
            "adapter_receipt_sha256": "a" * 64,
            "software_lock_sha256": "b" * 64,
            "runtime_evidence_sha256": "c" * 64,
            "hardware": "fixture",
            "precision": "fp16",
            "quantization": "none",
        }
        success = runner.attempt_record(
            case=case, variant="base", runtime=runtime, answer="fixture",
            latency_ms=1, input_tokens=2, output_tokens=3,
        )
        failed = runner.attempt_record(
            case=case, variant="configured_base", runtime=runtime
        )
        self.assertEqual(success["outcome"], "success")
        self.assertEqual(failed["outcome"], "failed")
        self.assertTrue(all(value == "pending"
                            for value in success["scores"].values()))
        self.assertIsNone(failed["answer_sha256"])

    def test_external_paths_reject_existing_output_and_repository_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            self.assertEqual(runner.external_existing(str(parent)), parent)
            new = parent / "new"
            self.assertEqual(runner.external_new(str(new)), new)
            new.mkdir()
            with self.assertRaises(runner.EvaluationRunnerError):
                runner.external_new(str(new))

        with tempfile.TemporaryDirectory(dir=runner.ROOT) as directory:
            internal = Path(directory)
            with self.assertRaises(runner.EvaluationRunnerError):
                runner.external_existing(str(internal))
            with self.assertRaises(runner.EvaluationRunnerError):
                runner.external_new(str(internal / "new"))

    def test_dry_run_declares_all_attempts_without_execution_claims(self):
        report = runner.dry_run()
        self.assertEqual(report["expected_attempts"], 36)
        self.assertEqual(report["variants"], [
            "base", "configured_base", "trained_adapter",
        ])
        self.assertEqual(report["rubric_sha256"], self.plan["rubric_sha256"])
        self.assertFalse(report["model_outputs_generated"])
        self.assertFalse(report["actual_model_outputs_evaluated"])
        self.assertFalse(report["phase_b_ready"])

    def test_execute_cli_is_sanitized_and_nonzero_while_blocked(self):
        error = io.StringIO()
        with redirect_stderr(error):
            self.assertEqual(runner.main(["--execute"]), 1)
        self.assertEqual(
            error.getvalue(), "kova cosmo evaluation runner rejected\n"
        )


if __name__ == "__main__":
    unittest.main()
