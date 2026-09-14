"""Fail-closed Kova Core benchmark worker. Importing it starts no paid work."""

import json
from pathlib import Path
from time import perf_counter_ns
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
MODEL = "Qwen/Qwen3.8-27B"
MODEL_REVISION = "1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0"
ALLOWED_EFFORTS = frozenset(("low", "medium", "xhigh"))
ALLOWED_SERVING_ENGINES = frozenset(("vllm", "sglang"))
ALLOWED_ENDPOINT_TYPES = frozenset(("queue_based", "load_balancing"))
MAX_OUTPUT_TOKENS = 32768
MAX_MESSAGES = 256
MAX_MESSAGE_TEXT_CHARS = 250_000
MAX_TOTAL_TEXT_CHARS = 750_000
TRUSTED_SYSTEM_IDENTITY = json.loads(
    (ROOT / "config" / "identity.v1.json").read_text(encoding="utf-8")
)["system_identity"]
ROUTE_POLICY = json.loads(
    (ROOT / "config" / "route-policy.v1.json").read_text(encoding="utf-8")
)
RUNTIME_NUMERIC_FIELDS = (
    "worker_start_ms", "model_load_ms", "queue_ms", "gpu_rate_per_second_usd",
)
RUNTIME_IDENTITY_FIELDS = (
    "source", "worker_lifecycle_id", "cold_start", "worker_start_ms", "model_load_ms",
    "queue_ms", "gpu_rate_per_second_usd", "gpu_type_id", "gpu_count", "serving_engine",
    "endpoint_type", "container_image_digest",
)


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _stage_ids(policy):
    stages = []
    for phase, field in (
        ("planning", "planning_passes"), ("answer", "answer_passes"),
        ("critic", "critic_passes"), ("verification", "verification_passes"),
    ):
        stages.extend(f"{phase}-{index}" for index in range(1, policy.get(field, 0) + 1))
    return stages


CORE_ROUTE_STAGES = {}
CORE_ROUTE_EFFORTS = {}
for route in ROUTE_POLICY["chat"]:
    if route["engine"] == "kova-core":
        CORE_ROUTE_STAGES[route["id"]] = _stage_ids(route)
        CORE_ROUTE_EFFORTS[route["id"]] = route["reasoning_effort"]
for family in ROUTE_POLICY["work"]["families"]:
    for effort in ROUTE_POLICY["work"]["effort_profiles"]:
        if effort["engine"] == "kova-core":
            route_id = f"work:{family}:{effort['name'].lower().replace(' ', '-')}"
            CORE_ROUTE_STAGES[route_id] = _stage_ids(effort)
            CORE_ROUTE_EFFORTS[route_id] = effort["reasoning_effort"]


def _validated_message(message):
    _require(isinstance(message, dict), "message must be an object")
    role = message.get("role")
    _require(role in ("user", "assistant"), "client system and tool messages are forbidden")
    _require(set(message) == {"role", "content"}, "message contains unsupported fields")
    content = message.get("content")
    _require(isinstance(content, str), "only text message content is enabled")
    _require(len(content) <= MAX_MESSAGE_TEXT_CHARS, "message content too large")
    return {"role": role, "content": content}


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


def validate_execution_context(value):
    _require(isinstance(value, dict), "trusted execution context missing")
    _require(set(value) == {"route_id", "stage_id", "public_response"}, "invalid trusted execution context")
    route_id = value["route_id"]
    stage_id = value["stage_id"]
    _require(route_id in CORE_ROUTE_STAGES, "execution route is not Kova Core")
    _require(stage_id in CORE_ROUTE_STAGES[route_id], "invalid execution stage")
    _require(isinstance(value["public_response"], bool), "invalid public_response")
    _require(value["public_response"] == (stage_id == CORE_ROUTE_STAGES[route_id][-1]), "public_response does not match route DAG")
    return dict(value)


