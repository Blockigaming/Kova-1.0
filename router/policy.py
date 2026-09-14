"""Resolve public Kova modes to immutable server-controlled compute policies."""

from copy import deepcopy


FORBIDDEN_FIELDS = frozenset((
    "model", "provider", "engine", "reasoning_effort", "planning_passes",
    "answer_passes", "critic_passes", "verification_passes", "dynamic_agent_maximum",
))

CHAT_POLICIES = {
    "instant": {"engine": "kova-core", "profile": "cosmo", "reasoning_effort": "low", "passes": (0, 1, 0, 0), "activity_updates": False},
    "medium": {"engine": "kova-core", "profile": "orion", "reasoning_effort": "medium", "passes": (1, 1, 0, 1), "activity_updates": False},
    "high": {"engine": "kova-core", "profile": "nova", "reasoning_effort": "high", "passes": (1, 1, 1, 1), "activity_updates": True},
    "extra-high": {"engine": "kova-core", "profile": "nova", "reasoning_effort": "high", "passes": (2, 2, 2, 2), "activity_updates": True},
    "max": {"engine": "kova-core", "profile": "nova", "reasoning_effort": "high", "passes": (2, 3, 2, 3), "activity_updates": True},
    "ultra": {"engine": "kova-ultra", "profile": "ultra", "reasoning_effort": "high", "dynamic_agents": (2, 5), "judge": True, "synthesis": True, "activity_updates": True},
}

WORK_FAMILIES = frozenset(("cosmo", "orion", "nova"))
WORK_EFFORTS = {
    "Light": {"reasoning_effort": "low", "passes": (0, 1, 0, 0), "maximum_output_tokens": 2048},
    "Medium": {"reasoning_effort": "medium", "passes": (1, 1, 0, 1), "maximum_output_tokens": 4096},
    "High": {"reasoning_effort": "high", "passes": (1, 2, 1, 1), "maximum_output_tokens": 8192},
    "Extra High": {"reasoning_effort": "high", "passes": (2, 3, 2, 2), "maximum_output_tokens": 16384},
    "Max": {"reasoning_effort": "high", "passes": (2, 4, 2, 3), "maximum_output_tokens": 24576},
    "Ultra": {"reasoning_effort": "high", "dynamic_agents": (2, 5), "maximum_output_tokens": 32768},
}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _reject_policy_overrides(request):
    _require(isinstance(request, dict), "route request must be an object")
    overridden = sorted(FORBIDDEN_FIELDS.intersection(request))
    _require(not overridden, f"server-controlled routing fields: {','.join(overridden)}")


def resolve_route(request):
    """Resolve a Chat or Work route without accepting provider/model overrides."""
    _reject_policy_overrides(request)
    surface = request.get("surface")
    _require(surface in ("chat", "work"), "invalid surface")

    if surface == "chat":
        route_id = request.get("route_id")
        _require(route_id != "kova-auto", "auto classifier is not implemented")
        _require(route_id in CHAT_POLICIES, "invalid chat route")
        return {"surface": "chat", "route_id": route_id, **deepcopy(CHAT_POLICIES[route_id])}

    family = request.get("family")
    effort = request.get("effort")
    _require(family in WORK_FAMILIES, "invalid work family")
    _require(effort in WORK_EFFORTS, "invalid work effort")
    policy = deepcopy(WORK_EFFORTS[effort])
    policy.update({
        "surface": "work",
        "route_id": f"work:{family}:{effort.lower().replace(' ', '-')}",
        "profile": family,
        "engine": "kova-ultra" if effort == "Ultra" else "kova-core",
        "activity_updates": True,
    })
    if effort == "Ultra":
        policy.update({"judge": True, "synthesis": True})
    return policy
