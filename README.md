# Kova 1.0

Kova is the AI system developed for KovaGPT. The target architecture has two
physical RunPod Serverless inference endpoints while preserving the existing
Azure application plane: one benchmark-selected Kova Core endpoint for Auto
through Max and non-Ultra Work, plus a separate scale-to-zero Kova Ultra endpoint.
Cloudflare remains the DNS, CDN, WAF, and DDoS edge; it is not an inference host.

Kova is not a foundation model trained from scratch. Cosmo, Orion, and Nova are behavior and compute profiles, not claims of separately trained foundation weights. The active provider, upstream model, and license must be disclosed truthfully when asked. This repository contains public-safe source only: never commit credentials, private conversations, paid model outputs, private datasets, downloaded weights, adapters, or checkpoints.

## Current state

- Two-engine provider and route contracts defined
- One shared RunPod Core endpoint and one RunPod Ultra endpoint are source-defined; neither exists yet
- BF16 and official FP8 Qwen3.8-27B Core candidates are pinned; no winner is selected
- Three self-hosted Qwen candidates remain pinned for evaluation
- Offline planning and dataset validation available
- Paid training disabled
- No trained Kova checkpoint exists yet
- No KovaGPT production routing has changed
- Progress is 22% under the product-complete definition; zero of 25 target routes are live
- Deterministic Kova Auto baseline implemented with Free-plan and Ultra-budget gates
- Source-only RunPod Core multi-pass request planner and lifecycle-cost summarizer implemented
- Source-only Ultra specialist, disagreement-check, judge, conditional-debate, and synthesis planner implemented
- Reproducible offline contract evaluation covers all 25 target routes without provider calls

## Product-complete target

Kova Auto sits above six Chat modes: Instant, Medium, High, Extra High, Max,
and Ultra. Instant through Max use increasing compute policies over one Kova
Core model. Ultra changes architecture to dynamic specialists, a disagreement
check, a judge, and synthesis. Work exposes Kova 5.6 Cosmo, Kova 5.6 Orion,
and Kova 5.6 Nova, each with Light through Ultra effort. Instant responds directly. Deeper modes
may provide concise, truthful progress updates and ask focused questions when
missing information would materially change the result. Activity text is never
hidden chain-of-thought and may only describe events that actually occurred.

## Free checks

```sh
npm test
npm run preflight
npm run evaluate:offline
npm run dataset:compile
npm run training:command
```

Passing these checks does not authorize GPU spending, training, deployment, or a production model replacement.

`npm run benchmark:candidate:summarize -- benchmark.json` summarizes isolated
model-candidate attempts only. It explicitly cannot claim Core or Ultra route
completion and cannot support customer route pricing. It never calls RunPod.

`npm run benchmark:core:summarize -- core-benchmark.json` prices complete recorded
RunPod worker lifecycles and separates results by pinned model revision, GPU type
and count, serving engine, endpoint type, container digest, and Kova route. A
shutdown observation is recorded separately from request attempts. It requires one
measured cold start and one measured shutdown tail per lifecycle, then shares that
overhead equally across the logical requests served during the lifecycle. This lets
one warm Core worker serve different routes without losing or duplicating cost. It reports RunPod compute
only, not a publishable customer price; Azure, tools, storage, payment processing,
taxes, and other attributable costs must still be included.
The request planner also requires a trusted provider tokenizer count, binds only
server-recorded but untrusted prior model artifacts, reserves their worst-case token ceilings,
and rejects any operation whose bound prompt plus output ceiling could exceed the
candidate context. The executor must recount the fully bound request before inference.

The source-only benchmark worker validates request IDs, roles, reasoning effort,
aggregate prompt size, token limits, trusted Kova identity, and measured telemetry.
It rebuilds the selected Core stage from the server policy, binds exactly the
server-recorded outputs required by that stage's DAG, recounts the fully bound prompt,
and rejects mismatched stage limits or missing artifacts. Public stages must return
real streaming chunks; the worker assembles content, tool-call fragments, and usage
before sanitizing the result and measures first-visible-delta latency with its
monotonic clock. That measurement is preserved if a later stream chunk fails;
attempts with no visible public delta and all private non-stream stages record TTFT
as unavailable (`null`) instead of inventing a value. Private stages use non-streaming responses. The worker pins its
candidate model server-side and fails closed if hidden reasoning appears in a separate
field or embedded `<think>` block. The unquantized hardware matrix starts at 80 GB VRAM. No container image
is selected until a compatible image digest and Qwen3.8 serving path are verified.

## Provider plan

Azure remains the application platform for routing, tools, billing enforcement,
and streaming. New providers must be added behind the existing provider abstraction;
existing Azure deployments are not deleted before a verified canary and cutover.

The final architecture decision rejects Cloudflare Workers AI as the primary
inference backend after user-reported inconsistent interactive latency. That report
is recorded as a product decision, not reproducible benchmark telemetry. Cloudflare
continues to serve only the edge roles.

Both inference engines target RunPod Serverless. Kova Core has two source-verified,
hardware-unbenchmarked candidates representing the same Qwen3.8-27B model family:
the original BF16 checkpoint and the official fine-grained FP8 checkpoint. Model,
quantization, GPU, serving engine, endpoint type, and container digest all remain
unselected until reproducible quality, latency, streaming, memory, and lifecycle-cost
benchmarks pass. Qwen documents a native 262,144-token context, `low`, `medium`, and
`xhigh` reasoning effort, and support for vLLM and SGLang.

Kova Auto currently uses deterministic server rules. Free is capped to Instant;
Plus can route through Max; Ultra additionally requires Pro entitlement, explicit
runtime authorization, and sufficient remaining request budget. This classifier is
tested but not production-routed.

### RunPod Core and Ultra

The checked-in RunPod configuration is planning-only and fail-closed. It reserves
`kova-core` and `kova-ultra`, each with Flex workers, zero active workers, a
one-worker cost cap, five-second idle timeout, required streaming, FlashBoot, and
cached-model loading. Neither endpoint has been created. Startup, request execution,
the post-request idle timeout, storage, retries, payment processing, and applicable
usage taxes must all be measured before customer prices are published.

RunPod's standard account billing is prepaid-credit based even though Serverless
compute is metered per second. This plan explicitly disables auto-pay and automatic
credit reloads: there is no flat-rate compute plan, but a manual prepaid balance is
still required by RunPod. Deposited credits are non-refundable. A true standard
postpaid card charge after usage is not represented as supported.

The target gross margin is 42.6%, using:

```text
customer price = attributable cost / 0.574
```

This formula targets 42.6% before rounding. Realized margin must be measured from
actual usage and recalibrated; it cannot be guaranteed from GPU list prices alone.

The public catalog reserves Kova Auto, Kova 5.6 Cosmo, Kova 5.6 Orion, Kova 5.6
Nova, and Kova Ultra. None is live. Public profile names describe actual compute and
orchestration differences while sharing Core weights through Max; they never imply
separate foundation models.

The offline evaluator resolves all 25 Auto, Chat, and Work route contracts through
the actual router; builds provider-free Core or Ultra plans; verifies DAG, identity,
disclosure, source-grounding, activity, and worst-case token-budget invariants; and
proves that Cosmo, Orion, and Nova Work profiles have distinct server-controlled
behavior instructions. It evaluates no real model output and therefore leaves all
quality, factuality, latency, cost, and release gates blocked.

The dataset compiler creates immutable, hashed ms-swift train and validation files.
The training command is a dry run by default and its execution path remains blocked
until cost authorization and single-GPU compatibility are separately verified.
