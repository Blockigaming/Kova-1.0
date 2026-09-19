# Kova identity pilot: configuration plus fine-tuning preparation

This is a source-only starter for the owner's requested Kova-branded assistant.
It is not a trained model, a production prompt rollout or a GPU deployment.
Phase A stays 30/40. Phase B remains NOT READY.

## Intended visible behavior

For "Who are you?", the ordinary target is:

> I'm Kova, the AI assistant in KovaGPT.

For ordinary tasks, answer the question without an identity preamble, supplier
branding or sales copy. Kova is the product/conversational identity. This starter
does not suppress truthful answers to explicit technical-provenance questions,
remove required upstream notices, rewrite licensed origin records or claim that
Kova trained a foundation model from scratch. The one known-origin validation
example is explicitly hypothetical; it is not a live runtime observation.

## New source files

- `prompts/kova-identity.v2.txt`: proposed shared identity instructions.
- `data/kova-identity-pilot.v1.jsonl`: 24 synthetic training examples and 12
  separately held-out validation examples, including basic identity, useful tasks,
  output format, uncertainty, privacy and truthful activity.
- `config/kova-cosmo-pilot.v1.json`: preparation-only LoRA plan for the already
  selected Cosmo source, bound to its immutable source revision. The proposed
  compute label is the owner's Azure NC4as T4 v3 target, not evidence of GPU fit.
- `training/identity_pilot.py`: standard-library-only validation and compilation.
- `training/test_identity_pilot.py`: source/data regression checks.

No private chats, customer records, credentials, external model outputs or
upstream weight files are included. These examples were synthetically prepared
for Kova; human review is not yet complete. The corpus is a small starting set,
not a claim of sufficient training diversity, model quality or independence of
all paraphrases. Validation prompts are disjoint by normalized exact text, not
by a proven semantic train/test contamination analysis.

## What is actually verified

The source checker verifies fixed paths, fingerprints, immutable Cosmo base
identity, exact flags/types/shapes, record roles, unique identifiers, normalized
prompt disjointness and train/validation counts. The compiler prepends the shared
identity prompt, keeps validation out of training, and writes deterministic JSONL
files with SHA-256 receipts. Existing output folders are refused, not overwritten.
It has no network client, model loader, cloud API, training framework or execute
option. Registered CI checks source integrity only; it does not evaluate trained
model answers. Hypothetical runtime metadata is allowed only in its designated
validation example and must never be passed off as real serving evidence.

Source validation only, from the repository root:

```sh
python3 -m training.identity_pilot
python3 -m unittest training.test_identity_pilot -v
```

Prepare data in a NEW folder, without downloading weights or starting training:

```sh
python3 -m training.identity_pilot --output artifacts/kova-identity-pilot
```

The resulting `train.jsonl`/`validation.jsonl` contain conversational messages.
Tokenization, model-specific chat-template compatibility and the actual training
framework still require a separate verified recipe. Do not claim a ready-to-run
trainer from the presence of these files.

## Existing source is not silently repurposed

The old `config/candidate.v1.json`, `config/training-stack.v1.json`,
`config/identity.v1.json` and original four-record starter are untouched. The old
`training:command` recipe is not this pilot and must not be used to launch it.
The v2 prompt is not connected to live app/worker prompts by this draft. Current
Chat/Work route policies, all exact compute budgets, runtime provider disclosure,
weekly usage and release guards are unchanged. No PR is merged into main here.

## Before a paid pilot

Review the examples; obtain a verified downloadable artifact inventory and its
notices; validate a pinned tokenizer/template and compatible training environment;
select/review measured-memory-safe hyperparameters; confirm region/quota and the
actual Azure rate; approve a separate budget and shutdown procedure. The plan
keeps budget, hyperparameters and trained-adapter digest null. Its download,
training and deployment permissions remain false. Neither this source nor a
successful compiler result can grant spending or deployment authority.

Evaluate real base and trained outputs on the held-out examples and a broader
quality suite before releasing the adapter. Record the exact base and adapter
hashes and preserve derivative lineage. A model introducing itself as Kova alone
is not proof that a fine-tune ran successfully or that its general quality improved.

## Technical references

- Selected Cosmo source: https://huggingface.co/Qwen/Qwen3-0.6B/commit/c1899de289a04d12100db370d81485cdf75e47ca
- Selected source license: https://huggingface.co/Qwen/Qwen3-0.6B/blob/c1899de289a04d12100db370d81485cdf75e47ca/LICENSE
- LoRA documentation: https://huggingface.co/docs/peft/main/en/conceptual_guides/lora
- Redistribution/notice conditions: https://www.apache.org/licenses/LICENSE-2.0.html

The license permits modifications under its terms and imposes notice conditions
on redistribution. It does not require a supplier name in every ordinary answer.
The fine-tuning method changes trainable parameters; this starter has not done so.
