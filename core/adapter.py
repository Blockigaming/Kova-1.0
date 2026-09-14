"""Build Cloudflare Workers AI plans without performing network requests."""

import json
from pathlib import Path

from router.policy import CHAT_POLICIES


ROOT = Path(__file__).resolve().parents[1]
IDENTITY = json.loads((ROOT / "config" / "identity.v1.json").read_text(encoding="utf-8"))["system_identity"]
ARCHITECTURE = json.loads((ROOT / "config" / "provider-architecture.v1.json").read_text(encoding="utf-8"))
CORE_CONFIG = next(engine for engine in ARCHITECTURE["engines"] if engine["id"] == "kova-core")
CANDIDATES = {candidate["model"]: candidate for candidate in CORE_CONFIG["candidate_models"]}
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


def build_core_plan(value, *, candidate_model, token_counter):
    """Build immutable provider calls; the caller payload cannot select a model or effort."""
    _require(isinstance(value, dict), "request must be an object")
    _require(set(value) == {"request_id", "messages", "route_id"}, "request contains unsupported or server-controlled fields")
    request_id = value["request_id"]
    _require(isinstance(request_id, str) and 1 <= len(request_id) <= 128, "invalid request_id")
    route_id = value["route_id"]
    _require(route_id in CORE_ROUTE_LIMITS, "route is not eligible for Kova Core")
    _require(candidate_model in CANDIDATES, "unverified Core candidate")
    _require(callable(token_counter), "trusted token counter missing")
    messages = _messages(value["messages"])
    policy = CHAT_POLICIES[route_id]
    operations = []
    stages = _stages(policy)
    for offset, (kind, index) in enumerate(stages):
        stage_id = f"{kind}-{index}"
        is_final = offset == len(stages) - 1
        provider_messages = [
            {"role": "system", "content": IDENTITY},
            {"role": "system", "content": STAGE_INSTRUCTIONS[kind]},
            *messages,
        ]
        input_tokens = token_counter(candidate_model, provider_messages)
        _require(isinstance(input_tokens, int) and not isinstance(input_tokens, bool) and input_tokens > 0, "invalid trusted token count")
        _require(input_tokens + CORE_ROUTE_LIMITS[route_id] <= CANDIDATES[candidate_model]["context_tokens"], "request exceeds candidate context")
        operations.append({
            "stage_id": stage_id,
            "phase": kind,
            "public_response": is_final,
            "depends_on_stage_ids": [operation["stage_id"] for operation in operations],
            "input_context": "conversation" if not operations else "conversation_plus_prior_private_artifacts",
            "input_tokens": input_tokens,
            "activity_event_allowed_after_start": policy["activity_updates"],
            "request": {
                "model": candidate_model,
                "messages": provider_messages,
                "reasoning_effort": policy["reasoning_effort"],
                "max_completion_tokens": CORE_ROUTE_LIMITS[route_id],
                "stream": is_final,
                "store": False,
                "metadata": {"request_id": request_id, "route_id": route_id, "stage_id": stage_id},
            },
        })
    return {
        "request_id": request_id,
        "route_id": route_id,
        "engine": "kova-core",
        "provider": "cloudflare_workers_ai",
        "candidate_model": candidate_model,
        "production_ready": False,
        "operations": operations,
    }
