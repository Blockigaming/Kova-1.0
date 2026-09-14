"""Fail-closed Kova request adapter. No deployment or network call occurs on import."""

MODEL = "Qwen/Qwen3.8-27B"
ALLOWED_EFFORTS = frozenset(("low", "medium", "xhigh"))
MAX_OUTPUT_TOKENS = 32768
MAX_MESSAGES = 256
MAX_TEXT_CHARS = 1_000_000


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_input(value):
    _require(isinstance(value, dict), "input must be an object")
    _require("model" not in value, "model is server-controlled")
    request_id = value.get("request_id")
    _require(isinstance(request_id, str) and 1 <= len(request_id) <= 128, "invalid request_id")
    messages = value.get("messages")
    _require(isinstance(messages, list) and 1 <= len(messages) <= MAX_MESSAGES, "invalid messages")
    for message in messages:
        _require(isinstance(message, dict), "message must be an object")
        _require(message.get("role") in ("system", "user", "assistant", "tool"), "invalid message role")
        content = message.get("content")
        _require(isinstance(content, str), "only text message content is enabled")
        _require(len(content) <= MAX_TEXT_CHARS, "message content too large")
    effort = value.get("reasoning_effort")
    _require(effort in ALLOWED_EFFORTS, "invalid reasoning_effort")
    maximum = value.get("max_output_tokens")
    _require(isinstance(maximum, int) and not isinstance(maximum, bool), "invalid max_output_tokens")
    _require(1 <= maximum <= MAX_OUTPUT_TOKENS, "invalid max_output_tokens")
    return value


def build_engine_request(value):
    value = validate_input(value)
    return {
        "model": MODEL,
        "messages": value["messages"],
        "max_tokens": value["max_output_tokens"],
        "reasoning_effort": value["reasoning_effort"],
        "stream": False,
    }


def sanitize_engine_response(request_id, response):
    _require(isinstance(response, dict), "engine response must be an object")
    choices = response.get("choices")
    _require(isinstance(choices, list) and choices, "engine response missing choices")
    message = choices[0].get("message", {})
    return {
        "request_id": request_id,
        "content": message.get("content", ""),
        "tool_calls": message.get("tool_calls", []),
        "usage": response.get("usage", {}),
    }


def handle_job(job, inference_client):
    _require(isinstance(job, dict) and isinstance(job.get("input"), dict), "job input missing")
    value = validate_input(job["input"])
    response = inference_client(build_engine_request(value))
    return sanitize_engine_response(value["request_id"], response)
