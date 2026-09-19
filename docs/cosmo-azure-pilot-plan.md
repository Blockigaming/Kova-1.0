# First Kova Cosmo Azure pilot

Status: proposed, not executable or provisioned. Phase A 30/40; Phase B NOT READY.

The owner requested actual identity fine-tuning and Azure hosting on September 19, 2026. The owner approved a strict $2 all-in pilot cap, the immutable Qwen3-0.6B download and one bounded training pilot, then explicitly withheld the release to spend. The last confirmed East US NCASv3_T4 family quota request state was `Received` and under review. Do not record completed training or promote source execution flags from this document.

## Scope

One Cosmo pilot using Qwen/Qwen3-0.6B revision c1899de289a04d12100db370d81485cdf75e47ca, existing FP16 LoRA recipe, East US, proposed Standard_NC4as_T4_v3. Keep the existing 24 training / 12 validation split. Do not expand to Orion, Nova or shared Chat until this pipeline is evaluated.

Proposed runtime ceiling: 60 minutes of allocated GPU time including environment checks, download, baseline evaluation, training and trained evaluation. This is a proposed bound, not a claim all work fits. On timeout preserve partial evidence and mark the run incomplete; never silently extend the bound. No public endpoint or production traffic during the pilot.

## Preconditions

- Verify the East US T4 quota request is approved and re-check capacity immediately before the pilot. A submitted or pending request is not approval.
- Re-check the owner-verified `$0.5260` hourly compute rate and bound disk, network and storage charges immediately before the pilot. Pricing drift blocks execution.
- Keep the approved all-in budget at `$2.0000`. The 60-minute compute maximum is `$0.5260`, leaving at least `$1.4740` for all ancillary charges. Budget alerts are not a hard stop.
- Preserve the approved 36/36 owner review ledger and its dataset binding. The completed review does not grant download, training or spending release by itself.
- Resolve and hash-lock PyTorch/CUDA and transitive dependencies; verify the exact tokenizer/template and completion token masks, maximum length and no silent answer truncation for every example.
- Verify actual LoRA target modules, FP16 capability and memory fit. CPU/source tests do not prove these.
- Review the assembled source and an explicit authorization change. Current validators intentionally reject promoted flags; changing flags alone cannot enable this version.

## Paid resource boundary and stop procedure

Before creation, select the exact subscription/resource group, image, disk configuration, region and size, and record resource IDs and the approved budget. Do not change existing production resources or RBAC casually.

Establish a separately verified control-plane deallocation mechanism with a deadline before starting GPU work. It must remain effective if the training process or SSH session fails. A shell trap, guest shutdown or training timeout alone is insufficient. Test the mechanism and its permissions before relying on it. If no such mechanism is available, do not provision the GPU.

`config/kova-cosmo-runtime-guard.v1.json` records the exact budget math and the current execution hold. `training.cosmo_runtime_guard` requires fresh, external (never checked-in) evidence of quota, capacity, price, ancillary-cost bound, a deallocated preflight state, no public IP, a control-plane deadline no more than 60 minutes away and a separately tested watchdog identity. The SFT entrypoint invokes this guard before it probes training dependencies. Both source authorization and runtime evidence must pass; an environment variable cannot override either one.

The same module verifies a post-run control-plane observation of `deallocated` and a complete residual-resource inventory. `stopped` is rejected because Azure compute billing can continue in that state. Post-run evidence must bind allocation start, deallocation and observation timestamps; the exact allocated seconds; four-decimal compute and ancillary upper bounds; and their all-in sum. The compute bound must cover elapsed time at `$0.5260` per hour, allocation cannot exceed 60 minutes, ancillary exposure cannot exceed `$1.4740`, and the total cannot exceed `$2.0000`. Every residual disk, interface or other resource must be recorded with evidence and either deleted or explicitly retained within that bound. This verification does not itself delete anything.

After deallocation, run `python3 -m training.cosmo_runtime_guard --verify-post-run /absolute/path/post-run.json --preflight-evidence /absolute/path/runtime-evidence.json`. Both files must remain outside the repository. A successful report includes the SHA-256 of each exact evidence file, the reconciled duration and costs, residual-resource counts and `within_approved_budget: true`; it still grants no deployment or Phase B authority.

`training.cosmo_runtime_probe` resolves the otherwise circular runtime gate. It remains blocked by the current quota, source-release and spending-release values. After those values are separately reviewed and promoted, it requires a distinct `KOVA_CONFIRM_PAID_RUNTIME_PROBE=YES` acknowledgement plus the same fresh external deadline/watchdog evidence. Only then may it download the fixed allowlist from the immutable checkpoint revision. It verifies the official weight SHA-256 (`f47f71177f32bcd101b7573ec9171e6a57f4f4d31148d38e382306f42996874b`), both tokenizer hashes, Qwen3 architecture fields and Apache-2.0 notice before loading locally with network resolution disabled. It then verifies the real Qwen target inventory on a T4 and runs one completion-masked FP16 forward/backward pass. It performs zero optimizer steps, saves no adapter and cannot authorize full training or deployment. Review its sanitized evidence before promoting `runtime_compatibility_verified` in another source change.

