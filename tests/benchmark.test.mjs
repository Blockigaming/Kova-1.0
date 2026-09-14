import assert from "node:assert/strict";
import { test } from "node:test";
import { summarizeBenchmark } from "../scripts/summarize-benchmark.mjs";

const base = {
  worker_start_ms: 0, model_load_ms: 0, queue_ms: 5, idle_timeout_ms: 5000,
  input_tokens: 100, output_tokens: 200, gpu_rate_per_second_usd: 0.001, reasoning_effort: "low",
};

test("benchmark reports measured cold-start increase", () => {
  const result = summarizeBenchmark([
    { ...base, request_id: "cold", cold_start: true, worker_start_ms: 10000, model_load_ms: 20000, inference_ms: 10000 },
    { ...base, request_id: "warm", cold_start: false, inference_ms: 10000 },
  ]);
  assert.equal(result.by_reasoning_effort.low.average_cold_compute_cost_usd, 0.045);
  assert.equal(result.by_reasoning_effort.low.average_warm_compute_cost_usd, 0.015);
  assert.ok(Math.abs(result.by_reasoning_effort.low.cold_start_cost_increase_percent - 200) < 1e-9);
});

test("benchmark separates effort levels and rejects non-Boolean cold flags", () => {
  const result = summarizeBenchmark([
    { ...base, request_id: "low", cold_start: false, inference_ms: 1000 },
    { ...base, request_id: "high", cold_start: false, reasoning_effort: "xhigh", inference_ms: 9000 },
  ]);
  assert.equal(result.by_reasoning_effort.low.samples, 1);
  assert.equal(result.by_reasoning_effort.xhigh.samples, 1);
  assert.throws(() => summarizeBenchmark([
    { ...base, request_id: "bad", cold_start: "false", inference_ms: 1000 },
  ]), /invalid cold_start/);
});

test("benchmark rejects incomplete telemetry", () => {
  assert.throws(() => summarizeBenchmark([{ request_id: "bad" }]), /missing cold_start/);
});
