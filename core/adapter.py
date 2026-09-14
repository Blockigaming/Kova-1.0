"""Build RunPod Kova Core plans without performing network requests."""

import json
from pathlib import Path

from router.policy import resolve_route


ROOT = Path(__file__).resolve().parents[1]
IDENTITY = json.loads((ROOT / "config" / "identity.v1.json").read_text(encoding="utf-8"))["system_identity"]
CORE_SERVING = json.loads((ROOT / "config" / "core-serving.v1.json").read_text(encoding="utf-8"))
CANDIDATES = {candidate["model"]: candidate for candidate in CORE_SERVING["candidates"]}
CORE_ROUTE_LIMITS = {
    "instant": 2048,
    "medium": 4096,
    "high": 8192,
    "extra-high": 16384,
    "max": 24576,
}
STAGE_INSTRUCTIONS = {
    "planning": "Create only a concise private execution plan for the next stage. Do not expose hidden chain-of-thought.",
    "answer": "Produce or revise the answer using available verified context. Do not invent tool results.",
    "critic": "Identify concrete defects in the draft without exposing hidden chain-of-thought.",
    "verification": "Return the corrected final answer. Include only conclusions and useful concise explanation.",
}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _messages(value):
    _require(isinstance(value, list) and 1 <= len(value) <= 256, "messages must contain 1 to 256 items")
    cleaned = []
    total = 0
    for message in value:
        _require(isinstance(message, dict) and set(message) == {"role", "content"}, "unsupported message schema")
        _require(message["role"] in ("user", "assistant"), "unsupported message role")
        _require(isinstance(message["content"], str), "message content must be text")
        _require(len(message["content"]) <= 250_000, "message content too large")
        total += len(message["content"])
        cleaned.append({"role": message["role"], "content": message["content"]})
    _require(total <= 750_000, "aggregate message content too large")
    return cleaned


def _stages(policy):
    planning, answers, critics, verifications = policy["passes"]
    stages = []
    for kind, count in (("planning", planning), ("answer", answers), ("critic", critics), ("verification", verifications)):
        stages.extend((kind, index + 1) for index in range(count))
    return stages


def _resolved_policy(value):
    keys = set(value)
    if "route_id" in value:
        _require(keys == {"request_id", "messages", "route_id"}, "request contains unsupported or server-controlled fields")
        policy = resolve_route({"surface": "chat", "route_id": value["route_id"]})
    else:
        expected = {"request_id", "messages", "surface", "family", "effort"}
        _require(keys == expected and value.get("surface") == "work", "request contains unsupported or server-controlled fields")
        policy = resolve_route({"surface": "work", "family": value["family"], "effort": value["effort"]})
    _require(policy["engine"] == "kova-core", "route is not eligible for Kova Core")
    return policy


def _stage_output_limit(kind, route_limit, is_final):
    if is_final:
        return route_limit
    if kind in ("planning", "critic"):
        return min(2048, route_limit)
    return min(8192, route_limit)


def _artifact_message(stage_id):
    return {
        "role": "system",
        "content": (
            f"Trusted private Kova stage artifact {stage_id}: "
            f"{{{{server_stage_output:{stage_id}}}}}"
        ),
    }


