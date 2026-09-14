"""Fail-closed Kova request adapter. No deployment or network call occurs on import."""

import json
from pathlib import Path


MODEL = "Qwen/Qwen3.8-27B"
ALLOWED_EFFORTS = frozenset(("low", "medium", "xhigh"))
MAX_OUTPUT_TOKENS = 32768
MAX_MESSAGES = 256
MAX_MESSAGE_TEXT_CHARS = 250_000
MAX_TOTAL_TEXT_CHARS = 750_000
IDENTITY_PATH = Path(__file__).resolve().parents[1] / "config" / "identity.v1.json"
TRUSTED_SYSTEM_IDENTITY = json.loads(IDENTITY_PATH.read_text(encoding="utf-8"))["system_identity"]
TELEMETRY_NUMERIC_FIELDS = (
    "worker_start_ms", "model_load_ms", "queue_ms", "inference_ms",
    "idle_timeout_ms", "gpu_rate_per_second_usd",
)


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
    total_chars = 0
    for message in messages:
        _require(isinstance(message, dict), "message must be an object")
        _require(message.get("role") in ("user", "assistant", "tool"), "client system messages are forbidden")
        content = message.get("content")
        _require(isinstance(content, str), "only text message content is enabled")
        _require(len(content) <= MAX_MESSAGE_TEXT_CHARS, "message content too large")
        total_chars += len(content)
    _require(total_chars <= MAX_TOTAL_TEXT_CHARS, "aggregate message content too large")
    effort = value.get("reasoning_effort")
    _require(effort in ALLOWED_EFFORTS, "invalid reasoning_effort")
    maximum = value.get("max_output_tokens")
    _require(isinstance(maximum, int) and not isinstance(maximum, bool), "invalid max_output_tokens")
    _require(1 <= maximum <= MAX_OUTPUT_TOKENS, "invalid max_output_tokens")
    return value


def validate_telemetry(value):
    _require(isinstance(value, dict), "telemetry missing")
    _require(isinstance(value.get("attempt_id"), str) and value["attempt_id"], "invalid attempt_id")
    _require(isinstance(value.get("cold_start"), bool), "invalid cold_start")
    for field in TELEMETRY_NUMERIC_FIELDS:
        number = value.get(field)
        _require(isinstance(number, (int, float)) and not isinstance(number, bool), f"invalid {field}")
        _require(number >= 0, f"invalid {field}")
    _require(value["gpu_rate_per_second_usd"] > 0, "invalid gpu_rate_per_second_usd")
    return value


def build_engine_request(value):
    value = validate_input(value)
    return {
        "model": MODEL,
        "messages": [{"role": "system", "content": TRUSTED_SYSTEM_IDENTITY}, *value["messages"]],
        "max_tokens": value["max_output_tokens"],
        "reasoning_effort": value["reasoning_effort"],
        "stream": False,
    }


def sanitize_engine_response(request_id, reasoning_effort, response, telemetry):
    telemetry = validate_telemetry(telemetry)
    _require(isinstance(response, dict), "engine response must be an object")
    choices = response.get("choices")
    _require(isinstance(choices, list) and choices, "engine response missing choices")
    first = choices[0]
    _require(isinstance(first, dict), "engine choice must be an object")
    message = first.get("message")
    _require(isinstance(message, dict), "engine response missing message")
    content = message.get("content")
    tool_calls = message.get("tool_calls", [])
    _require(isinstance(content, str), "engine response content must be text")
    _require(isinstance(tool_calls, list), "engine tool_calls must be an array")
    _require(bool(content) or bool(tool_calls), "engine response must contain content or tool_calls")
    hidden_reasoning = message.get("reasoning_content")
    _require(hidden_reasoning in (None, ""), "engine returned hidden reasoning")
    lowered = content.lower()
    _require("<think" not in lowered and "</think>" not in lowered, "engine embedded hidden reasoning in content")

    usage = response.get("usage")
    _require(isinstance(usage, dict), "engine response missing usage")
    input_tokens = usage.get("prompt_tokens")
    output_tokens = usage.get("completion_tokens")
    for label, value in (("input_tokens", input_tokens), ("output_tokens", output_tokens)):
        _require(isinstance(value, int) and not isinstance(value, bool) and value >= 0, f"invalid {label}")

    benchmark = {
        "request_id": request_id,
        "attempt_id": telemetry["attempt_id"],
        "outcome": "success",
        "cold_start": telemetry["cold_start"],
        "reasoning_effort": reasoning_effort,
        **{field: telemetry[field] for field in TELEMETRY_NUMERIC_FIELDS},
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }
    return {
        "request_id": request_id,
        "content": content,
        "tool_calls": tool_calls,
        "usage": usage,
        "benchmark": benchmark,
    }


def handle_job(job, inference_client):
    _require(isinstance(job, dict) and isinstance(job.get("input"), dict), "job input missing")
    value = validate_input(job["input"])
    response = inference_client(build_engine_request(value))
    return sanitize_engine_response(value["request_id"], value["reasoning_effort"], response, job.get("telemetry"))
