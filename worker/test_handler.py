import unittest

from worker.handler import MODEL, build_engine_request, handle_job


class HandlerTests(unittest.TestCase):
    def request(self, **overrides):
        value = {
            "request_id": "request-1",
            "messages": [{"role": "user", "content": "hello"}],
            "reasoning_effort": "low",
            "max_output_tokens": 100,
        }
        value.update(overrides)
        return value

    def test_model_is_pinned(self):
        self.assertEqual(build_engine_request(self.request())["model"], MODEL)

    def test_caller_cannot_select_model(self):
        with self.assertRaisesRegex(ValueError, "server-controlled"):
            build_engine_request(self.request(model="attacker/model"))

    def test_invalid_effort_and_token_limit_fail(self):
        with self.assertRaisesRegex(ValueError, "reasoning_effort"):
            build_engine_request(self.request(reasoning_effort="ultra"))
        with self.assertRaisesRegex(ValueError, "max_output_tokens"):
            build_engine_request(self.request(max_output_tokens=32769))

    def test_remote_multimodal_content_is_blocked(self):
        with self.assertRaisesRegex(ValueError, "only text"):
            build_engine_request(self.request(messages=[{
                "role": "user",
                "content": [{"type": "image_url", "image_url": {"url": "http://127.0.0.1/private"}}],
            }]))

    def test_hidden_reasoning_is_not_returned(self):
        def client(_payload):
            return {
                "choices": [{"message": {"content": "answer", "reasoning_content": "secret"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            }

        result = handle_job({"input": self.request()}, client)
        self.assertEqual(result["content"], "answer")
        self.assertNotIn("reasoning_content", result)


if __name__ == "__main__":
    unittest.main()