def build_core_plan(value, *, candidate_model, token_counter):
    """Build immutable provider calls; the caller payload cannot select a model or effort."""
    _require(isinstance(value, dict), "request must be an object")
    policy = _resolved_policy(value)
    request_id = value["request_id"]
    _require(isinstance(request_id, str) and 1 <= len(request_id) <= 128, "invalid request_id")
    route_id = policy["route_id"]
    _require(candidate_model in CANDIDATES, "unverified Core candidate")
    _require(callable(token_counter), "trusted token counter missing")
    messages = _messages(value["messages"])
    route_limit = policy.get("maximum_output_tokens", CORE_ROUTE_LIMITS.get(route_id))
    _require(isinstance(route_limit, int) and route_limit > 0, "route output limit missing")
    operations = []
    stages = _stages(policy)
    for offset, (kind, index) in enumerate(stages):
        stage_id = f"{kind}-{index}"
        is_final = offset == len(stages) - 1
        dependencies = [operation["stage_id"] for operation in operations]
        maximum_output_tokens = _stage_output_limit(kind, route_limit, is_final)
        first_artifact_message_index = 3 + len(messages)
        artifact_bindings = [
            {
                "source_stage_id": dependency,
                "placeholder": f"{{{{server_stage_output:{dependency}}}}}",
                "trust": "server_generated_private_stage_output",
                "target_message_index": first_artifact_message_index + dependency_index,
                "target_field": "content",
                "replace_exact_target_only": True,
            }
            for dependency_index, dependency in enumerate(dependencies)
        ]
        provider_messages = [
            {"role": "system", "content": IDENTITY},
            {"role": "system", "content": policy["behavior_instruction"]},
            {"role": "system", "content": STAGE_INSTRUCTIONS[kind]},
            *messages,
            *[_artifact_message(dependency) for dependency in dependencies],
        ]
        template_input_tokens = token_counter(candidate_model, provider_messages)
        _require(
            isinstance(template_input_tokens, int) and not isinstance(template_input_tokens, bool) and template_input_tokens > 0,
            "invalid trusted token count",
        )
        reserved_prior_artifact_tokens = sum(operation["maximum_output_tokens"] for operation in operations)
        maximum_input_tokens = template_input_tokens + reserved_prior_artifact_tokens
        _require(
            maximum_input_tokens + maximum_output_tokens <= CANDIDATES[candidate_model]["context_tokens"],
            "request exceeds candidate context",
        )
        operations.append({
            "stage_id": stage_id,
            "phase": kind,
            "public_response": is_final,
            "depends_on_stage_ids": dependencies,
            "input_context": "conversation" if not operations else "conversation_plus_prior_private_artifacts",
            "template_input_tokens": template_input_tokens,
            "reserved_prior_artifact_tokens": reserved_prior_artifact_tokens,
            "maximum_input_tokens": maximum_input_tokens,
            "maximum_output_tokens": maximum_output_tokens,
            "activity_event_allowed_after_start": policy["activity_updates"],
            "request_template": {
                "model": candidate_model,
                "model_revision": CANDIDATES[candidate_model]["revision"],
                "messages": provider_messages,
                "artifact_bindings": artifact_bindings,
                "reject_placeholder_outside_binding_targets": True,
                "reject_unbound_artifacts": True,
                "recount_bound_messages_with_trusted_tokenizer": True,
                "maximum_bound_input_tokens": maximum_input_tokens,
                "reject_if_bound_input_exceeds_maximum": True,
                "reasoning_effort": policy["reasoning_effort"],
                "chat_template_kwargs": {
                    "enable_thinking": policy["thinking_enabled"],
                    "preserve_thinking": False,
                },
                "max_completion_tokens": maximum_output_tokens,
                "stream": is_final,
                "stream_options": {"include_usage": True},
                "store": False,
                "metadata": {"request_id": request_id, "route_id": route_id, "stage_id": stage_id},
            },
        })
    return {
        "request_id": request_id,
        "route_id": route_id,
        "display_name": policy["display_name"],
        "engine": "kova-core",
        "provider": "runpod_serverless",
        "endpoint_name": CORE_SERVING["endpoint_name_reserved"],
        "candidate_model": candidate_model,
        "candidate_revision": CANDIDATES[candidate_model]["revision"],
        "candidate_quantization": CANDIDATES[candidate_model]["quantization"],
        "behavior_contract_id": policy["behavior_contract_id"],
        "production_ready": False,
        "endpoint_deployed": False,
        "executor_contract": {
            "artifact_sources": "server_generated_stage_outputs_only",
            "bind_before_provider_request": True,
            "binding_scope": "exact_server_created_message_target_only",
            "trusted_token_recount_after_binding": True,
            "reject_if_bound_input_exceeds_reserved_or_context": True,
        },
        "operations": operations,
    }
