import unittest

from router.auto import classify_auto


class AutoClassifierTests(unittest.TestCase):
    def budget(self, **overrides):
        value = {"ultra_authorized": True, "remaining_usd": 2.0, "estimated_ultra_usd": 0.5}
        value.update(overrides)
        return value

    def classify(self, prompt, entitlement="pro", **budget_overrides):
        return classify_auto(prompt, entitlement=entitlement, budget=self.budget(**budget_overrides))

    def test_simple_requests_route_to_instant(self):
        self.assertEqual(self.classify("What's 8 × 7?")["route_id"], "instant")
        self.assertEqual(self.classify("Rewrite this sentence to sound nicer.")["route_id"], "instant")

    def test_tool_or_debug_request_routes_to_orion_medium(self):
        self.assertEqual(self.classify("What is the latest weather today?")["route_id"], "medium")
        self.assertEqual(self.classify("Debug this React hydration error.")["route_id"], "medium")

    def test_serious_analysis_routes_to_nova(self):
        route = self.classify("Analyze this architecture and identify race conditions and security risks.")
        self.assertEqual(route["route_id"], "high")
        self.assertEqual(route["engine"], "kova-core")

    def test_classifier_terms_match_boundaries_not_substrings(self):
        self.assertEqual(self.classify("What is a bracelet?")["route_id"], "instant")

    def test_multi_domain_project_can_route_to_ultra(self):
        prompt = "Research 30 competitors, create a comprehensive full report, compare pricing, and produce a launch strategy."
        route = self.classify(prompt)
        self.assertEqual(route["route_id"], "ultra")
        self.assertEqual(route["engine"], "kova-ultra")

    def test_ultra_fails_back_to_max_without_entitlement_or_budget(self):
        prompt = "Research competitors and create a comprehensive cross-functional launch strategy and full report."
        self.assertEqual(self.classify(prompt, entitlement="plus")["route_id"], "max")
        self.assertEqual(self.classify(prompt, remaining_usd=0.1)["route_id"], "max")
        self.assertEqual(self.classify(prompt, ultra_authorized=False)["route_id"], "max")

    def test_free_plan_is_server_capped_to_instant(self):
        route = self.classify("Create a comprehensive multi-domain competitor launch strategy.", entitlement="free")
        self.assertEqual(route["route_id"], "instant")
        self.assertEqual(route["feature_ids"], ["free_plan_instant_cap"])

    def test_invalid_budget_context_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "budget context"):
            classify_auto("hello", entitlement="pro", budget={})


if __name__ == "__main__":
    unittest.main()
