# Current Kova model topology and pinned upstream source

Owner topology: Models issue #10 comment 5734534302 (September 18, 2026).
The following source references retain the subsequently selected Qwen model names.
This document is not evidence that a Kova model was trained, loaded or deployed.

## Chat

The intended Chat topology has one underlying model slot, `chat-shared`. Lite,
Medium, Thinking/High, Extra High, Max and Ultra are effort/orchestration choices
over the same model. Effort changes bounded work depth, not base model identity.
Lite is the default. Free and signed-out users stay locked to Lite. Plus exposes
Lite, Medium, Thinking. Pro exposes Lite, Medium, High, Extra High, Max, Ultra.
Ultra remains bounded 2-5 specialist orchestration over the selected model.

The historical internal Chat route `instant` is retained while its display label
is Lite. Plus Thinking retains the canonical High effort; this does not imply a
separate Nova Chat model. Kova Auto must first resolve through the existing
trusted classifier to an entitled Chat route; it is not an additional model.

## Work

Work has three distinct model families: Kova 5.6 Cosmo, Orion and Nova. Within each
family, Lite, Medium, High, Extra High, Max and Ultra stay on that family's model.
Lite is the default; historical internal `light` is retained. Ultra uses bounded
sub-agents over the selected family, not a fourth family or renamed single call.
Current target access is Free 0/18, Plus 18/18, Pro 18/18. The published execution
grant still contains the older Plus 9/18 ceiling and is not changed by this work.

## Exact upstream references

The official Qwen commit pages were checked on September 18, 2026. These are
immutable **upstream source repository** revisions, not checksums of a downloaded
weight set or a selected Q4/other quantization. No weights were downloaded.

| Slot | Upstream model | Full source revision |
| --- | --- | --- |
| `chat-shared` | `Qwen/Qwen3-8B` | `b968826d9c46dd6066d109eabc6255188de91218` |
| `work-cosmo` | `Qwen/Qwen3-0.6B` | `c1899de289a04d12100db370d81485cdf75e47ca` |
| `work-orion` | `Qwen/Qwen3-1.7B` | `70d244cc86ccca08cf5af4e1e306ecf908b1ad5e` |
| `work-nova` | `Qwen/Qwen3-4B` | `1cfa9a7208912126459214e8b04321603b3df60c` |

Primary provenance:
- https://huggingface.co/Qwen/Qwen3-8B/commit/b968826d9c46dd6066d109eabc6255188de91218
- https://huggingface.co/Qwen/Qwen3-0.6B/commit/c1899de289a04d12100db370d81485cdf75e47ca
- https://huggingface.co/Qwen/Qwen3-1.7B/commit/70d244cc86ccca08cf5af4e1e306ecf908b1ad5e
- https://huggingface.co/Qwen/Qwen3-4B/commit/1cfa9a7208912126459214e8b04321603b3df60c

`release/model_revisions.py` holds immutable source references for six canonical
Chat routes and eighteen canonical Work routes. Lookup is exact; caller objects,
wildcards, unnormalized aliases and unresolved Auto do not select a model. This
is source introspection, not tier authorization, authenticated active-model
metadata, a native loader, a job-admission capability or a dispatch endpoint.
The reference class itself is not an authorization credential.

## Validation and evidence boundaries

`config/current-product-policy.v2.json` and its checker agree on the complete
shape, every model/slot/revision, every effort, the current target entitlements,
and source-only readiness state. Unknown fields, duplicate JSON keys, booleans
standing in for numeric budgets, floating-point lookalikes, changed readiness
flags, swapped family assignments and mutable/replacement revisions fail closed.
Input is bounded to 64 KiB and malformed input produces a sanitized error.

The checker compares existing Work compute metadata without changing its passes,
output ceilings or Ultra agent bounds. A mismatch is visible in its report and
fails the registered policy test. Merely changing runtime profile names or adding
a `model_slot` string cannot establish runtime alignment. The checker has no
runtime observations and continues to report both runtime identity flags false,
no verified or quantized artifact slots, no checklist closures and Phase B false.

Before serving, independently verify the full artifact inventory and hashes,
source/quantization/fine-tuning lineage, tokenizer/template/config compatibility,
native loading, trusted worker identity, actual route dispatch, model quality,
resource use and application behavior. Upstream revisions are not substitutions
for that evidence, and they do not establish T4 memory fit or latency/throughput.

Run the registered source tests with:

```sh
python3 -m unittest release.test_current_product_policy release.test_current_product_policy_integrity release.test_model_revisions -v
python3 -m release.current_product_policy
```

## Work usage and unfinished integration

Paid Chat must neither debit nor depend on the Work weekly allowance. Pro Work
capacity remains five times Plus. An exhausted Work allowance must not disable
entitled Chat. Paid replenishment is permitted by product policy, but its amount
and price, Plus base weekly allowance and reset anchor remain unspecified/null.
Existing uncertain-job reservations and finite per-request controls are retained.

Runtime still uses historical Chat profiles and a shared Core candidate for Work.
The new source pins do not repair that integration or remove existing application
aggregate token/premium limits. Loader, exact-route entitlement, job/API, browser
streaming/cancellation, historical evaluation/source reconciliation and independent
review gates remain open. No previously blocked publication payload is included.
No merge, deployment, Azure/Supabase/Stripe/DNS mutation, model/weight download,
training, paid benchmark or new account/resource provisioning occurs here.
