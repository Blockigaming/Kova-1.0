"""Validate the newest owner-approved model topology without pretending it is live.

This module records source truth for current packaging/model identity. It deliberately
reports unresolved runtime alignment instead of guessing upstream models, quota sizes,
reset timing, replenishment pricing, or deployed route identity.
"""

import json
from pathlib import Path

from router.policy import CHAT_POLICIES, WORK_EFFORTS, WORK_FAMILY_POLICIES

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config/current-product-policy.v2.json"


class CurrentPolicyError(ValueError):
    pass


def need(condition):
    if not condition:
        raise CurrentPolicyError("current product policy rejected")


def load_policy():
    try:
        value = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise CurrentPolicyError("current product policy rejected") from None
    need(type(value) is dict)
    need(value.get("schema_version") == 2)
    need(value.get("status") == "owner_approved_source_policy_not_runtime_integrated")
    need(value.get("provenance") == {
        "repository": "Blockigaming/KovaGPT_Models",
        "issue": 10,
        "comment_id": 5734534302,
        "approved_on": "2026-09-18",
    })
    return value


def validate():
    value = load_policy()
    chat = value["chat"]
    need(chat["default_route_id"] == "instant" and chat["default_label"] == "Lite")
    need(chat["shared_model_slot"] == "chat-shared")
    need(chat["same_underlying_model_across_efforts"] is True)
    need(chat["free"] == {"selectable": False, "routes": ["instant"]})
    need(chat["plus"]["routes"] == ["instant", "medium", "high"])
    need(chat["plus"]["labels"] == {"instant": "Lite", "medium": "Medium", "high": "Thinking"})
    need(chat["pro"]["routes"] == ["instant", "medium", "high", "extra-high", "max", "ultra"])
    need(chat["pro"]["labels"] == {
        "instant": "Lite", "medium": "Medium", "high": "High",
        "extra-high": "Extra High", "max": "Max", "ultra": "Ultra",
    })
    need(chat["ultra"] == {
        "engine": "kova-ultra", "minimum_agents": 2, "maximum_agents": 5,
        "uses_same_model_slot": True,
    })
    need(chat["paid_chat_uses_work_weekly_allowance"] is False)

    work = value["work"]
    need(work["default_effort_id"] == "light" and work["default_label"] == "Lite")
    need(work["same_family_model_across_efforts"] is True)
    need(work["family_model_slots_must_be_distinct"] is True)
    families = work["families"]
    need(set(families) == {"cosmo", "orion", "nova"})
    slots = [families[name]["model_slot"] for name in ("cosmo", "orion", "nova")]
    need(len(set(slots)) == 3)
    need(work["entitlements"] == {"free": [], "plus": "all_18", "pro": "all_18"})

    expected_efforts = {
        "light": ("Lite", [0, 1, 0, 0], 2048, "kova-core"),
        "medium": ("Medium", [1, 1, 0, 1], 4096, "kova-core"),
        "high": ("High", [1, 2, 1, 1], 8192, "kova-core"),
        "extra-high": ("Extra High", [2, 3, 2, 2], 16384, "kova-core"),
        "max": ("Max", [2, 4, 2, 3], 24576, "kova-core"),
    }
    for effort, expected in expected_efforts.items():
        item = work["efforts"][effort]
        need((item["label"], item["passes"], item["maximum_output_tokens"], item["engine"]) == expected)
    ultra = work["efforts"]["ultra"]
    need(ultra == {
        "label": "Ultra", "passes": None, "maximum_output_tokens": 32768,
        "engine": "kova-ultra", "minimum_agents": 2, "maximum_agents": 5,
        "uses_same_family_model_slot": True,
    })

    usage = value["work_usage"]
    need(usage["period"] == "weekly")
    need(usage["plus_base_units"] is None and usage["reset_anchor"] is None)
    need(usage["pro_multiplier"] == 5)
    need(usage["paid_replenishment_allowed"] is True)
    need(usage["replenishment_units"] is None and usage["replenishment_price_usd"] is None)
    need(usage["chat_remains_available_when_exhausted"] is True)

    model_slots = value["model_slots"]
    need(set(model_slots) == {"chat-shared", "work-cosmo", "work-orion", "work-nova"})
    need(all(item == {"upstream_model": None, "upstream_revision": None} for item in model_slots.values()))

    # Compare newest source policy with the currently published runtime policy.
    runtime_chat_profiles = {route: CHAT_POLICIES[route].get("profile") for route in CHAT_POLICIES}
    chat_runtime_aligned = len(set(runtime_chat_profiles.values())) == 1 and set(runtime_chat_profiles) == set(chat["pro"]["routes"])

    runtime_work_families_are_model_slots = all(
        "model_slot" in WORK_FAMILY_POLICIES[family] for family in ("cosmo", "orion", "nova")
    )
    runtime_efforts_match = True
    name_map = {
        "light": "Light", "medium": "Medium", "high": "High",
        "extra-high": "Extra High", "max": "Max", "ultra": "Ultra",
    }
    for effort_id, source_name in name_map.items():
        current = WORK_EFFORTS[source_name]
        declared = work["efforts"][effort_id]
        if declared["maximum_output_tokens"] != current["maximum_output_tokens"]:
            runtime_efforts_match = False
        if effort_id != "ultra" and tuple(declared["passes"]) != tuple(current["passes"]):
            runtime_efforts_match = False

    return {
        "schema_version": 2,
        "status": "current_policy_valid_runtime_integration_pending",
        "owner_comment_id": 5734534302,
        "chat_shared_model_policy_valid": True,
        "work_three_distinct_model_slots_policy_valid": True,
        "work_effort_contracts_match_current_compute": runtime_efforts_match,
        "runtime_chat_model_identity_aligned": chat_runtime_aligned,
        "runtime_work_model_identity_aligned": runtime_work_families_are_model_slots,
        "missing_upstream_model_slots": [
            name for name, item in model_slots.items() if item["upstream_model"] is None
        ],
        "missing_plus_weekly_units": usage["plus_base_units"] is None,
        "missing_reset_anchor": usage["reset_anchor"] is None,
        "missing_replenishment_terms": (
            usage["replenishment_units"] is None or usage["replenishment_price_usd"] is None
        ),
        "closed_checklist_ids": [],
        "phase_b_ready": False,
    }


if __name__ == "__main__":
    print(json.dumps(validate(), sort_keys=True))
