import assert from "node:assert/strict";
import { test } from "node:test";
import { summarizeBenchmark } from "../scripts/summarize-benchmark.mjs";

const base = {
  worker_start_ms: 0, model_load_ms: 0, queue_ms: 5, idle_timeout_ms: 5000,
  input_tokens: 100, output_tokens: 200, gpu_rate_per_second_usd: 0.001,
};

test("benchmark reports measured cold-start increase", () => {
  const result = summarizeBenchmark([
    { ...base, request_id: "cold", cold_start: true, worker_start_ms: 10000, model_load_ms: 20000, inference_ms: 10000 },
    { ...base, request_id: "warm", cold_start: false, inference_ms: 10000 },
  ]);
  assert.equal(result.average_cold_compute_cost_usd, 0.045);
  assert.equal(result.average_warm_compute_cost_usd, 0.015);
  assert.ok(Math.abs(result.cold_start_cost_increase_percent - 200) < 1e-9);
});

test("benchmark rejects incomplete telemetry", () => {
  assert.throws(() => summarizeBenchmark([{ request_id: "bad" }]), /missing cold_start/);
});
