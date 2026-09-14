import unittest

from ultra.orchestrator import build_ultra_plan


class UltraPlannerTests(unittest.TestCase):
    def admission(self, **overrides):
        value = {
            "entitlement": "pro", "ultra_authorized": True, "remaining_usd": 2.0,
            "estimated_max_usd": 0.5, "max_agents": 5, "max_total_tokens": 32768,
        }
        value.update(overrides)
        return value

    def request(self, task="Research competitors, pricing, security, and produce a launch report."):
        return {"request_id": "request-1", "task": task}

    def test_plan_uses_dynamic_bounded_specialists(self):
        plan = build_ultra_plan(self.request(), admission=self.admission())
        specialists = [operation for operation in plan["operations"] if operation.get("parallel_group") == "specialists"]
        self.assertGreaterEqual(len(specialists), 2)
        self.assertLessEqual(len(specialists), 5)
        self.assertIn("research", plan["domains"])
        self.assertIn("business", plan["domains"])

    def test_judge_debate_and_synthesis_have_real_dependencies(self):
        plan = build_ultra_plan(self.request(), admission=self.admission(max_agents=3))
        by_id = {operation["id"]: operation for operation in plan["operations"]}
        self.assertEqual(len(by_id["judge"]["depends_on"]), 3)
        self.assertEqual(by_id["debate-round-1"]["condition"], "judge_detected_material_disagreement")
        self.assertTrue(by_id["synthesis"]["public_output"])
        self.assertTrue(all(not operation["public_output"] for operation in plan["operations"][:-1]))

    def test_direct_ultra_requires_pro_authorization_and_budget(self):
        with self.assertRaisesRegex(ValueError, "Pro"):
            build_ultra_plan(self.request(), admission=self.admission(entitlement="plus"))
        with self.assertRaisesRegex(ValueError, "not authorized"):
            build_ultra_plan(self.request(), admission=self.admission(ultra_authorized=False))
        with self.assertRaisesRegex(ValueError, "budget exceeded"):
            build_ultra_plan(self.request(), admission=self.admission(remaining_usd=0.1))

    def test_caller_cannot_supply_model_or_agent_count(self):
        with self.assertRaisesRegex(ValueError, "unsupported fields"):
            build_ultra_plan({**self.request(), "model": "attacker/model"}, admission=self.admission())
        with self.assertRaisesRegex(ValueError, "unsupported fields"):
            build_ultra_plan({**self.request(), "max_agents": 100}, admission=self.admission())

    def test_source_plan_never_claims_deployment_or_selected_model(self):
        plan = build_ultra_plan(self.request("Prove this probability equation."), admission=self.admission())
        self.assertFalse(plan["production_ready"])
        self.assertTrue(plan["model_selection_required"])
        self.assertEqual(plan["provider"], "runpod_serverless")


if __name__ == "__main__":
    unittest.main()
