import assert from "node:assert/strict";
import { test } from "node:test";
import { summarizeBenchmark } from "../scripts/summarize-benchmark.mjs";

const base = {
  attempt_id: "attempt-1", outcome: "success", worker_start_ms: 0, model_load_ms: 0,
  queue_ms: 5, idle_timeout_ms: 5000, input_tokens: 100, output_tokens: 200,
  gpu_rate_per_second_usd: 0.001, reasoning_effort: "low",
};

test("benchmark measures cold startup directly instead of comparing unmatched workloads", () => {
  const result = summarizeBenchmark([
    { ...base, request_id: "cold", attempt_id: "cold-1", cold_start: true, worker_start_ms: 10000, model_load_ms: 20000, inference_ms: 10000 },
    { ...base, request_id: "warm", attempt_id: "warm-1", cold_start: false, inference_ms: 1000, output_tokens: 10 },
  ]);
  const low = result.by_reasoning_effort.low;
  assert.equal(low.average_cold_startup_cost_usd, 0.03);
  assert.ok(Math.abs(low.cold_start_overhead_percent_of_cold_compute - (30 / 45 * 100)) < 1e-9);
  assert.equal("cold_start_cost_increase_percent" in low, false);
});

test("benchmark attributes retries and fully failed requests to cost per success", () => {
  const result = summarizeBenchmark([
    { ...base, request_id: "eventual", attempt_id: "try-1", outcome: "failed", cold_start: true, inference_ms: 1000 },
    { ...base, request_id: "eventual", attempt_id: "try-2", outcome: "success", cold_start: false, inference_ms: 1000 },
    { ...base, request_id: "failed", attempt_id: "try-3", outcome: "failed", cold_start: false, inference_ms: 1000 },
  ]);
  const low = result.by_reasoning_effort.low;
  assert.equal(low.attempts, 3);
  assert.equal(low.logical_requests, 2);
  assert.equal(low.successful_requests, 1);
  assert.equal(low.failed_requests, 1);
  assert.equal(low.retry_attempts, 1);
  assert.ok(Math.abs(low.average_compute_cost_per_successful_request_usd - 0.018) < 1e-12);
});

test("benchmark separates effort levels and rejects malformed identity fields", () => {
  const result = summarizeBenchmark([
    { ...base, request_id: "low", attempt_id: "low-1", cold_start: false, inference_ms: 1000 },
    { ...base, request_id: "high", attempt_id: "high-1", cold_start: false, reasoning_effort: "high", inference_ms: 9000 },
  ]);
  assert.equal(result.by_reasoning_effort.low.attempts, 1);
  assert.equal(result.by_reasoning_effort.high.attempts, 1);
  assert.throws(() => summarizeBenchmark([
    { ...base, request_id: "bad", attempt_id: "bad-1", cold_start: "false", inference_ms: 1000 },
  ]), /invalid cold_start/);
  assert.throws(() => summarizeBenchmark([
    { ...base, request_id: "bad", attempt_id: "bad-1", cold_start: false, inference_ms: 1000 },
    { ...base, request_id: "bad", attempt_id: "bad-2", cold_start: false, reasoning_effort: "high", inference_ms: 1000 },
  ]), /mixes reasoning_effort/);
});

test("benchmark rejects incomplete telemetry, duplicate attempts, and zero GPU rate", () => {
  assert.throws(() => summarizeBenchmark([{ request_id: "bad" }]), /missing attempt_id/);
  assert.throws(() => summarizeBenchmark([
    { ...base, request_id: "a", cold_start: false, inference_ms: 1000 },
    { ...base, request_id: "b", cold_start: false, inference_ms: 1000 },
  ]), /duplicate attempt_id/);
  assert.throws(() => summarizeBenchmark([
    { ...base, request_id: "bad", attempt_id: "zero", cold_start: false, inference_ms: 1000, gpu_rate_per_second_usd: 0 },
  ]), /invalid gpu_rate/);
});
