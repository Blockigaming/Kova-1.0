"""Create bounded Ultra plans; this module never launches agents or paid compute."""

DOMAIN_SPECIALISTS = {
    "coding": ("planner", "implementation", "security", "test", "performance"),
    "research": ("source_finder", "evidence_analyst", "counterargument", "fact_checker", "domain_reviewer"),
    "math": ("solver_a", "solver_b", "verification"),
    "business": ("market", "cost", "risk", "strategy", "operations"),
    "work": ("researcher", "planner", "browser", "document", "data_analyst"),
    "general": ("planner", "domain_specialist", "critic"),
}
DOMAIN_TERMS = {
    "coding": ("code", "debug", "software", "api", "architecture", "database", "security"),
    "research": ("research", "sources", "evidence", "competitors", "fact check"),
    "math": ("math", "calculate", "prove", "equation", "probability"),
    "business": ("business", "market", "pricing", "launch", "revenue", "cost"),
    "work": ("document", "spreadsheet", "browser", "report", "presentation", "project"),
}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _domains(task):
    lowered = task.lower()
    scores = {
        domain: sum(1 for term in terms if term in lowered)
        for domain, terms in DOMAIN_TERMS.items()
    }
    selected = [domain for domain, score in sorted(scores.items(), key=lambda item: (-item[1], item[0])) if score > 0]
    return selected or ["general"]


def _validate_admission(admission):
    _require(isinstance(admission, dict), "trusted Ultra admission missing")
    expected = {"entitlement", "ultra_authorized", "remaining_usd", "estimated_max_usd", "max_agents", "max_total_tokens"}
    _require(set(admission) == expected, "invalid Ultra admission")
    _require(admission["entitlement"] == "pro", "Ultra requires Pro entitlement")
    _require(admission["ultra_authorized"] is True, "Ultra execution is not authorized")
    for field in ("remaining_usd", "estimated_max_usd"):
        value = admission[field]
        _require(isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0, f"invalid {field}")
    _require(admission["estimated_max_usd"] > 0, "invalid estimated_max_usd")
    _require(admission["remaining_usd"] >= admission["estimated_max_usd"], "Ultra request budget exceeded")
    _require(isinstance(admission["max_agents"], int) and not isinstance(admission["max_agents"], bool), "invalid max_agents")
    _require(2 <= admission["max_agents"] <= 5, "max_agents must be between 2 and 5")
    _require(isinstance(admission["max_total_tokens"], int) and not isinstance(admission["max_total_tokens"], bool), "invalid max_total_tokens")
    _require(4096 <= admission["max_total_tokens"] <= 131072, "max_total_tokens outside safe range")


def _select_specialists(domains, maximum):
    specialists = []
    for domain in domains:
        for role in DOMAIN_SPECIALISTS[domain]:
            item = f"{domain}:{role}"
            if item not in specialists:
                specialists.append(item)
            if len(specialists) == maximum:
                return specialists
    fallback = DOMAIN_SPECIALISTS["general"]
    for role in fallback:
        item = f"general:{role}"
        if item not in specialists:
            specialists.append(item)
        if len(specialists) == maximum:
            break
    return specialists


def build_ultra_plan(request, *, admission):
    """Return a bounded DAG description without executing any operation."""
    _require(isinstance(request, dict) and set(request) == {"request_id", "task"}, "Ultra request contains unsupported fields")
    request_id = request["request_id"]
    task = request["task"]
    _require(isinstance(request_id, str) and 1 <= len(request_id) <= 128, "invalid request_id")
    _require(isinstance(task, str) and task.strip(), "task must be nonempty text")
    _require(len(task) <= 250_000, "task too large")
    _validate_admission(admission)
    domains = _domains(task)
    requested_agents = min(admission["max_agents"], max(2, len(domains) + 2))
    specialists = _select_specialists(domains, requested_agents)
    per_operation_tokens = admission["max_total_tokens"] // (len(specialists) + 3)
    _require(per_operation_tokens >= 512, "Ultra token budget too small for bounded plan")

    specialist_operations = [
        {
            "id": f"specialist-{index + 1}",
            "role": role,
            "parallel_group": "specialists",
            "depends_on": [],
            "maximum_output_tokens": per_operation_tokens,
            "public_output": False,
            "activity_event_allowed_after_start": True,
        }
        for index, role in enumerate(specialists)
    ]
    specialist_ids = [operation["id"] for operation in specialist_operations]
    judge = {
        "id": "judge",
        "role": "disagreement_and_evidence_judge",
        "depends_on": specialist_ids,
        "maximum_output_tokens": per_operation_tokens,
        "public_output": False,
        "activity_event_allowed_after_start": True,
    }
    debate = {
        "id": "debate-round-1",
        "role": "targeted_challenge",
        "depends_on": ["judge"],
        "condition": "judge_detected_material_disagreement",
        "maximum_rounds": 1,
        "maximum_output_tokens": per_operation_tokens,
        "public_output": False,
        "activity_event_allowed_after_start": True,
    }
    synthesis = {
        "id": "synthesis",
        "role": "final_kova_synthesizer",
        "depends_on": ["judge", "debate-round-1_if_executed"],
        "maximum_output_tokens": per_operation_tokens,
        "public_output": True,
        "activity_event_allowed_after_start": True,
    }
    return {
        "request_id": request_id,
        "engine": "kova-ultra",
        "provider": "runpod_serverless",
        "domains": domains,
        "model_selection_required": True,
        "production_ready": False,
        "estimated_max_usd": admission["estimated_max_usd"],
        "operations": [*specialist_operations, judge, debate, synthesis],
    }
