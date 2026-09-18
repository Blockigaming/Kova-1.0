import unittest

from release.current_product_policy import validate


class CurrentProductPolicyTests(unittest.TestCase):
    def test_owner_policy_is_structurally_valid_and_not_misreported_live(self):
        report = validate()
        self.assertEqual(report["owner_comment_id"], 5734534302)
        self.assertTrue(report["chat_shared_model_policy_valid"])
        self.assertTrue(report["work_three_distinct_model_slots_policy_valid"])
        self.assertTrue(report["work_effort_contracts_match_current_compute"])
        self.assertEqual(report["selected_upstream_models"], {
            "chat-shared": "Qwen/Qwen3-8B",
            "work-cosmo": "Qwen/Qwen3-0.6B",
            "work-orion": "Qwen/Qwen3-1.7B",
            "work-nova": "Qwen/Qwen3-4B",
        })
        self.assertEqual(report["missing_upstream_revision_slots"],
                         ["chat-shared", "work-cosmo", "work-orion", "work-nova"])
        self.assertEqual(report["closed_checklist_ids"], [])
        self.assertFalse(report["phase_b_ready"])

    def test_current_runtime_mismatches_are_exposed_instead_of_hidden(self):
        report = validate()
        self.assertFalse(report["runtime_chat_model_identity_aligned"])
        self.assertFalse(report["runtime_work_model_identity_aligned"])

    def test_missing_weekly_and_replenishment_terms_remain_explicit(self):
        report = validate()
        self.assertTrue(report["missing_plus_weekly_units"])
        self.assertTrue(report["missing_reset_anchor"])
        self.assertTrue(report["missing_replenishment_terms"])


if __name__ == "__main__":
    unittest.main()
