"""Immutable artifact verification for the pinned Qwen3-0.6B checkpoint."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

REQUIRED_ASSETS = (
    "LICENSE",
    "README.md",
    "config.json",
    "generation_config.json",
    "merges.txt",
    "model.safetensors",
    "tokenizer.json",
    "tokenizer_config.json",
    "vocab.json",
)
EXPECTED_SHA256 = {
    "model.safetensors":
        "f47f71177f32bcd101b7573ec9171e6a57f4f4d31148d38e382306f42996874b",
    "tokenizer.json":
        "aeb13307a71acd8fe81861d94ad54ab689df773318809eed3cbe794b4492dae4",
    "tokenizer_config.json":
        "d5d09f07b48c3086c508b30d1c9114bd1189145b74e982a265350c923acd8101",
}


class ArtifactError(ValueError):
    pass


def need(condition: bool) -> None:
    if not condition:
        raise ArtifactError("kova cosmo artifact rejected")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_snapshot(directory: Path) -> dict[str, dict]:
    try:
        need(directory.is_absolute() and directory.is_dir())
        inventory = {}
        for name in REQUIRED_ASSETS:
            path = directory / name
            need(path.is_file())
            digest = file_sha256(path)
            if name in EXPECTED_SHA256:
                need(digest == EXPECTED_SHA256[name])
            inventory[name] = {"bytes": path.stat().st_size, "sha256": digest}

        config = json.loads(
            (directory / "config.json").read_text(encoding="utf-8")
        )
        license_text = (directory / "LICENSE").read_text(encoding="utf-8")
        need(type(config) is dict)
        need(config.get("architectures") == ["Qwen3ForCausalLM"])
        need(config.get("model_type") == "qwen3")
        need(config.get("num_hidden_layers") == 28)
        need(config.get("hidden_size") == 1024)
        need(config.get("vocab_size") == 151936)
        need("Apache License" in license_text)
        need("Version 2.0, January 2004" in license_text)
        return inventory
    except (OSError, UnicodeError, ValueError, TypeError, KeyError,
            json.JSONDecodeError):
        raise ArtifactError("kova cosmo artifact rejected") from None
