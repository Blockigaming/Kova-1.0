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

The dataset compiler creates immutable, hashed ms-swift train and validation files.
The training command is a dry run by default and its execution path remains blocked
until cost authorization and single-GPU compatibility are separately verified.
