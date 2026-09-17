"""Review preparation for unresolved A36/A37 decisions, never runtime policy.

No function authenticates an owner, issues an ExecutionGrant, modifies routing,
chooses missing targets or closes a checklist gate. Even a fully populated valid
proposal remains unapproved. Current checked-in decisions must remain null.
"""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

from evaluation.offline import build_route_manifest
from router.policy import CHAT_POLICIES

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 512 * 1024
MAX_NODES = 12000
TIERS = ("free", "plus", "pro")
CONDITIONS = ("cold", "warm")
PROTECTED_PATHS = (
    "config/application-bridge.v1.json", "config/route-policy.v1.json",
    "config/identity.v1.json", "config/product-surface.v1.json",
)
# This is a source snapshot, not an assertion about a currently deployed app.
SOURCE_COMMIT = "38a1a020029c9c007652a554592f0a197e7b8dfb"
SOURCE_HASHES = {'config/application-bridge.v1.json': '7abd602f7bb46ef4897dd9f199353c08a6a92734012d079f66df1cf300835bdf', 'config/route-policy.v1.json': 'a2d41563af0eaf9f9b77a22e9f6d1e16b2e902cac16eb638960e8196530b3c5a', 'config/identity.v1.json': '279e97f249a845c6594699c551335ea7716fd297dc94ad7b99ee1313c3acd876', 'config/product-surface.v1.json': 'b1ce1964dc1d82900dd97632b06a14d51c0acb993f48339ee4af9108bffc8ce4'}
LEGACY_CHAT = {
    "free": ["instant", "thinking"],
    "plus": ["instant", "medium", "high"],
    "pro": ["instant", "medium", "high", "extra_high", "max", "ultra"],
}


class DecisionRejected(ValueError):
    """Sanitized malformed proposal or source-contract failure."""


def need(condition):
    if not condition:
        raise DecisionRejected("product decision document rejected")


def fields(value, names):
    need(type(value) is dict and set(value) == set(names))


def text(value):
    need(type(value) is str and 0 < len(value.strip()) <= 4096)
    try:
        value.encode("utf-8")
    except UnicodeError:
        raise DecisionRejected("product decision document rejected") from None


def positive_ms(value):
    # A parser limit, not a selected product execution duration or latency.
    need(type(value) is int and 0 < value <= 2**53 - 1)


def finite_document(value):
    """Bound nesting/nodes before recursive JSON canonicalization."""
    pending, count = [(value, 0)], 0
    while pending:
        item, depth = pending.pop()
        count += 1
        need(count <= MAX_NODES and depth <= 16)
        if type(item) is dict:
            need(all(type(key) is str for key in item))
            pending.extend((v, depth + 1) for v in item.values())
        elif type(item) is list:
            pending.extend((v, depth + 1) for v in item)
        else:
            need(item is None or type(item) in (str, int, bool))
    try:
        encoded = json.dumps(value, sort_keys=True, ensure_ascii=False,
                             allow_nan=False, separators=(",", ":")).encode("utf-8")
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise DecisionRejected("product decision document rejected") from None
    need(len(encoded) <= MAX_BYTES)
    return encoded


def document_digest(value):
    return hashlib.sha256(finite_document(value)).hexdigest()


def parse_document(raw):
    need(type(raw) is bytes and 0 < len(raw) <= MAX_BYTES)
    def pairs(entries):
        result = {}
        for key, value in entries:
            need(key not in result)
            result[key] = value
        return result
    def reject_number(_):
        raise DecisionRejected("product decision document rejected")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                           parse_constant=reject_number, parse_float=reject_number)
        finite_document(value)
        return value
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise DecisionRejected("product decision document rejected") from None


def source_contract():
    """Build the exact pending-decision template from protected source names."""
    routes = [r["route_id"] for r in build_route_manifest()]
    need(len(routes) == 25 and len(set(routes)) == 25)
    work = [r for r in routes if r.startswith("work:")]
    need(len(work) == 18)
    return {
        "schema_version": 1,
        "document_kind": "unapproved_product_proposal",
        "phase_a": {"rubric": "Phase A fixed v1", "total": 40, "items": ["A36", "A37"]},
        "source": {"repository": "Blockigaming/Kova-1.0", "commit": SOURCE_COMMIT,
                   "sha256_by_path": dict(SOURCE_HASHES)},
        "preserved": {
            "application_chat_modes": deepcopy(LEGACY_CHAT),
            "ultra_requires_pro": True,
            "cosmo_goal": {"route_id": "instant", "condition": "warm",
                "metric": "first_visible_answer_token", "ideal_reference_ms": [1000, 3000],
                "faster_allowed": True, "measured_on_azure": False, "hard_limit": False},
            "extra_high": {"current_chat_passes": [2, 2, 2, 2],
                "historical_concept": {"planning": 2, "reasoning_range": [4, 6],
                                       "critic": 2, "verification": 2}},
            "clocks": ["genuine_acknowledgement", "first_visible_answer_token",
                       "completed_answer", "maximum_active_execution"],
            "fixture_timeouts_are_product_requirements": False,
        },
        "decisions": {
            "free_thinking": None,
            # Pro is necessary for Ultra, not sufficient proof that it is granted.
            "work_tiers": {tier: {route: None for route in work} for tier in TIERS},
            "completed_answer_targets": {route: {c: None for c in CONDITIONS} for route in routes},
            "maximum_active_execution": {route: None for route in routes},
            "extra_high_semantics": None,
        },
    }