def _validate_runtime_value(value, *, include_first_token):
    _require(isinstance(value, dict), "runtime probe must return an object")
    required = set(RUNTIME_IDENTITY_FIELDS)
    if include_first_token:
        required.add("time_to_first_token_ms")
    _require(set(value) == required, "runtime probe returned unsupported or missing fields")
    _require(isinstance(value.get("cold_start"), bool), "invalid cold_start")
    _require(value.get("source") == "server_provider_runtime", "untrusted runtime measurement source")
    for field in RUNTIME_NUMERIC_FIELDS:
        number = value.get(field)
        _require(isinstance(number, (int, float)) and not isinstance(number, bool), f"invalid {field}")
        _require(number >= 0, f"invalid {field}")
    _require(value["gpu_rate_per_second_usd"] > 0, "invalid gpu_rate_per_second_usd")
    _require(isinstance(value["worker_lifecycle_id"], str) and value["worker_lifecycle_id"], "invalid worker_lifecycle_id")
    _require(isinstance(value["gpu_type_id"], str) and value["gpu_type_id"].strip(), "invalid gpu_type_id")
    _require(isinstance(value["gpu_count"], int) and not isinstance(value["gpu_count"], bool) and 1 <= value["gpu_count"] <= 8, "invalid gpu_count")
    _require(value["serving_engine"] in ALLOWED_SERVING_ENGINES, "invalid serving_engine")
    _require(value["endpoint_type"] in ALLOWED_ENDPOINT_TYPES, "invalid endpoint_type")
    digest = value["container_image_digest"]
    _require(isinstance(digest, str) and len(digest) == 71 and digest.startswith("sha256:") and all(character in "0123456789abcdef" for character in digest[7:]), "invalid container_image_digest")
    startup_ms = value["worker_start_ms"] + value["model_load_ms"]
    _require(startup_ms > 0 if value["cold_start"] else startup_ms == 0, "cold_start and startup attribution disagree")
    if include_first_token:
        first_token = value["time_to_first_token_ms"]
        _require(isinstance(first_token, (int, float)) and not isinstance(first_token, bool) and first_token >= 0, "invalid time_to_first_token_ms")
    return dict(value)


def validate_runtime_probe(runtime_probe, phase):
    _require(callable(runtime_probe), "trusted runtime probe missing")
    _require(phase in ("before", "after"), "invalid runtime probe phase")
    return _validate_runtime_value(runtime_probe(phase), include_first_token=phase == "after")


