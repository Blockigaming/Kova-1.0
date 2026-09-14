import assert from "node:assert/strict";
import { test } from "node:test";
import { summarizeBenchmark } from "../scripts/summarize-benchmark.mjs";

const base = {
  benchmark_scope: "isolated_model_candidate",
  attempt_id: "attempt-1", outcome: "success", worker_start_ms: 0, model_load_ms: 0,
  queue_ms: 5, idle_timeout_ms: 5000, input_tokens: 100, output_tokens: 200,
  gpu_rate_per_second_usd: 0.001, reasoning_effort: "low",
  model: "Qwen/Qwen3.8-27B", model_revision: "1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0",
  measurement_source: "server_provider_runtime",
};

const group = (result, effort = "low", model = base.model, revision = base.model_revision) =>
  result.by_model[`${model}@${revision}`].by_reasoning_effort[effort];

test("benchmark measures cold startup directly instead of comparing unmatched workloads", () => {
  const result = summarizeBenchmark([
    { ...base, request_id: "cold", attempt_id: "cold-1", cold_start: true, worker_start_ms: 10000, model_load_ms: 20000, inference_ms: 10000 },
    { ...base, request_id: "warm", attempt_id: "warm-1", cold_start: false, inference_ms: 1000, output_tokens: 10 },
  ]);
  const low = group(result);
  assert.equal(low.average_cold_startup_cost_usd, 0.03);
  assert.ok(Math.abs(low.cold_start_overhead_percent_of_cold_compute - (30 / 45 * 100)) < 1e-9);
  assert.equal("cold_start_cost_increase_percent" in low, false);
});

test("candidate benchmark attributes failed attempts without claiming route completion", () => {
  const result = summarizeBenchmark([
    { ...base, request_id: "eventual", attempt_id: "try-1", outcome: "failed", cold_start: true, inference_ms: 1000 },
    { ...base, request_id: "eventual", attempt_id: "try-2", outcome: "success", cold_start: false, inference_ms: 1000 },
    { ...base, request_id: "failed", attempt_id: "try-3", outcome: "failed", cold_start: false, inference_ms: 1000 },
  ]);
  const low = group(result);
  assert.equal(low.attempts, 3);
  assert.equal(low.successful_candidate_attempts, 1);
  assert.equal(low.failed_candidate_attempts, 2);
  assert.ok(Math.abs(low.average_compute_cost_per_successful_candidate_attempt_usd - 0.018) < 1e-12);
  assert.equal(result.route_completion_claimed, false);
  assert.equal(result.ultra_route_completion_supported, false);
});

test("benchmark separates effort levels and rejects malformed identity fields", () => {
  const result = summarizeBenchmark([
    { ...base, request_id: "low", attempt_id: "low-1", cold_start: false, inference_ms: 1000 },
    { ...base, request_id: "xhigh", attempt_id: "xhigh-1", cold_start: false, reasoning_effort: "xhigh", inference_ms: 9000 },
  ]);
  assert.equal(group(result).attempts, 1);
  assert.equal(group(result, "xhigh").attempts, 1);
  assert.throws(() => summarizeBenchmark([
    { ...base, request_id: "bad", attempt_id: "bad-1", cold_start: "false", inference_ms: 1000 },
  ]), /invalid cold_start/);
  assert.throws(() => summarizeBenchmark([
    { ...base, request_id: "bad", attempt_id: "bad-1", cold_start: false, inference_ms: 1000 },
    { ...base, request_id: "bad", attempt_id: "bad-2", cold_start: false, reasoning_effort: "xhigh", inference_ms: 1000 },
  ]), /mixes model, revision, or reasoning_effort/);
});

test("benchmark separates models and revisions", () => {
  const otherRevision = "017b9c7af6b5689d5dd426a76e0bc077eb5ca20a";
  const result = summarizeBenchmark([
    { ...base, request_id: "base", attempt_id: "base-1", cold_start: false, inference_ms: 1000 },
    { ...base, request_id: "fp8", attempt_id: "fp8-1", cold_start: false, inference_ms: 1000, model: "Qwen/Qwen3.8-27B-FP8", model_revision: otherRevision },
  ]);
  assert.equal(Object.keys(result.by_model).length, 2);
  assert.equal(group(result).attempts, 1);
  assert.equal(group(result, "low", "Qwen/Qwen3.8-27B-FP8", otherRevision).attempts, 1);
});

test("benchmark rejects incomplete telemetry, duplicate attempts, and zero GPU rate", () => {
  assert.throws(() => summarizeBenchmark([{ benchmark_scope: "isolated_model_candidate", request_id: "bad" }]), /missing attempt_id/);
  assert.throws(() => summarizeBenchmark([
    { ...base, request_id: "a", cold_start: false, inference_ms: 1000 },
    { ...base, request_id: "b", cold_start: false, inference_ms: 1000 },
  ]), /duplicate attempt_id/);
  assert.throws(() => summarizeBenchmark([
    { ...base, request_id: "bad", attempt_id: "zero", cold_start: false, inference_ms: 1000, gpu_rate_per_second_usd: 0 },
  ]), /invalid gpu_rate/);
  assert.throws(() => summarizeBenchmark([
    { ...base, request_id: "bad", attempt_id: "route", cold_start: false, inference_ms: 1000, route_id: "ultra" },
  ]), /route telemetry is not valid/);
  assert.throws(() => summarizeBenchmark([
    { ...base, benchmark_scope: "ultra", request_id: "bad", attempt_id: "scope", cold_start: false, inference_ms: 1000 },
  ]), /invalid benchmark_scope/);
});
