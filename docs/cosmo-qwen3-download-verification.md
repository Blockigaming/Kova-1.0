# Qwen3-0.6B immutable download and verification

Status: prepared only. These commands were not executed by this source change,
and no model weights were downloaded.

The reviewed manifest is
`config/qwen3-0.6b-download-manifest.v1.json`. It binds all nine allowed files
for `Qwen/Qwen3-0.6B` revision
`c1899de289a04d12100db370d81485cdf75e47ca` by exact byte count and SHA-256.
The expected total is 1,519,207,673 bytes. The runtime verifier rejects a
missing, additional required, resized, or byte-changed runtime asset, including
`config.json`, `generation_config.json`, tokenizer files, and weights.

## Source-only check now

This command validates only the checked-in manifest and performs no network
request or download:

```sh
python3 -m training.cosmo_artifacts
```

## Future authorized download

Run only after quota, capacity, source release, spending release, the external
watchdog, and the control-plane deallocation deadline have all passed. Use a new
absolute directory outside the repository:

```sh
export KOVA_COSMO_CACHE=/absolute/external/path/new-huggingface-cache
test ! -e "$KOVA_COSMO_CACHE"
mkdir -m 700 "$KOVA_COSMO_CACHE"

KOVA_COSMO_SNAPSHOT="$(python3 - <<'PY'
import os
from huggingface_hub import snapshot_download

print(snapshot_download(
    repo_id="Qwen/Qwen3-0.6B",
    revision="c1899de289a04d12100db370d81485cdf75e47ca",
    allow_patterns=[
        "LICENSE",
        "README.md",
        "config.json",
        "generation_config.json",
        "merges.txt",
        "model.safetensors",
        "tokenizer.json",
        "tokenizer_config.json",
        "vocab.json",
    ],
    cache_dir=os.environ["KOVA_COSMO_CACHE"],
))
PY
)"
export KOVA_COSMO_SNAPSHOT

python3 -m training.cosmo_artifacts "$KOVA_COSMO_SNAPSHOT"
```

Do not use a floating revision, broaden the allowlist, continue after a hash
failure, upload the snapshot, or place it inside the repository.

## Independent generation authentication

Before a future measured evaluation, create one random per-run authentication
key on a trusted operator system, keep the verifier copy outside the GPU run,
and expose an owner-only copy to the guarded runner:

```sh
umask 077
openssl rand -hex 32 > /absolute/protected/path/cosmo-generation-auth.key
export KOVA_COSMO_EVALUATION_AUTH_KEY_FILE=/absolute/protected/path/cosmo-generation-auth.key
```

Compute the fingerprint over the decoded 32-byte key, then place only that
fingerprint in `config/kova-cosmo-generation-trust.v1.json` and change its
status to `signing_key_pinned_for_guarded_runner` in a separately reviewed,
exact-head-green source commit:

```sh
python3 - <<'PY'
import hashlib
from pathlib import Path

path = Path("/absolute/protected/path/cosmo-generation-auth.key")
key = bytes.fromhex(path.read_text(encoding="ascii").strip())
assert len(key) == 32
print(hashlib.sha256(key).hexdigest())
PY
```

The current trust policy intentionally contains no fingerprint, so arbitrary
caller-selected keys cannot turn hand-written output into measured evidence.
The runner and evaluator remain blocked until that separate trust-anchor change
passes review. Never commit the key itself.

The runner HMAC-authenticates every generated answer and its case, variant,
tokens, timing, runtime, adapter, source commit, and plan lineage. Human scores
remain a separate hash-bound overlay. The evaluator requires the protected key
again and rejects absent, forged, wrong-key, or post-run-tampered measurements.
The key is never copied into the evaluation output or repository.
