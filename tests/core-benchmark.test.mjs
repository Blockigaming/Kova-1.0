import assert from "node:assert/strict";
import { test } from "node:test";
import { summarizeCoreBenchmark } from "../scripts/summarize-core-benchmark.mjs";

const revision = "1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0";
const fp8Revision = "017b9c7af6b5689d5dd426a76e0bc077eb5ca20a";
const base = {
  request_id: "request-1",
  attempt_id: "attempt-1",
  worker_lifecycle_id: "lifecycle-1",
  lifecycle_closed: true,
  outcome: "success",
  model: "Qwen/Qwen3.8-27B",
  model_revision: revision,
  route_id: "instant",
  stage_id: "answer-1",
  public_response: true,
  cold_start: true,
  worker_start_ms: 1000,
  model_load_ms: 2000,
  queue_ms: 50,
  inference_ms: 2000,
  attributed_idle_timeout_ms: 5000,
  time_to_first_token_ms: 500,
  input_tokens: 1000,
  output_tokens: 500,
  gpu_rate_per_second_usd: 0.001,
  measurement_source: "server_provider_runtime",
};

const warmAttempt = (overrides) => ({
  ...base,
  cold_start: false,
  worker_start_ms: 0,
  model_load_ms: 0,
  lifecycle_closed: false,
  attributed_idle_timeout_ms: 0,
  ...overrides,
});

test("Core benchmark prices complete RunPod worker lifecycles", () => {
  const result = summarizeCoreBenchmark([base]);
  const record = result.records[0];
  assert.equal(record.startup_cost_usd, 0.003);
  assert.equal(record.inference_cost_usd, 0.002);
  assert.equal(record.idle_cost_usd, 0.005);
  assert.equal(record.compute_cost_usd, 0.01);
  assert.equal(result.provider, "runpod_serverless");
  assert.equal(result.cost_scope, "runpod_compute_only_excludes_storage_app_tools_payment_and_taxes");
});

test("Core benchmark separates candidate revisions and routes", () => {
  const result = summarizeCoreBenchmark([
    base,
    {
      ...base,
      request_id: "request-2",
      attempt_id: "attempt-2",
      worker_lifecycle_id: "lifecycle-2",
      model: "Qwen/Qwen3.8-27B-FP8",
      model_revision: fp8Revision,
      route_id: "medium",
      stage_id: "verification-1",
    },
  ]);
  assert.equal(Object.keys(result.by_model).length, 2);
  assert.equal(result.by_model[`Qwen/Qwen3.8-27B@${revision}`].by_route.instant.attempts, 1);
  assert.equal(result.by_model[`Qwen/Qwen3.8-27B-FP8@${fp8Revision}`].by_route.medium.attempts, 1);
});

test("Core benchmark attributes failed retries and one idle tail to the logical request", () => {
  const result = summarizeCoreBenchmark([
    {
      ...base,
      attempt_id: "failed",
      outcome: "failed",
      lifecycle_closed: false,
      attributed_idle_timeout_ms: 0,
      inference_ms: 1000,
      output_tokens: 0,
      time_to_first_token_ms: 0,
    },
    warmAttempt({
      attempt_id: "success",
      lifecycle_closed: true,
      attributed_idle_timeout_ms: 5000,
      inference_ms: 1000,
    }),
  ]);
  const group = result.by_model[`Qwen/Qwen3.8-27B@${revision}`].by_route.instant;
  assert.equal(group.successful_requests, 1);
  assert.equal(group.failed_attempts, 1);
  assert.equal(group.worker_lifecycles, 1);
  assert.equal(group.average_compute_cost_per_successful_request_usd, 0.01);
});

test("Core request is not successful when only a private stage succeeded", () => {
  const result = summarizeCoreBenchmark([{
    ...base, route_id: "medium", stage_id: "planning-1", public_response: false,
  }]);
  const group = result.by_model[`Qwen/Qwen3.8-27B@${revision}`].by_route.medium;
  assert.equal(group.successful_requests, 0);
  assert.equal(group.average_compute_cost_per_successful_request_usd, null);
});

test("Core request succeeds only after every declared route stage succeeds", () => {
  const records = [
    {
      ...base,
      attempt_id: "planning",
      route_id: "medium",
      stage_id: "planning-1",
      public_response: false,
      lifecycle_closed: false,
      attributed_idle_timeout_ms: 0,
    },
    warmAttempt({attempt_id: "answer", route_id: "medium", stage_id: "answer-1", public_response: false}),
    warmAttempt({
      attempt_id: "verification",
      route_id: "medium",
      stage_id: "verification-1",
      lifecycle_closed: true,
      attributed_idle_timeout_ms: 5000,
    }),
  ];
  const group = summarizeCoreBenchmark(records)
    .by_model[`Qwen/Qwen3.8-27B@${revision}`].by_route.medium;
  assert.equal(group.successful_requests, 1);
});

test("Core benchmark rejects retries that cross a model revision or route", () => {
  assert.throws(() => summarizeCoreBenchmark([
    {...base, lifecycle_closed: false, attributed_idle_timeout_ms: 0},
    {
      ...base,
      attempt_id: "retry",
      worker_lifecycle_id: "lifecycle-2",
      model: "Qwen/Qwen3.8-27B-FP8",
      model_revision: fp8Revision,
    },
  ]), /mixes model revision or route/);
  assert.throws(() => summarizeCoreBenchmark([
    {...base, lifecycle_closed: false, attributed_idle_timeout_ms: 0},
    {
      ...base,
      attempt_id: "retry",
      worker_lifecycle_id: "lifecycle-2",
      route_id: "medium",
      stage_id: "verification-1",
    },
  ]), /mixes model revision or route/);
});

test("Core benchmark validates stage visibility against Chat and Work DAGs", () => {
  assert.throws(() => summarizeCoreBenchmark([{
    ...base, route_id: "max", stage_id: "planning-1", public_response: true,
  }]), /public_response does not match route DAG/);
  const result = summarizeCoreBenchmark([{
    ...base, route_id: "work:cosmo:light", stage_id: "answer-1",
  }]);
  assert.equal(
    result.by_model[`Qwen/Qwen3.8-27B@${revision}`].by_route["work:cosmo:light"].successful_requests,
    1,
  );
});

test("Core benchmark rejects incomplete lifecycle attribution", () => {
  assert.throws(() => summarizeCoreBenchmark([{
    ...base, lifecycle_closed: false, attributed_idle_timeout_ms: 5000,
  }]), /open lifecycle contains idle-tail attribution/);
  assert.throws(() => summarizeCoreBenchmark([
    {...base, lifecycle_closed: false, attributed_idle_timeout_ms: 0},
  ]), /exactly one closed-tail attribution/);
  assert.throws(() => summarizeCoreBenchmark([
    base,
    warmAttempt({request_id: "request-2", attempt_id: "attempt-2", lifecycle_closed: true}),
  ]), /exactly one closed-tail attribution/);
});

test("Core benchmark rejects unverified revisions, zero rates, and impossible timing", () => {
  assert.throws(() => summarizeCoreBenchmark([{...base, model: "attacker/model"}]), /unverified model revision/);
  assert.throws(() => summarizeCoreBenchmark([{...base, model_revision: "0".repeat(40)}]), /unverified model revision/);
  assert.throws(() => summarizeCoreBenchmark([{...base, gpu_rate_per_second_usd: 0}]), /gpu_rate/);
  assert.throws(() => summarizeCoreBenchmark([{...base, time_to_first_token_ms: 3000}]), /first token exceeds inference/);
});
