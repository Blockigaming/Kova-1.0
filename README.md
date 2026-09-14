# Kova 1.0

Kova is the AI system developed for KovaGPT. The target architecture has two physical inference engines while preserving the existing Azure application plane: a benchmark-selected Kova Core on Cloudflare Workers AI for Auto through Max, and a scale-to-zero Kova Ultra orchestrator on RunPod Serverless.

Kova is not a foundation model trained from scratch. Cosmo, Orion, and Nova are behavior and compute profiles, not claims of separately trained foundation weights. The active provider, upstream model, and license must be disclosed truthfully when asked. This repository contains public-safe source only: never commit credentials, private conversations, paid model outputs, private datasets, downloaded weights, adapters, or checkpoints.

## Current state

- Two-engine provider and route contracts defined
- Three Cloudflare Core candidates documented; no winner selected
- Three self-hosted Qwen candidates remain pinned for evaluation
- Offline planning and dataset validation available
- Paid training disabled
- No trained Kova checkpoint exists yet
- No KovaGPT production routing has changed
- Progress is 15% under the product-complete definition; zero of 25 target routes are live

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
npm run dataset:compile
npm run training:command
```

Passing these checks does not authorize GPU spending, training, deployment, or a production model replacement.

`npm run benchmark:summarize -- benchmark.json` converts measured cold and warm
worker telemetry into actual compute cost and cold-start percentage. It never calls
RunPod. Pricing remains blocked until real endpoint samples exist.

The source-only benchmark worker validates request IDs, roles, reasoning effort,
aggregate prompt size, token limits, trusted Kova identity, and measured telemetry;
pins its candidate model server-side; and fails closed if hidden reasoning appears
in a separate field or embedded `<think>` block. The unquantized hardware matrix starts at 80 GB VRAM. No container image
is selected until a compatible image digest and Qwen3.8 serving path are verified.

## Provider plan

Azure remains the application platform for routing, tools, billing enforcement,
and streaming. New providers must be added behind the existing provider abstraction;
existing Azure deployments are not deleted before a verified canary and cutover.

Cloudflare Workers AI is the planned Kova Core provider. The permanent Core model
is not selected until quality, latency, streaming, tool use, context, hallucination,
and cost benchmarks pass. The current candidate list includes Cloudflare-hosted
Qwen3.8-27B, Qwen3-30B-A3B-FP8, and GLM-5.3-Flash.

Cloudflare inference is usage-metered and includes 10,000 free neurons per day,
but production usage introduces a billing tradeoff: exceeding the free allocation
requires the Workers Paid plan (currently a $5 monthly minimum) or prepaid AI
Gateway credits. The architecture therefore does not claim to satisfy both “no
flat fee” and “no prepaid credits.” That choice remains blocked for explicit review.
See the official [Workers AI pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/)
and [Workers plan pricing](https://developers.cloudflare.com/workers/platform/pricing/).

### RunPod Ultra

The checked-in RunPod configuration is planning-only and fail-closed. It uses Flex
workers with zero active workers so inference can scale to zero. Startup, request
execution, the post-request idle timeout, storage, retries, payment processing, and
applicable usage taxes must all be measured before customer prices are published.

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

The dataset compiler creates immutable, hashed ms-swift train and validation files.
The training command is a dry run by default and its execution path remains blocked
until cost authorization and single-GPU compatibility are separately verified.
