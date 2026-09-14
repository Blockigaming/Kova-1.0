# Kova 1.0

Kova is a self-hosted AI model project developed for KovaGPT. The first candidate uses the openly licensed `Qwen/Qwen3.8-27B` checkpoint as its base and applies Kova-owned post-training, evaluation, and serving code.

Kova is not a foundation model trained from scratch. Qwen attribution and its Apache 2.0 license must be retained. This repository contains public-safe source only: never commit credentials, private conversations, paid model outputs, private datasets, downloaded weights, adapters, or checkpoints.

## Current state

- Base revision pinned
- Offline planning and dataset validation available
- Paid training disabled
- No trained Kova checkpoint exists yet
- No KovaGPT production routing has changed

## Free checks

```sh
npm test
npm run preflight
npm run dataset:compile
npm run training:command
```

Passing these checks does not authorize GPU spending, training, deployment, or a production model replacement.

## RunPod Serverless plan

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

The public catalog reserves the Kova, Kova 5.6 Cosmo, Kova 5.6 Orion, and Kova 5.6
Nova names. Only the pinned Qwen3.8-27B Orion candidate is currently verified.
Cosmo and Nova remain blocked until exact upstream checkpoints, revisions, licenses,
and hardware requirements are verified.

The dataset compiler creates immutable, hashed ms-swift train and validation files.
The training command is a dry run by default and its execution path remains blocked
until cost authorization and single-GPU compatibility are separately verified.
