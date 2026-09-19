"""Fail-closed cost and deallocation guard for the bounded Cosmo GPU pilot.

This module validates source policy and operator-supplied control-plane evidence.
It does not call Azure, create resources, download weights, or start training.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path
import re
import sys

from release.model_revisions import MODEL_SOURCE_REFERENCES

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config/kova-cosmo-runtime-guard.v1.json"
EVIDENCE_ENV = "KOVA_COSMO_RUNTIME_EVIDENCE"
MONEY = re.compile(r"(?:0|[1-9][0-9]*)\.[0-9]{4}")
UTC_TIMESTAMP = re.compile(
    r"20[0-9]{2}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])T"
    r"(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]Z"
)
MAX_EVIDENCE_BYTES = 1024 * 1024


class RuntimeGuardError(ValueError):
    pass


def need(condition: bool) -> None:
    if not condition:
        raise RuntimeGuardError("kova cosmo runtime guard rejected")


def unique_object(pairs: list[tuple[str, object]]) -> dict:
    value = {}
    for key, item in pairs:
        need(type(key) is str and key not in value)
        value[key] = item
    return value


def reject_constant(_value: str) -> None:
    raise RuntimeGuardError("kova cosmo runtime guard rejected")


def parse_json(raw: str) -> object:
    return json.loads(
        raw, object_pairs_hook=unique_object, parse_constant=reject_constant
    )


def money(value: object) -> Decimal:
    need(type(value) is str and MONEY.fullmatch(value) is not None)
    try:
        return Decimal(value)
    except InvalidOperation:
        raise RuntimeGuardError("kova cosmo runtime guard rejected") from None


def timestamp(value: object) -> datetime:
    need(type(value) is str and UTC_TIMESTAMP.fullmatch(value) is not None)
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        raise RuntimeGuardError("kova cosmo runtime guard rejected") from None


def nonempty(value: object, maximum: int = 512) -> bool:
    return type(value) is str and 0 < len(value) <= maximum


def load_policy(root: Path = ROOT) -> dict:
    try:
        value = parse_json(
            (root / "config/kova-cosmo-runtime-guard.v1.json").read_text(
                encoding="utf-8"
            )
        )
        need(type(value) is dict and list(value) == [
            "schema_version", "status", "model_slot", "base_model",
            "base_revision", "azure", "pricing", "required_controls",
            "owner_approvals", "runtime_evidence", "phase_b_ready",
        ])
        reference = MODEL_SOURCE_REFERENCES["work-cosmo"]
        need(value["schema_version"] == 1)
        need(value["model_slot"] == reference.slot)
        need(value["base_model"] == reference.model)
        need(value["base_revision"] == reference.revision)
        need(value["azure"] == {
            "region": "eastus",
            "vm_size": "Standard_NC4as_T4_v3",
            "required_family_quota_vcpus": 4,
        })

        pricing = value["pricing"]
        need(type(pricing) is dict and list(pricing) == [
            "owner_verified_compute_usd_per_hour",
            "approved_all_in_budget_usd", "maximum_allocated_minutes",
            "maximum_compute_cost_usd", "minimum_ancillary_reserve_usd",
            "budget_alert_is_hard_stop",
        ])
        hourly = money(pricing["owner_verified_compute_usd_per_hour"])
        budget = money(pricing["approved_all_in_budget_usd"])
        compute = money(pricing["maximum_compute_cost_usd"])
        reserve = money(pricing["minimum_ancillary_reserve_usd"])
        need(hourly == Decimal("0.5260"))
        need(budget == Decimal("2.0000"))
        need(pricing["maximum_allocated_minutes"] == 60)
        need(compute == hourly)
        need(compute + reserve == budget)
        need(pricing["budget_alert_is_hard_stop"] is False)

        need(value["required_controls"] == {
            "control_plane_deallocation_deadline": True,
            "independent_watchdog": True,
            "watchdog_permission_test": True,
            "no_public_ip": True,
            "post_run_power_state_verification": True,
            "post_run_residual_resource_inventory": True,
        })

        approvals = value["owner_approvals"]
        need(type(approvals) is dict and list(approvals) == [
            "budget_approved", "model_download_approved",
            "bounded_training_pilot_approved", "resource_creation_release",
            "spending_release", "deployment_authorized",
        ])
        for key, item in approvals.items():
            need(type(item) is bool)
        need(approvals["budget_approved"] is True)
        need(approvals["model_download_approved"] is True)
        need(approvals["bounded_training_pilot_approved"] is True)
        need(approvals["deployment_authorized"] is False)
        released = (approvals["resource_creation_release"] is True and
                    approvals["spending_release"] is True)
        need(value["status"] == (
            "operator_preflight_required" if released
            else "budget_approved_execution_withheld"
        ))
        need(value["runtime_evidence"] == {
            "environment_variable": EVIDENCE_ENV,
            "checked_in_evidence_allowed": False,
        })
        need(value["phase_b_ready"] is False)
        return value
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError,
            RecursionError, AttributeError):
        raise RuntimeGuardError("kova cosmo runtime guard rejected") from None


def load_evidence_record(path: Path, *,
                         repository_root: Path = ROOT) -> tuple[dict, str]:
    try:
        need(path.is_absolute())
        resolved = path.resolve(strict=True)
        repository = repository_root.resolve(strict=True)
        need(repository not in resolved.parents and resolved != repository)
        with resolved.open("rb") as stream:
            raw = stream.read(MAX_EVIDENCE_BYTES + 1)
        need(0 < len(raw) <= MAX_EVIDENCE_BYTES)
        value = parse_json(raw.decode("utf-8"))
        need(type(value) is dict and list(value) == [
            "schema_version", "captured_at_utc", "subscription_id",
            "resource_group", "vm_name", "region", "vm_size",
            "family_quota_limit_vcpus", "capacity_confirmed",
            "compute_usd_per_hour", "ancillary_cost_bound_usd",
            "preflight_power_state", "public_ip_attached",
            "control_plane_deallocation_deadline_utc",
            "control_plane_deallocation_rule_id", "watchdog_principal",
            "watchdog_permission_tested_at_utc", "watchdog_test_result",
        ])
        need(value["schema_version"] == 1)
        timestamp(value["captured_at_utc"])
        for key in ("subscription_id", "resource_group", "vm_name",
                    "control_plane_deallocation_rule_id",
                    "watchdog_principal"):
            need(nonempty(value[key]))
        need(value["region"] == "eastus")
        need(value["vm_size"] == "Standard_NC4as_T4_v3")
        need(type(value["family_quota_limit_vcpus"]) is int)
        need(value["family_quota_limit_vcpus"] >= 4)
        need(value["capacity_confirmed"] is True)
        money(value["compute_usd_per_hour"])
        money(value["ancillary_cost_bound_usd"])
        need(value["preflight_power_state"] == "deallocated")
        need(value["public_ip_attached"] is False)
        timestamp(value["control_plane_deallocation_deadline_utc"])
        timestamp(value["watchdog_permission_tested_at_utc"])
        need(value["watchdog_test_result"] == "passed")
        return value, hashlib.sha256(raw).hexdigest()
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError,
            RecursionError, AttributeError):
        raise RuntimeGuardError("kova cosmo runtime guard rejected") from None


def load_evidence(path: Path, *, repository_root: Path = ROOT) -> dict:
    return load_evidence_record(path, repository_root=repository_root)[0]


def assess_preflight(policy: dict, evidence: dict, *, now: datetime) -> dict:
    need(now.tzinfo is not None and now.utcoffset() == timedelta(0))
    approvals = policy["owner_approvals"]
    need(approvals["resource_creation_release"] is True)
    need(approvals["spending_release"] is True)
    need(approvals["deployment_authorized"] is False)

    pricing = policy["pricing"]
    need(money(evidence["compute_usd_per_hour"]) ==
         money(pricing["owner_verified_compute_usd_per_hour"]))
    need(money(evidence["ancillary_cost_bound_usd"]) <=
         money(pricing["minimum_ancillary_reserve_usd"]))

    captured = timestamp(evidence["captured_at_utc"])
    tested = timestamp(evidence["watchdog_permission_tested_at_utc"])
    deadline = timestamp(evidence["control_plane_deallocation_deadline_utc"])
    need(captured <= now <= captured + timedelta(minutes=15))
    need(tested <= now <= tested + timedelta(hours=24))
    need(now + timedelta(minutes=5) <= deadline)
    need(deadline <= now + timedelta(
        minutes=pricing["maximum_allocated_minutes"]
    ))
    return {
        "status": "ready_for_single_bounded_pilot",
        "deadline_utc": evidence["control_plane_deallocation_deadline_utc"],
        "maximum_allocated_minutes": pricing["maximum_allocated_minutes"],
        "maximum_compute_cost_usd": pricing["maximum_compute_cost_usd"],
        "approved_all_in_budget_usd": pricing["approved_all_in_budget_usd"],
        "deployment_authorized": False,
        "phase_b_ready": False,
        "closed_checklist_ids": [],
    }


def require_ready(*, root: Path = ROOT, evidence_path: Path | None = None,
                  now: datetime | None = None) -> dict:
    policy = load_policy(root)
    if evidence_path is None:
        raw = os.environ.get(EVIDENCE_ENV)
        need(nonempty(raw, 4096))
        evidence_path = Path(raw)
    evidence, evidence_sha256 = load_evidence_record(
        evidence_path, repository_root=root
    )
    report = assess_preflight(
        policy, evidence, now=now or datetime.now(timezone.utc)
    )
    report["runtime_evidence_sha256"] = evidence_sha256
    return report


def verify_post_run(preflight: dict, post_run_path: Path,
                    root: Path = ROOT) -> dict:
    """Verify deallocation evidence and enumerate every residual resource."""
    try:
        need(post_run_path.is_absolute() and not post_run_path.is_symlink())
        resolved = post_run_path.resolve(strict=True)
        repository = root.resolve(strict=True)
        need(repository not in resolved.parents and resolved != repository)
        with resolved.open("rb") as stream:
            raw = stream.read(MAX_EVIDENCE_BYTES + 1)
        need(0 < len(raw) <= MAX_EVIDENCE_BYTES)
        value = parse_json(raw.decode("utf-8"))
        need(type(value) is dict and list(value) == [
            "schema_version", "observed_at_utc", "allocation_started_at_utc",
            "deallocated_at_utc", "subscription_id",
            "resource_group", "vm_name", "deallocation_deadline_utc",
            "power_state", "public_ip_attached", "allocated_seconds",
            "compute_cost_upper_bound_usd",
            "ancillary_cost_observed_or_bound_usd",
            "all_in_cost_upper_bound_usd", "residual_resources",
        ])
        need(value["schema_version"] == 1)
        observed = timestamp(value["observed_at_utc"])
        started = timestamp(value["allocation_started_at_utc"])
        deallocated = timestamp(value["deallocated_at_utc"])
        deadline = timestamp(value["deallocation_deadline_utc"])
        need(value["subscription_id"] == preflight["subscription_id"])
        need(value["resource_group"] == preflight["resource_group"])
        need(value["vm_name"] == preflight["vm_name"])
        need(value["deallocation_deadline_utc"] ==
             preflight["control_plane_deallocation_deadline_utc"])
        need(timestamp(preflight["captured_at_utc"]) <= started)
        need(started <= deallocated <= observed)
        need(deallocated <= deadline)
        need(observed <= deadline + timedelta(minutes=15))
        allocated_seconds = int((deallocated - started).total_seconds())
        need(type(value["allocated_seconds"]) is int and
             not isinstance(value["allocated_seconds"], bool))
        need(value["allocated_seconds"] == allocated_seconds)
        policy = load_policy(root)
        pricing = policy["pricing"]
        need(0 <= allocated_seconds <=
             pricing["maximum_allocated_minutes"] * 60)
        compute = money(value["compute_cost_upper_bound_usd"])
        ancillary = money(value["ancillary_cost_observed_or_bound_usd"])
        all_in = money(value["all_in_cost_upper_bound_usd"])
        minimum_compute = (
            money(pricing["owner_verified_compute_usd_per_hour"]) *
            Decimal(allocated_seconds) / Decimal(3600)
        )
        need(compute >= minimum_compute)
        need(compute <= money(pricing["maximum_compute_cost_usd"]))
        need(ancillary <= money(pricing["minimum_ancillary_reserve_usd"]))
        need(all_in == compute + ancillary)
        need(all_in <= money(pricing["approved_all_in_budget_usd"]))
        need(value["power_state"] == "deallocated")
        need(value["public_ip_attached"] is False)
        resources = value["residual_resources"]
        need(type(resources) is list and len(resources) <= 32)
        for item in resources:
            need(type(item) is dict and list(item) == [
                "resource_id", "resource_type", "billable",
                "disposition", "evidence",
            ])
            need(nonempty(item["resource_id"], 2048))
            need(nonempty(item["resource_type"]))
            need(type(item["billable"]) is bool)
            need(item["disposition"] in (
                "deleted", "retained_within_approved_budget",
            ))
            need(nonempty(item["evidence"], 2048))
        return {
            "status": "deallocation_verified",
            "observed_at_utc": value["observed_at_utc"],
            "power_state": value["power_state"],
            "allocated_seconds": allocated_seconds,
            "compute_cost_upper_bound_usd": value[
                "compute_cost_upper_bound_usd"
            ],
            "ancillary_cost_observed_or_bound_usd": value[
                "ancillary_cost_observed_or_bound_usd"
            ],
            "all_in_cost_upper_bound_usd": value[
                "all_in_cost_upper_bound_usd"
            ],
            "within_approved_budget": True,
            "post_run_evidence_sha256": hashlib.sha256(raw).hexdigest(),
            "residual_resource_count": len(resources),
            "billable_residual_resource_count": sum(
                item["billable"] for item in resources
            ),
            "deployment_authorized": False,
            "phase_b_ready": False,
            "closed_checklist_ids": [],
        }
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError,
            RecursionError, AttributeError):
        raise RuntimeGuardError("kova cosmo runtime guard rejected") from None


def dry_run(root: Path = ROOT) -> dict:
    policy = load_policy(root)
    approvals = policy["owner_approvals"]
    blockers = []
    if not approvals["resource_creation_release"]:
        blockers.append("resource_creation_release_withheld")
    if not approvals["spending_release"]:
        blockers.append("spending_release_withheld")
    if not os.environ.get(EVIDENCE_ENV):
        blockers.append("runtime_evidence_missing")
    return {
        "status": "blocked" if blockers else "operator_preflight_required",
        "blockers": blockers,
        "approved_all_in_budget_usd": policy["pricing"][
            "approved_all_in_budget_usd"
        ],
        "maximum_allocated_minutes": policy["pricing"][
            "maximum_allocated_minutes"
        ],
        "resource_created": False,
        "spending_started": False,
        "phase_b_ready": False,
        "closed_checklist_ids": [],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--require-ready", action="store_true")
    actions.add_argument("--verify-post-run", type=Path,
                         help="External post-run deallocation/cost evidence")
    parser.add_argument("--preflight-evidence", type=Path,
                        help="Exact external preflight evidence used by the run")
    arguments = parser.parse_args(argv)
    try:
        if arguments.verify_post_run is not None:
            need(arguments.preflight_evidence is not None)
            preflight, preflight_sha256 = load_evidence_record(
                arguments.preflight_evidence
            )
            report = verify_post_run(preflight, arguments.verify_post_run)
            report["preflight_evidence_sha256"] = preflight_sha256
        else:
            need(arguments.preflight_evidence is None)
            report = require_ready() if arguments.require_ready else dry_run()
        print(json.dumps(report, sort_keys=True))
        return 0
    except RuntimeGuardError as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
