# First Kova Cosmo Azure pilot

Status: proposed, not executable or provisioned. Phase A 30/40; Phase B NOT READY.

The owner requested actual identity fine-tuning and Azure hosting on September 19, 2026. This establishes direction, but no numeric spending cap or authenticated Azure access is available in the current session. Do not record completed training or promote source authorization flags from this document.

## Scope

One Cosmo pilot using Qwen/Qwen3-0.6B revision c1899de289a04d12100db370d81485cdf75e47ca, existing FP16 LoRA recipe, East US, proposed Standard_NC4as_T4_v3. Keep the existing 24 training / 12 validation split. Do not expand to Orion, Nova or shared Chat until this pipeline is evaluated.

Proposed runtime ceiling: 60 minutes of allocated GPU time including environment checks, download, baseline evaluation, training and trained evaluation. This is a proposed bound, not a claim all work fits. On timeout preserve partial evidence and mark the run incomplete; never silently extend the bound. No public endpoint or production traffic during the pilot.

## Preconditions

- Verify authenticated subscription and East US T4 quota/capacity once; quota remains unknown.
- Read current regional compute, disk, network and storage prices. Record quote time and billing assumptions; do not use historical hourly estimates as a current quote.
- Obtain an explicit total pilot budget covering compute plus ancillary charges. Leave the amount unset until the owner supplies it. Budget alerts are not a hard stop.
- Finish human corpus review. Review identity consistency, hypothetical provenance context and held-out evaluation coverage. Assistant inspection is not human approval.
- Resolve and hash-lock PyTorch/CUDA and transitive dependencies; verify the exact tokenizer/template and completion token masks, maximum length and no silent answer truncation for every example.
- Verify actual LoRA target modules, FP16 capability and memory fit. CPU/source tests do not prove these.
- Review the assembled source and an explicit authorization change. Current validators intentionally reject promoted flags; changing flags alone cannot enable this version.

## Paid resource boundary and stop procedure

Before creation, select the exact subscription/resource group, image, disk configuration, region and size, and record resource IDs and the approved budget. Do not change existing production resources or RBAC casually.

Establish a separately verified control-plane deallocation mechanism with a deadline before starting GPU work. It must remain effective if the training process or SSH session fails. A shell trap, guest shutdown or training timeout alone is insufficient. Test the mechanism and its permissions before relying on it. If no such mechanism is available, do not provision the GPU.

The operator must verify the final Azure allocation state is deallocated. Record elapsed allocation time and remaining billable disks/storage; remove only pilot resources explicitly authorized for deletion. Do not claim an exact dollar hard cap solely from a timer. If deadline enforcement fails, stop progression and use the verified account control path to deallocate, preserving failure evidence.

## Execution and evidence

1. Download only approved immutable model/tokenizer assets, preserve notices and hash the inventory.
2. Evaluate the same held-out cases on the base model and configured base model. Record all failures and missing cases, environment, latency and memory use.
3. Train the adapter once under the approved recipe and bound. No external reporting or Hub upload.
4. Hash the saved adapter and config; record dataset, prompt, recipe, source revision and dependency digests. Test adapter reload.
5. Evaluate the trained adapter on the same cases, preserving all outputs and missing-case accounting. Human review evaluates utility and identity; saying Kova alone does not establish success.
6. Preserve results, deallocate and verify resource state, then decide whether an Azure serving trial is justified.

## Azure publication boundary

After successful evaluation, prepare a separately reviewable private Azure artifact/serving plan with exact artifact digest, storage/access details, running cost, health checks and rollback. Public deployment and KovaGPT production traffic require their own verified cutover; a request to host the model is not evidence those gates passed. Preserve working application routes.

Kova is the derivative model's product identity. Preserve upstream license and lineage records and answer explicit technical-provenance questions truthfully. Do not describe the upstream foundation weights as trained from scratch by Kova.
