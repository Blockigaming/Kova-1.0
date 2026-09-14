import unittest

from core.adapter import CANDIDATES, IDENTITY, build_core_plan


class CoreAdapterTests(unittest.TestCase):
    def request(self, **overrides):
        value = {"request_id": "request-1", "route_id": "instant", "messages": [{"role": "user", "content": "hello"}]}
        value.update(overrides)
        return value

    def model(self):
        return "@cf/qwen/qwen3.8-27b"

    def build(self, request=None, model=None, token_count=100):
        return build_core_plan(
            request or self.request(), candidate_model=model or self.model(),
            token_counter=lambda _model, _messages: token_count,
        )

    def test_verified_candidate_registry_is_loaded_from_architecture(self):
        self.assertIn(self.model(), CANDIDATES)
        self.assertEqual(CANDIDATES[self.model()]["context_tokens"], 262144)

    def test_instant_is_one_streaming_operation(self):
        plan = self.build()
        self.assertEqual(len(plan["operations"]), 1)
        operation = plan["operations"][0]
        self.assertEqual(operation["stage_id"], "answer-1")
        self.assertTrue(operation["public_response"])
        self.assertTrue(operation["request"]["stream"])
        self.assertFalse(operation["activity_event_allowed_after_start"])

    def test_max_has_real_multi_pass_operations_and_only_final_streams(self):
        plan = self.build(self.request(route_id="max"))
        self.assertEqual(len(plan["operations"]), 10)
        self.assertTrue(all(not item["public_response"] for item in plan["operations"][:-1]))
        self.assertTrue(plan["operations"][-1]["public_response"])
        self.assertEqual(plan["operations"][-1]["phase"], "verification")
        self.assertEqual(plan["operations"][0]["depends_on_stage_ids"], [])
        self.assertEqual(plan["operations"][1]["depends_on_stage_ids"], [plan["operations"][0]["stage_id"]])
        self.assertEqual(plan["operations"][1]["input_context"], "conversation_plus_prior_private_artifacts")

    def test_identity_model_effort_and_limits_are_server_controlled(self):
        plan = self.build(self.request(route_id="medium"))
        provider_request = plan["operations"][0]["request"]
        self.assertEqual(provider_request["messages"][0]["content"], IDENTITY)
        self.assertEqual(provider_request["reasoning_effort"], "medium")
        self.assertEqual(provider_request["max_completion_tokens"], 4096)
        with self.assertRaisesRegex(ValueError, "server-controlled"):
            self.build(self.request(model="attacker/model"))

    def test_ultra_and_unknown_models_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "not eligible"):
            self.build(self.request(route_id="ultra"))
        with self.assertRaisesRegex(ValueError, "unverified"):
            self.build(model="@cf/attacker/model")

    def test_no_operation_is_production_ready(self):
        plan = self.build(self.request(route_id="high"))
        self.assertFalse(plan["production_ready"])
        self.assertTrue(all(operation["request"]["store"] is False for operation in plan["operations"]))

    def test_trusted_token_count_is_required_and_context_is_enforced(self):
        with self.assertRaisesRegex(ValueError, "token counter"):
            build_core_plan(self.request(), candidate_model=self.model(), token_counter=None)
        with self.assertRaisesRegex(ValueError, "exceeds candidate context"):
            self.build(token_count=262144)


if __name__ == "__main__":
    unittest.main()
