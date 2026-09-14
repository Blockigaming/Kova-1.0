"""Fail-closed Kova benchmark worker. Importing it starts no network or paid work."""

import json
from pathlib import Path
from time import perf_counter_ns
from uuid import uuid4


MODEL = "Qwen/Qwen3.8-27B"
MODEL_REVISION = "1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0"
ALLOWED_EFFORTS = frozenset(("low", "medium", "xhigh"))
MAX_OUTPUT_TOKENS = 32768
MAX_MESSAGES = 256
MAX_MESSAGE_TEXT_CHARS = 250_000
MAX_TOTAL_TEXT_CHARS = 750_000
MAX_TOOL_CALL_ID_CHARS = 128
IDENTITY_PATH = Path(__file__).resolve().parents[1] / "config" / "identity.v1.json"
TRUSTED_SYSTEM_IDENTITY = json.loads(IDENTITY_PATH.read_text(encoding="utf-8"))["system_identity"]
RUNTIME_NUMERIC_FIELDS = (
    "worker_start_ms", "model_load_ms", "queue_ms", "idle_timeout_ms",
    "gpu_rate_per_second_usd",
)


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _validated_message(message):
    _require(isinstance(message, dict), "message must be an object")
    role = message.get("role")
    _require(role in ("user", "assistant", "tool"), "client system messages are forbidden")
    allowed_keys = {"role", "content", "tool_call_id"} if role == "tool" else {"role", "content"}
    _require(set(message).issubset(allowed_keys), "message contains unsupported fields")
    content = message.get("content")
    _require(isinstance(content, str), "only text message content is enabled")
    _require(len(content) <= MAX_MESSAGE_TEXT_CHARS, "message content too large")
    cleaned = {"role": role, "content": content}
    if role == "tool":
        tool_call_id = message.get("tool_call_id")
        _require(isinstance(tool_call_id, str) and 1 <= len(tool_call_id) <= MAX_TOOL_CALL_ID_CHARS, "invalid tool_call_id")
        cleaned["tool_call_id"] = tool_call_id
    return cleaned


def validate_input(value):
    _require(isinstance(value, dict), "input must be an object")
    _require("model" not in value, "model is server-controlled")
    _require(set(value).issubset({"request_id", "messages", "reasoning_effort", "max_output_tokens"}), "input contains unsupported fields")
    request_id = value.get("request_id")
    _require(isinstance(request_id, str) and 1 <= len(request_id) <= 128, "invalid request_id")
    messages = value.get("messages")
    _require(isinstance(messages, list) and 1 <= len(messages) <= MAX_MESSAGES, "invalid messages")
    cleaned_messages = [_validated_message(message) for message in messages]
    _require(sum(len(message["content"]) for message in cleaned_messages) <= MAX_TOTAL_TEXT_CHARS, "aggregate message content too large")
    effort = value.get("reasoning_effort")
    _require(effort in ALLOWED_EFFORTS, "invalid reasoning_effort")
    maximum = value.get("max_output_tokens")
    _require(isinstance(maximum, int) and not isinstance(maximum, bool), "invalid max_output_tokens")
    _require(1 <= maximum <= MAX_OUTPUT_TOKENS, "invalid max_output_tokens")
    return {**value, "messages": cleaned_messages}


def validate_runtime_probe(runtime_probe):
    _require(callable(runtime_probe), "trusted runtime probe missing")
    value = runtime_probe()
    _require(isinstance(value, dict), "runtime probe must return an object")
    _require(isinstance(value.get("cold_start"), bool), "invalid cold_start")
    _require(value.get("source") == "server_provider_runtime", "untrusted runtime measurement source")
    for field in RUNTIME_NUMERIC_FIELDS:
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


def _usage_tokens(response):
    if not isinstance(response, dict) or not isinstance(response.get("usage"), dict):
        return 0, 0
    usage = response["usage"]
    values = usage.get("prompt_tokens"), usage.get("completion_tokens")
    if any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in values):
        return 0, 0
    return values


def sanitize_engine_response(request_id, response):
    _require(isinstance(response, dict), "engine response must be an object")
    choices = response.get("choices")
    _require(isinstance(choices, list) and choices, "engine response missing choices")
    first = choices[0]
    _require(isinstance(first, dict), "engine choice must be an object")
    message = first.get("message")
    _require(isinstance(message, dict), "engine response missing message")
    content = message.get("content")
    tool_calls = message.get("tool_calls", [])
    _require(content is None or isinstance(content, str), "engine response content must be text or null")
    _require(isinstance(tool_calls, list), "engine tool_calls must be an array")
    _require(bool(content) or bool(tool_calls), "engine response must contain content or tool_calls")
    hidden_reasoning = message.get("reasoning_content")
    _require(hidden_reasoning in (None, ""), "engine returned hidden reasoning")
    lowered = (content or "").lower()
    _require("<think" not in lowered and "</think>" not in lowered, "engine embedded hidden reasoning in content")
    usage = response.get("usage")
    _require(isinstance(usage, dict), "engine response missing usage")
    input_tokens, output_tokens = _usage_tokens(response)
    _require(input_tokens > 0, "invalid input_tokens")
    _require(output_tokens >= 0, "invalid output_tokens")
    return {
        "request_id": request_id,
        "content": content or "",
        "tool_calls": tool_calls,
        "usage": usage,
    }


def _benchmark_record(value, attempt_id, outcome, elapsed_ms, runtime, response):
    input_tokens, output_tokens = _usage_tokens(response)
    return {
        "request_id": value["request_id"],
        "attempt_id": attempt_id,
        "outcome": outcome,
        "model": MODEL,
        "model_revision": MODEL_REVISION,
        "cold_start": runtime["cold_start"],
        "reasoning_effort": value["reasoning_effort"],
        "worker_start_ms": runtime["worker_start_ms"],
        "model_load_ms": runtime["model_load_ms"],
        "queue_ms": runtime["queue_ms"],
        "inference_ms": elapsed_ms,
        "idle_timeout_ms": runtime["idle_timeout_ms"],
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "gpu_rate_per_second_usd": runtime["gpu_rate_per_second_usd"],
        "measurement_source": runtime["source"],
    }


def handle_job(job, inference_client, runtime_probe, telemetry_sink, *, clock_ns=perf_counter_ns, attempt_id_factory=lambda: str(uuid4())):
    """Execute one attempt and persist success or failure telemetry before returning/raising."""
    _require(isinstance(job, dict) and set(job) == {"input"} and isinstance(job["input"], dict), "job must contain only input")
    _require(callable(inference_client), "inference client missing")
    _require(callable(telemetry_sink), "telemetry sink missing")
    value = validate_input(job["input"])
    runtime = validate_runtime_probe(runtime_probe)
    attempt_id = attempt_id_factory()
    _require(isinstance(attempt_id, str) and attempt_id, "invalid server attempt_id")
    started_ns = clock_ns()
    response = None
    finished_ns = None
    try:
        response = inference_client(build_engine_request(value))
        finished_ns = clock_ns()
        result = sanitize_engine_response(value["request_id"], response)
    except Exception:
        if finished_ns is None:
            finished_ns = clock_ns()
        failed = _benchmark_record(value, attempt_id, "failed", max(0, finished_ns - started_ns) / 1_000_000, runtime, response)
        telemetry_sink(failed)
        raise
    succeeded = _benchmark_record(value, attempt_id, "success", max(0, finished_ns - started_ns) / 1_000_000, runtime, response)
    telemetry_sink(succeeded)
    result["benchmark"] = succeeded
    return result
