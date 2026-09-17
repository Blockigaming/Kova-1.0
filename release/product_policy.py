"""Validate the owner-approved A36/A37 source policy without enabling production.

This validator proves that the approved source decisions match the routing and
admission contracts. It performs no authentication, network, model, cloud, tool,
or deployment action and does not imply Phase B readiness.
"""

import json
from pathlib import Path
import sys

from execution.contracts import CHAT_ALLOWED, ExecutionLimits
from router.entitlements import (
    ALL_WORK_ROUTES, FREE_THINKING_MODE_ID, FREE_THINKING_ROUTE,
    PLUS_WORK_ROUTES, PRODUCT_POLICY, WORK_ALLOWED_BY_TIER,
)
from router.policy import CHAT_POLICIES, WORK_EFFORTS


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config/product-policy.v1.json"


class ProductPolicyError(ValueError):
    pass


def need(condition):
    if not condition:
        raise ProductPolicyError("approved product policy rejected")


def validate_checked_in():
    try:
        value = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise ProductPolicyError("approved product policy rejected") from None
    need(value == PRODUCT_POLICY)
    need(value["provenance"] == {
        "repository": "Blockigaming/Kova-1.0",
        "issue": 10,
        "comment_id": 5718592571,
        "approved_on": "2026-09-17",
    })

    # A36: visible Free Thinking is a controlled alias, not direct Free Medium.
    need(FREE_THINKING_MODE_ID == "thinking" and FREE_THINKING_ROUTE == "medium")
    need(value["free_thinking"]["direct_free_medium_allowed"] is False)
    need(CHAT_ALLOWED["free"] == frozenset(("instant",)))
    need(CHAT_ALLOWED["plus"] == frozenset(("instant", "medium", "high")))
    need(CHAT_ALLOWED["pro"] == frozenset(CHAT_POLICIES))
    need(WORK_ALLOWED_BY_TIER["free"] == frozenset())
    need(WORK_ALLOWED_BY_TIER["plus"] == PLUS_WORK_ROUTES and len(PLUS_WORK_ROUTES) == 9)
    need(WORK_ALLOWED_BY_TIER["pro"] == ALL_WORK_ROUTES and len(ALL_WORK_ROUTES) == 18)

    # A37: timing clocks remain distinct and no fabricated completion/global max
    # is introduced. The real execution contract still requires finite per-job
    # admission bounds whenever an execution is actually admitted.
    timing = value["timing"]
    ttft = timing["cosmo_warm_first_visible_answer_token"]
    need(ttft == {"ideal_reference_ms": [1000, 3000], "faster_allowed": True,
                  "hard_limit": False, "measured_on_azure": False})
    need(timing["completed_answer"] == {
        "policy": "no_fixed_product_target",
        "applies_to_all_routes": True,
        "separate_cold_warm_sla_created": False,
    })
    need(timing["maximum_active_execution"] == {
        "policy": "finite_server_budget_per_job_no_global_duration",
        "fixed_product_maximum_ms": None,
        "finite_job_deadline_required": True,
        "restart_renews_deadline": False,
        "client_can_widen_limits": False,
    })
    budget = value["budget_policy"]
    need(budget == {
        "route_output_token_caps_preserved": True,
        "finite_job_token_limit_required": True,
        "finite_job_cost_limit_required": True,
        "bounded_parallelism_required": True,
        "bounded_stage_timeout_required": True,
        "client_budget_override_allowed": False,
        "fixed_dollar_promise_created": False,
    })
    # Exercise the same finite bounds used by execution source; this is not a
    # selected production duration or dollar budget.
    sample = ExecutionLimits(deadline_unix_ms=1, token_limit=1,
                             cost_limit_microusd=1, max_parallel=1,
                             stage_timeout_seconds=1)
    need(sample.deadline_unix_ms == 1 and sample.token_limit == 1
         and sample.cost_limit_microusd == 1 and sample.max_parallel == 1)

    semantics = value["extra_high_semantics"]
    need(semantics["chat_passes"] == list(CHAT_POLICIES["extra-high"]["passes"]) == [2, 2, 2, 2])
    need(semantics["work_passes"] == list(WORK_EFFORTS["Extra High"]["passes"]) == [2, 3, 2, 2])
    need(semantics["historical_reasoning_range"] == [4, 6])
    need(semantics["historical_reasoning_range_is_execution_pass_count"] is False)

    return {
        "schema_version": 1,
        "status": "approved_product_policy_source_valid",
        "owner_decision_comment_id": 5718592571,
        "free_thinking_route": FREE_THINKING_ROUTE,
        "work_routes_by_tier": {tier: len(routes) for tier, routes in WORK_ALLOWED_BY_TIER.items()},
        "completed_answer_fixed_target": False,
        "global_active_execution_duration": False,
        "finite_server_job_budget_required": True,
        "closed_checklist_ids": ["A36", "A37"],
        "phase_a_total": 40,
        "product_policy_ready": True,
        "phase_b_ready": False,
    }


def main(args=None):
    args = sys.argv[1:] if args is None else args
    try:
        need(args in ([], ["--require-ready"]))
        report = validate_checked_in()
        print(json.dumps(report, sort_keys=True))
        return 0
    except (ProductPolicyError, RuntimeError, OSError, ValueError, TypeError, KeyError):
        print("approved product policy rejected", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
