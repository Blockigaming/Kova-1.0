"""Owner-approved source entitlements for Kova Chat aliases and Work routes.

This module is authorization policy only. It does not authenticate callers, enable
execution, deploy a model, or grant a route unless the server also supplies that
exact route in an ExecutionGrant.
"""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config/product-policy.v1.json"
TIERS = ("free", "plus", "pro")
FAMILIES = ("cosmo", "orion", "nova")
EFFORT_IDS = ("light", "medium", "high", "extra-high", "max", "ultra")
ALL_WORK_ROUTES = frozenset(
    f"work:{family}:{effort}" for family in FAMILIES for effort in EFFORT_IDS
)
PLUS_WORK_ROUTES = frozenset(
    f"work:{family}:{effort}" for family in FAMILIES for effort in ("light", "medium", "high")
)
EXPECTED_WORK = {
    "free": frozenset(),
    "plus": PLUS_WORK_ROUTES,
    "pro": ALL_WORK_ROUTES,
}


def _require(condition, message="invalid approved product policy"):
    if not condition:
        raise RuntimeError(message)


def _load_policy():
    try:
        value = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise RuntimeError("invalid approved product policy") from None
    _require(type(value) is dict and set(value) == {
        "schema_version", "status", "provenance", "free_thinking",
        "work_entitlements", "timing", "budget_policy", "extra_high_semantics",
    })
    _require(value["schema_version"] == 1 and value["status"] == "owner_approved_source_policy")
    provenance = value["provenance"]
    _require(type(provenance) is dict and provenance == {
        "repository": "Blockigaming/Kova-1.0",
        "issue": 10,
        "comment_id": 5718592571,
        "approved_on": "2026-09-17",
    })
    thinking = value["free_thinking"]
    _require(type(thinking) is dict and thinking == {
        "application_mode_id": "thinking",
        "route_id": "medium",
        "display_route": "Kova 5.6 Orion",
        "direct_free_medium_allowed": False,
    })
    work = value["work_entitlements"]
    _require(type(work) is dict and set(work) == set(TIERS))
    normalized = {}
    for tier in TIERS:
        routes = work[tier]
        _require(type(routes) is list and len(routes) == len(set(routes)))
        route_set = frozenset(routes)
        _require(route_set == EXPECTED_WORK[tier])
        normalized[tier] = route_set
    return value, normalized


PRODUCT_POLICY, WORK_ALLOWED_BY_TIER = _load_policy()
FREE_THINKING_MODE_ID = PRODUCT_POLICY["free_thinking"]["application_mode_id"]
FREE_THINKING_ROUTE = PRODUCT_POLICY["free_thinking"]["route_id"]