def build_engine_request(value):
    value = validate_input(value)
    return {
        "model": MODEL,
        "messages": [{"role": "system", "content": TRUSTED_SYSTEM_IDENTITY}, *value["messages"]],
        "max_tokens": value["max_output_tokens"],
        "reasoning_effort": value["reasoning_effort"],
        "chat_template_kwargs": {
            "enable_thinking": value["reasoning_effort"] != "low",
            "preserve_thinking": False,
        },
        "stream": True,
        "stream_options": {"include_usage": True},
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
    _require(message.get("reasoning_content") in (None, ""), "engine returned hidden reasoning")
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


def _attempt_record(value, execution, attempt_id, outcome, elapsed_ms, runtime, response):
    input_tokens, output_tokens = _usage_tokens(response)
    return {
        "record_type": "attempt",
        "request_id": value["request_id"],
        "attempt_id": attempt_id,
        "outcome": outcome,
        "model": MODEL,
        "model_revision": MODEL_REVISION,
        "route_id": execution["route_id"],
        "stage_id": execution["stage_id"],
        "public_response": execution["public_response"],
        "worker_lifecycle_id": runtime["worker_lifecycle_id"],
        "cold_start": runtime["cold_start"],
        "reasoning_effort": value["reasoning_effort"],
        "worker_start_ms": runtime["worker_start_ms"],
        "model_load_ms": runtime["model_load_ms"],
        "queue_ms": runtime["queue_ms"],
        "inference_ms": elapsed_ms,
        "time_to_first_token_ms": runtime["time_to_first_token_ms"],
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "gpu_rate_per_second_usd": runtime["gpu_rate_per_second_usd"],
        "gpu_type_id": runtime["gpu_type_id"],
        "gpu_count": runtime["gpu_count"],
        "serving_engine": runtime["serving_engine"],
        "endpoint_type": runtime["endpoint_type"],
        "container_image_digest": runtime["container_image_digest"],
        "measurement_source": runtime["source"],
    }


def emit_lifecycle_close(runtime_close_probe, telemetry_sink, *, close_event_id_factory=lambda: str(uuid4())):
    """Emit the idle-tail event only after the trusted runtime observes worker shutdown."""
    _require(callable(runtime_close_probe), "trusted lifecycle close probe missing")
    _require(callable(telemetry_sink), "telemetry sink missing")
    value = runtime_close_probe()
    required = {
        "source", "worker_lifecycle_id", "attributed_idle_timeout_ms", "gpu_rate_per_second_usd",
        "gpu_type_id", "gpu_count", "serving_engine", "endpoint_type", "container_image_digest",
    }
    _require(isinstance(value, dict) and set(value) == required, "invalid lifecycle close probe")
    identity_probe = {
        **{field: value[field] for field in (
            "source", "worker_lifecycle_id", "gpu_rate_per_second_usd", "gpu_type_id",
            "gpu_count", "serving_engine", "endpoint_type", "container_image_digest",
        )},
        "cold_start": False,
        "worker_start_ms": 0,
        "model_load_ms": 0,
        "queue_ms": 0,
    }
    validated = _validate_runtime_value(identity_probe, include_first_token=False)
    idle_ms = value["attributed_idle_timeout_ms"]
    _require(isinstance(idle_ms, (int, float)) and not isinstance(idle_ms, bool) and idle_ms > 0, "invalid attributed_idle_timeout_ms")
    close_event_id = close_event_id_factory()
    _require(isinstance(close_event_id, str) and close_event_id, "invalid close_event_id")
    record = {
        "record_type": "lifecycle_close",
        "close_event_id": close_event_id,
        "worker_lifecycle_id": validated["worker_lifecycle_id"],
        "model": MODEL,
        "model_revision": MODEL_REVISION,
        "attributed_idle_timeout_ms": idle_ms,
        "gpu_rate_per_second_usd": validated["gpu_rate_per_second_usd"],
        "gpu_type_id": validated["gpu_type_id"],
        "gpu_count": validated["gpu_count"],
        "serving_engine": validated["serving_engine"],
        "endpoint_type": validated["endpoint_type"],
        "container_image_digest": validated["container_image_digest"],
        "measurement_source": validated["source"],
    }
    telemetry_sink(record)
    return record


def handle_job(
    job, inference_client, runtime_probe, telemetry_sink, *, execution_context,
    clock_ns=perf_counter_ns, attempt_id_factory=lambda: str(uuid4()),
):
    """Execute one Core stage and persist its attempt telemetry before returning or raising."""
    _require(isinstance(job, dict) and set(job) == {"input"} and isinstance(job["input"], dict), "job must contain only input")
    _require(callable(inference_client), "inference client missing")
    _require(callable(telemetry_sink), "telemetry sink missing")
    value = validate_input(job["input"])
    execution = validate_execution_context(execution_context)
    _require(value["reasoning_effort"] == CORE_ROUTE_EFFORTS[execution["route_id"]], "reasoning_effort does not match trusted route")
    before = validate_runtime_probe(runtime_probe, "before")
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
        after = validate_runtime_probe(runtime_probe, "after")
        _require(all(after[field] == before[field] for field in RUNTIME_IDENTITY_FIELDS), "runtime identity changed during attempt")
        elapsed_ms = max(0, finished_ns - started_ns) / 1_000_000
        _require(after["time_to_first_token_ms"] <= elapsed_ms, "first token exceeds measured inference")
        failed = _attempt_record(value, execution, attempt_id, "failed", elapsed_ms, after, response)
        telemetry_sink(failed)
        raise
    after = validate_runtime_probe(runtime_probe, "after")
    _require(all(after[field] == before[field] for field in RUNTIME_IDENTITY_FIELDS), "runtime identity changed during attempt")
    elapsed_ms = max(0, finished_ns - started_ns) / 1_000_000
    _require(after["time_to_first_token_ms"] <= elapsed_ms, "first token exceeds measured inference")
    succeeded = _attempt_record(value, execution, attempt_id, "success", elapsed_ms, after, response)
    telemetry_sink(succeeded)
    result["benchmark"] = succeeded
    return result