def validate_proposal(value):
    """Validate an unapproved proposal without promoting it to a decision.

    A resolved field is a proposal entry, not evidence of owner consent. Complete
    proposals still need explicit decisions, source implementation, integration
    tests and independent review. No editable approval/status field is accepted.
    """
    finite_document(value)
    template = source_contract()
    fields(value, template)
    # Equality alone would accept 1 for True; canonical typed JSON does not.
    for name in set(template) - {"decisions"}:
        need(finite_document(value[name]) == finite_document(template[name]))
    proposed, expected = value["decisions"], template["decisions"]
    fields(proposed, expected)
    missing = []
    mapping = proposed["free_thinking"]
    if mapping is None:
        missing.append("decisions.free_thinking")
    else:
        fields(mapping, ("handling", "route_id", "rationale"))
        text(mapping["rationale"])
        if mapping["handling"] == "retain_legacy_only":
            need(mapping["route_id"] is None)
        else:
            need(mapping["handling"] == "custom_chat_route")
            need(type(mapping["route_id"]) is str and mapping["route_id"] in CHAT_POLICIES)
            # A proposal cannot silently contradict the preserved Pro-only rule.
            need(mapping["route_id"] != "ultra")

    fields(proposed["work_tiers"], TIERS)
    for tier in TIERS:
        fields(proposed["work_tiers"][tier], expected["work_tiers"][tier])
        for route, allow in proposed["work_tiers"][tier].items():
            need(allow is None or type(allow) is bool)
            if allow is None:
                missing.append(f"decisions.work_tiers.{tier}.{route}")
            need(not (allow is True and tier != "pro" and route.endswith(":ultra")))

    fields(proposed["completed_answer_targets"], expected["completed_answer_targets"])
    for route, conditions in proposed["completed_answer_targets"].items():
        fields(conditions, CONDITIONS)
        for condition, target in conditions.items():
            if target is None:
                missing.append(f"decisions.completed_answer_targets.{route}.{condition}")
                continue
            fields(target, ("kind", "milliseconds", "statistic", "rationale"))
            text(target["rationale"])
            if target["kind"] == "no_fixed_target":
                need(target["milliseconds"] is None and target["statistic"] is None)
            else:
                need(target["kind"] == "target")
                positive_ms(target["milliseconds"])
                need(target["statistic"] in ("mean", "median", "p95"))
            # No comparison with acknowledgement or the Cosmo TTFT goal: these
            # are distinct clocks and no artificial minimum delay is inferred.

    fields(proposed["maximum_active_execution"], expected["maximum_active_execution"])
    for route, limit in proposed["maximum_active_execution"].items():
        if limit is None:
            missing.append(f"decisions.maximum_active_execution.{route}")
            continue
        fields(limit, ("maximum_ms", "measurement_definition"))
        positive_ms(limit["maximum_ms"])
        text(limit["measurement_definition"])
        # Free text is preserved for human review, not executed as a clock policy.
        # A finite value alone does not implement active-time metering, queue or
        # pause semantics, nor replace the existing wall-clock ExecutionLimits.

    semantics = proposed["extra_high_semantics"]
    if semantics is None:
        missing.append("decisions.extra_high_semantics")
    else:
        text(semantics)
    return {
        "schema_version": 1, "status": "proposal_valid_but_unapproved",
        "document_sha256": document_digest(value),
        "routes": 25, "work_combinations": 18, "work_tier_cells": 54,
        "missing_field_count": len(missing), "missing_fields": missing,
        "proposal_fully_populated": not missing,
        "owner_approval_verified": False, "runtime_policy_changed": False,
        "closed_checklist_ids": [], "phase_a_total": 40, "phase_b_ready": False,
        "blockers": ["owner_decisions_unapproved", "runtime_integration_not_performed",
                     "independent_review_not_performed"],
    }


def validate_checked_in():
    """Verify protected source bytes and the still-unresolved checked-in record."""
    need(set(SOURCE_HASHES) == set(PROTECTED_PATHS))
    for path, expected in SOURCE_HASHES.items():
        need(hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == expected)
    bridge = parse_document((ROOT / PROTECTED_PATHS[0]).read_bytes())
    need(bridge["application_chat_modes"] == LEGACY_CHAT)
    route = parse_document((ROOT / "config/route-policy.v1.json").read_bytes())
    extra_high = next(r for r in route["chat"] if r["id"] == "extra-high")
    need([extra_high[k] for k in ("planning_passes", "answer_passes", "critic_passes", "verification_passes")] == [2, 2, 2, 2])
    need(list(CHAT_POLICIES["extra-high"]["passes"]) == [2, 2, 2, 2])
    value = parse_document((ROOT / "config/product-decisions.v1.json").read_bytes())
    # Current source accepts no selected values; proposals are separate inputs.
    need(finite_document(value) == finite_document(source_contract()))
    report = validate_proposal(value)
    report["status"] = "pending_decision_source_valid_not_ready"
    return report


def main(args=None):
    args = sys.argv[1:] if args is None else args
    try:
        need(args in ([], ["--require-ready"]) or
             (len(args) == 2 and args[0] == "--proposal"))
        report = validate_checked_in()
        if len(args) == 2:
            with open(args[1], "rb") as stream:
                raw = stream.read(MAX_BYTES + 1)
            report = validate_proposal(parse_document(raw))
        print(json.dumps(report, sort_keys=True))
        # This is an explicit blocker result, not a failed test or CI workaround.
        return 78 if args == ["--require-ready"] else 0
    except (DecisionRejected, OSError, ValueError, TypeError, KeyError, StopIteration):
        print("product decision document rejected", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