Full SFT must receive that external cache location through `KOVA_COSMO_VERIFIED_SNAPSHOT`. The trainer re-hashes the same artifact inventory, rejects repository-contained snapshots, sets Hugging Face, Transformers and Datasets offline, and passes only the verified local path to `SFTTrainer`. It cannot silently re-resolve the model name or accept a changed cache after the compatibility probe. It also requires a new absolute directory outside the repository through `KOVA_COSMO_OUTPUT_DIR` and a lowercase 40-character `KOVA_SOURCE_COMMIT`; existing output paths are refused. The paid probe, trainer and evaluator compare that commit to `git rev-parse HEAD` and reject any tracked or untracked checkout changes.

Checkpoints remain separate from the retained `adapter/` candidate. The final candidate is saved with safe serialization and `training.cosmo_adapter_receipt` writes `adapter-receipt.v1.json` without overwriting existing evidence. The receipt binds the source commit, immutable base revision and weight hash, dataset/prompt/review digests, SFT recipe, runtime guard and exact external runtime-evidence digest, evaluation plan, software lock, declared training settings, completed global-step count and training loss, hardware declaration and every retained adapter file. Verification rejects symlinks, unknown files, pickle-style weight files, malformed or incomplete LoRA tensor inventories, lineage drift and post-receipt mutation. It explicitly records that evaluation, deployment and Phase B readiness remain false.

The operator must verify the final Azure allocation state is deallocated. Record elapsed allocation time and remaining billable disks/storage; remove only pilot resources explicitly authorized for deletion. Do not claim an exact dollar hard cap solely from a timer. If deadline enforcement fails, stop progression and use the verified account control path to deallocate, preserving failure evidence.

## Execution and evidence

1. Download only approved immutable model/tokenizer assets, preserve notices and hash the inventory.
2. Evaluate the same held-out cases on the base model and configured base model. Record all failures and missing cases, environment, latency and memory use.
3. Train the adapter once under the approved recipe and bound. No external reporting or Hub upload.
4. Verify the generated adapter receipt and test adapter reload. A retained adapter without a valid receipt is not an evaluation candidate.
5. Evaluate the trained adapter on the same cases, preserving all outputs and missing-case accounting. Measured evidence must verify the local receipt and bind both its digest and the adapter digest. Human review evaluates utility and identity; saying Kova alone does not establish success.
6. Preserve results, deallocate and verify resource state, then decide whether an Azure serving trial is justified.

`training.cosmo_evaluation_runner` implements step 5 but is source-blocked by the same quota, runtime-compatibility and spending controls plus a separate `KOVA_CONFIRM_PAID_EVALUATION=YES` acknowledgement. It re-verifies the offline snapshot and adapter receipt before importing model dependencies. It runs greedy, thinking-disabled generation capped at 256 new tokens for the 12 cases under all three variants, with identical hardware/software/runtime evidence. Each attempt is fsynced to an external append-only journal; the final bundle is written without overwriting existing evidence. Generation failures remain explicit failed attempts, and every human score remains `pending`, so generation alone cannot complete comparison or authorize release.

Human review uses the hash-locked `config/kova-cosmo-evaluation-rubric.v1.json` and a separate `training.cosmo_evaluation_review` score overlay bound to both that rubric and the SHA-256 of the immutable 36-attempt generation bundle. The rubric defines pass/fail criteria for identity, instruction adherence, factuality, format adherence, general quality and safety/truthfulness; a Kova keyword alone cannot establish an identity pass. The overlay contains only ordered attempt IDs and those six verdicts, so it cannot replace answers, latency, token counts, runtime lineage or artifact digests. Failed, missing, pre-scored, wrong-rubric or still-pending attempts block finalization. A completed overlay writes a separate reviewed bundle and review receipt, but a free-form reviewer label is not authenticated identity and the result still cannot authorize release, deployment or Phase B.

## Azure publication boundary

After successful evaluation, prepare a separately reviewable private Azure artifact/serving plan with exact artifact digest, storage/access details, running cost, health checks and rollback. Public deployment and KovaGPT production traffic require their own verified cutover; a request to host the model is not evidence those gates passed. Preserve working application routes.

Kova is the derivative model's product identity. Preserve upstream license and lineage records and answer explicit technical-provenance questions truthfully. Do not describe the upstream foundation weights as trained from scratch by Kova.
