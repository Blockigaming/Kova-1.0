import assert from "node:assert/strict";
import { test } from "node:test";
import { summarizeCoreBenchmark } from "../scripts/summarize-core-benchmark.mjs";

const base = {
  request_id: "request-1",
  attempt_id: "attempt-1",
  outcome: "success",
  model: "@cf/qwen/qwen3.8-27b",
  provider_model_version: "fingerprint-1",
  route_id: "instant",
  stage_id: "answer-1",
  input_tokens: 1_000_000,
  output_tokens: 1_000_000,
  latency_ms: 2000,
  time_to_first_token_ms: 500,
  measurement_source: "cloudflare_response_usage_and_server_clock",
  public_response: true,
};

test("Core benchmark uses the verified candidate token prices", () => {
  const result = summarizeCoreBenchmark([base]);
  const record = result.records[0];
  assert.ok(Math.abs(record.inference_cost_usd - 3.65) < 1e-12);
  assert.equal(result.cost_scope, "cloudflare_inference_only_not_total_attributable_customer_cost");
});

test("Core benchmark separates model versions and routes", () => {
  const result = summarizeCoreBenchmark([
    base,
    {...base, request_id: "request-2", attempt_id: "attempt-2", provider_model_version: "fingerprint-2", route_id: "medium"},
  ]);
  assert.equal(Object.keys(result.by_model).length, 2);
  assert.equal(result.by_model["@cf/qwen/qwen3.8-27b@fingerprint-1"].by_route.instant.attempts, 1);
  assert.equal(result.by_model["@cf/qwen/qwen3.8-27b@fingerprint-2"].by_route.medium.attempts, 1);
});

test("Core benchmark attributes failed attempt usage to successful requests", () => {
  const result = summarizeCoreBenchmark([
    {...base, attempt_id: "failed", outcome: "failed", input_tokens: 1000, output_tokens: 0, public_response: false},
    {...base, attempt_id: "success", input_tokens: 1000, output_tokens: 1000},
  ]);
  const group = result.by_model["@cf/qwen/qwen3.8-27b@fingerprint-1"].by_route.instant;
  const expected = 2000 / 1_000_000 * 0.45 + 1000 / 1_000_000 * 3.2;
  assert.equal(group.successful_requests, 1);
  assert.equal(group.failed_attempts, 1);
  assert.ok(Math.abs(group.average_inference_cost_per_successful_request_usd - expected) < 1e-12);
});

test("Core request is not successful when only a private stage succeeded", () => {
  const result = summarizeCoreBenchmark([{...base, public_response: false}]);
  const group = result.by_model["@cf/qwen/qwen3.8-27b@fingerprint-1"].by_route.instant;
  assert.equal(group.successful_requests, 0);
  assert.equal(group.average_inference_cost_per_successful_request_usd, null);
});

test("Core benchmark rejects unverified models, missing versions, and impossible timing", () => {
  assert.throws(() => summarizeCoreBenchmark([{...base, model: "@cf/attacker/model"}]), /unverified model/);
  assert.throws(() => summarizeCoreBenchmark([{...base, provider_model_version: ""}]), /provider_model_version/);
  assert.throws(() => summarizeCoreBenchmark([{...base, time_to_first_token_ms: 3000}]), /first token exceeds latency/);
});
