"""Offline checks for the guarded Kova Cosmo SFT recipe."""
from contextlib import redirect_stderr
from copy import deepcopy
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from training import kova_cosmo_sft as recipe


class KovaCosmoSftTests(unittest.TestCase):
    def test_dry_run_is_nonexecuting_and_pinned(self):
        report = recipe.dry_run()
        self.assertEqual(report["display_name"], "Kova Cosmo")
        self.assertEqual(report["region"], "eastus")
        self.assertEqual(report["vm_size"], "Standard_NC4as_T4_v3")
        self.assertEqual(report["precision"], "fp16")
        self.assertFalse(report["model_weights_downloaded"])
        self.assertFalse(report["training_started"])
        self.assertFalse(report["phase_b_ready"])

    def test_current_package_versions_are_exact(self):
        self.assertEqual(recipe.load_recipe()["software"], {
            "python": "3.12",
            "torch": "2.8.0",
            "transformers": "5.17.0",
            "peft": "0.21.0",
            "trl": "1.13.0",
            "accelerate": "1.15.0",
            "datasets": "5.0.1",
        })

    def test_lora_targets_are_explicit_and_stable(self):
        value = recipe.load_recipe()
        self.assertEqual(value["lora"]["target_modules"], recipe.EXPECTED_TARGETS)
        self.assertEqual(value["lora"]["r"], 16)
        self.assertEqual(value["lora"]["alpha"], 32)

    def test_t4_recipe_uses_fp16_not_bf16(self):
        value = recipe.load_recipe()
        self.assertEqual(value["hardware"]["precision"], "fp16")
        self.assertIs(value["hardware"]["bf16"], False)
        self.assertIs(value["hardware"]["quantized_base"], False)

    def test_first_cosmo_pilot_is_plain_lora_not_q_lora(self):
        value = recipe.load_recipe()
        self.assertEqual(value["method"], "lora_sft")
        self.assertFalse(value["hardware"]["quantized_base"])

    def test_completion_only_loss_keeps_prompt_tokens_out_of_objective(self):
        value = recipe.load_recipe()
        self.assertIs(value["training"]["completion_only_loss"], True)
        self.assertIs(value["training"]["packing"], False)

    def test_remote_reporting_and_hub_push_are_disabled(self):
        training = recipe.load_recipe()["training"]
        self.assertEqual(training["report_to"], "none")
        self.assertIs(training["push_to_hub"], False)

    def test_quota_and_budget_are_still_unverified(self):
        gates = recipe.load_recipe()["account_gates"]
        self.assertIs(gates["eastus_ncast4_quota_verified"], False)
        self.assertIsNone(gates["approved_budget_usd"])

    def test_all_execution_permissions_are_false(self):
        permissions = recipe.load_recipe()["execution"]
        self.assertEqual(permissions, {
            "model_download_authorized": False,
            "training_authorized": False,
            "deployment_authorized": False,
        })

    def test_execute_fails_before_heavy_library_imports(self):
        with patch.dict("sys.modules", {
            "torch": None,
            "datasets": None,
            "peft": None,
            "trl": None,
        }):
            with self.assertRaises(recipe.RecipeError):
                recipe.execute()

    def test_operator_environment_variable_cannot_override_source_guards(self):
        with patch.dict("os.environ", {"KOVA_CONFIRM_PAID_TRAINING": "YES"}):
            with self.assertRaises(recipe.RecipeError):
                recipe.execute()

    def test_dry_run_never_closes_phase_a_items(self):
        report = recipe.dry_run()
        self.assertEqual(report["closed_checklist_ids"], [])
        self.assertFalse(report["runtime_integrated"])

    def test_cli_execute_returns_nonzero_while_blocked(self):
        error = io.StringIO()
        with redirect_stderr(error):
            self.assertEqual(recipe.main(["--execute"]), 1)
        self.assertEqual(error.getvalue(), "kova cosmo sft recipe rejected\n")


if __name__ == "__main__":
    unittest.main()
