"""Authenticate Cosmo generation measurements with an external per-run key.

The key is created and retained outside both the repository and runner output.
The guarded runner signs all measurement fields; the human score overlay is
deliberately excluded because it is produced later and hash-bound separately.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
TRUST_POLICY_PATH = "config/kova-cosmo-generation-trust.v1.json"
MAX_CANONICAL_BYTES = 16 * 1024 * 1024
KEY_HEX = re.compile(r"[0-9a-f]{64}")
HEX64 = re.compile(r"[0-9a-f]{64}")
ALGORITHM = "hmac-sha256"


class AttestationError(ValueError):
    pass


def need(condition: bool) -> None:
    if not condition:
        raise AttestationError("kova cosmo generation attestation rejected")


def canonical(value: object) -> bytes:
    try:
        raw = json.dumps(
            value, sort_keys=True, separators=(",", ":"),
            ensure_ascii=True, allow_nan=False,
        ).encode("ascii")
        need(0 < len(raw) <= MAX_CANONICAL_BYTES)
        return raw
    except (TypeError, ValueError, UnicodeError, RecursionError):
        raise AttestationError(
            "kova cosmo generation attestation rejected"
        ) from None


def load_trust_policy(root: Path = ROOT) -> dict:
    """Load the reviewed trust anchor; an unpinned key fails closed."""
    try:
        value = json.loads(
            (root / TRUST_POLICY_PATH).read_text(encoding="utf-8")
        )
        need(type(value) is dict and list(value) == [
            "schema_version", "status", "algorithm",
            "key_fingerprint_sha256", "external_secret_required",
            "checked_in_secret_allowed",
        ])
        need(value["schema_version"] == 1)
        need(value["algorithm"] == ALGORITHM)
        need(value["external_secret_required"] is True)
        need(value["checked_in_secret_allowed"] is False)
        fingerprint = value["key_fingerprint_sha256"]
        if value["status"] == "signing_key_provisioning_required":
            need(fingerprint is None)
        else:
            need(value["status"] == "signing_key_pinned_for_guarded_runner")
            need(type(fingerprint) is str and
                 HEX64.fullmatch(fingerprint) is not None)
        return value
    except (OSError, ValueError, TypeError, KeyError, AttributeError,
            UnicodeError, RecursionError, json.JSONDecodeError):
        raise AttestationError(
            "kova cosmo generation attestation rejected"
        ) from None


def load_key(path: Path, *, expected_fingerprint: str,
             repository_root: Path = ROOT) -> bytes:
    """Read a 256-bit key from a protected file outside the repository."""
    try:
        need(path.is_absolute() and path.is_file() and not path.is_symlink())
        resolved = path.resolve(strict=True)
        repository = repository_root.resolve(strict=True)
        need(repository != resolved and repository not in resolved.parents)
        mode = resolved.stat().st_mode
        need(mode & 0o077 == 0)
        with resolved.open("rb") as stream:
            raw = stream.read(66)
        encoded = raw.rstrip(b"\n")
        need(len(encoded) == 64 and raw in (encoded, encoded + b"\n"))
        text = encoded.decode("ascii")
        need(KEY_HEX.fullmatch(text) is not None)
        key = bytes.fromhex(text)
        need(type(expected_fingerprint) is str and
             HEX64.fullmatch(expected_fingerprint) is not None)
        need(hmac.compare_digest(
            hashlib.sha256(key).hexdigest(), expected_fingerprint
        ))
        return key
    except (OSError, ValueError, TypeError, UnicodeError):
        raise AttestationError(
            "kova cosmo generation attestation rejected"
        ) from None


def measurement_payload(bundle: dict) -> dict:
    """Return exactly the runner-produced fields protected by the MAC."""
    need(type(bundle) is dict)
    expected = [
        "schema_version", "kind", "plan_sha256", "source_commit",
        "adapter_sha256", "adapter_receipt_sha256", "runner_attestation",
        "attempts",
    ]
    need(list(bundle) == expected)
    attempts = bundle["attempts"]
    need(type(attempts) is list)
    protected_attempts = []
    for row in attempts:
        need(type(row) is dict and "scores" in row)
        protected_attempts.append({
            key: value for key, value in row.items() if key != "scores"
        })
    return {
        "schema_version": bundle["schema_version"],
        "kind": bundle["kind"],
        "plan_sha256": bundle["plan_sha256"],
        "source_commit": bundle["source_commit"],
        "adapter_sha256": bundle["adapter_sha256"],
        "adapter_receipt_sha256": bundle["adapter_receipt_sha256"],
        "attempts": protected_attempts,
    }


def create_attestation(bundle: dict, key: bytes) -> dict:
    need(type(key) is bytes and len(key) == 32)
    need(bundle.get("kind") == "measured")
    need(bundle.get("runner_attestation") is None)
    raw = canonical(measurement_payload(bundle))
    return {
        "schema_version": 1,
        "kind": "kova_cosmo_guarded_runner_attestation",
        "algorithm": ALGORITHM,
        "key_fingerprint_sha256": hashlib.sha256(key).hexdigest(),
        "measurement_sha256": hashlib.sha256(raw).hexdigest(),
        "signature": hmac.new(key, raw, hashlib.sha256).hexdigest(),
    }


def verify_attestation(bundle: dict, key_path: Path, *,
                       expected_key_fingerprint: str,
                       repository_root: Path = ROOT) -> dict:
    key = load_key(
        key_path, expected_fingerprint=expected_key_fingerprint,
        repository_root=repository_root,
    )
    value = bundle.get("runner_attestation")
    need(type(value) is dict and list(value) == [
        "schema_version", "kind", "algorithm", "key_fingerprint_sha256",
        "measurement_sha256", "signature",
    ])
    need(value["schema_version"] == 1)
    need(value["kind"] == "kova_cosmo_guarded_runner_attestation")
    need(value["algorithm"] == ALGORITHM)
    for field in (
        "key_fingerprint_sha256", "measurement_sha256", "signature",
    ):
        need(type(value[field]) is str and
             HEX64.fullmatch(value[field]) is not None)
    raw = canonical(measurement_payload(bundle))
    expected_fingerprint = hashlib.sha256(key).hexdigest()
    expected_measurement = hashlib.sha256(raw).hexdigest()
    expected_signature = hmac.new(key, raw, hashlib.sha256).hexdigest()
    need(hmac.compare_digest(value["key_fingerprint_sha256"],
                             expected_fingerprint))
    need(hmac.compare_digest(value["measurement_sha256"],
                             expected_measurement))
    need(hmac.compare_digest(value["signature"], expected_signature))
    return {
        "status": "guarded_runner_attestation_verified",
        "algorithm": ALGORITHM,
        "key_fingerprint_sha256": expected_fingerprint,
        "measurement_sha256": expected_measurement,
    }
