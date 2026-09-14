import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

const required = [
  "request_id", "attempt_id", "outcome", "cold_start", "reasoning_effort", "worker_start_ms",
  "model_load_ms", "queue_ms", "inference_ms", "idle_timeout_ms", "input_tokens",
  "output_tokens", "gpu_rate_per_second_usd",
];
const numericFields = [
  "worker_start_ms", "model_load_ms", "queue_ms", "inference_ms", "idle_timeout_ms",
  "input_tokens", "output_tokens", "gpu_rate_per_second_usd",
];
const allowedEfforts = new Set(["low", "medium", "high", "xhigh"]);
const allowedOutcomes = new Set(["success", "failed"]);

function average(items, key) {
  return items.length ? items.reduce((sum, item) => sum + item[key], 0) / items.length : null;
}

function summarizeGroup(records) {
  const requests = new Map();
  for (const record of records) {
    const request = requests.get(record.request_id) ?? {
      request_id: record.request_id,
      attempts: [],
      total_compute_cost_usd: 0,
      success: false,
      cold_start: false,
    };
    request.attempts.push(record.attempt_id);
    request.total_compute_cost_usd += record.compute_cost_usd;
    request.success ||= record.outcome === "success";
    request.cold_start ||= record.cold_start;
    requests.set(record.request_id, request);
  }

  const logicalRequests = [...requests.values()];
  const successful = logicalRequests.filter((request) => request.success);
  const failed = logicalRequests.filter((request) => !request.success);
  const coldAttempts = records.filter((record) => record.cold_start);
  const totalComputeCost = records.reduce((sum, record) => sum + record.compute_cost_usd, 0);
  const totalStartupCost = records.reduce((sum, record) => sum + record.startup_cost_usd, 0);
  const coldComputeCost = coldAttempts.reduce((sum, record) => sum + record.compute_cost_usd, 0);
  const coldStartupCost = coldAttempts.reduce((sum, record) => sum + record.startup_cost_usd, 0);
  return {
    attempts: records.length,
    logical_requests: logicalRequests.length,
    successful_requests: successful.length,
    failed_requests: failed.length,
    retry_attempts: records.length - logicalRequests.length,
    total_attributable_compute_cost_usd: totalComputeCost,
    average_compute_cost_per_successful_request_usd: successful.length ? totalComputeCost / successful.length : null,
    average_cold_startup_cost_usd: average(coldAttempts, "startup_cost_usd"),
    cold_start_overhead_percent_of_cold_compute: coldComputeCost > 0 ? coldStartupCost / coldComputeCost * 100 : null,
    startup_share_of_total_compute_percent: totalComputeCost > 0 ? totalStartupCost / totalComputeCost * 100 : null,
    average_output_tokens_per_attempt: average(records, "output_tokens"),
    requests: logicalRequests,
  };
}

export function summarizeBenchmark(records) {
  if (!Array.isArray(records) || records.length === 0) throw new Error("benchmark requires records");
  const seenAttempts = new Set();
  const requestEfforts = new Map();
  for (const [index, record] of records.entries()) {
    for (const key of required) {
      if (!(key in record)) throw new Error(`record ${index} missing ${key}`);
    }
    if (typeof record.request_id !== "string" || !record.request_id) throw new Error(`record ${index} invalid request_id`);
    if (typeof record.attempt_id !== "string" || !record.attempt_id || seenAttempts.has(record.attempt_id)) {
      throw new Error(`record ${index} invalid or duplicate attempt_id`);
    }
    seenAttempts.add(record.attempt_id);
    if (!allowedOutcomes.has(record.outcome)) throw new Error(`record ${index} invalid outcome`);
    if (typeof record.cold_start !== "boolean") throw new Error(`record ${index} invalid cold_start`);
    if (!allowedEfforts.has(record.reasoning_effort)) throw new Error(`record ${index} invalid reasoning_effort`);
    const priorEffort = requestEfforts.get(record.request_id);
    if (priorEffort && priorEffort !== record.reasoning_effort) throw new Error(`request ${record.request_id} mixes reasoning_effort`);
    requestEfforts.set(record.request_id, record.reasoning_effort);
    for (const key of numericFields) {
      if (!Number.isFinite(record[key]) || record[key] < 0) throw new Error(`record ${index} invalid ${key}`);
    }
    if (record.gpu_rate_per_second_usd <= 0) throw new Error(`record ${index} invalid gpu_rate_per_second_usd`);
  }

  const priced = records.map((record) => {
    const startupMs = record.worker_start_ms + record.model_load_ms;
    const billableMs = startupMs + record.inference_ms + record.idle_timeout_ms;
    const rate = record.gpu_rate_per_second_usd;
    return {
      ...record,
      startup_ms: startupMs,
      billable_ms: billableMs,
      startup_cost_usd: startupMs / 1000 * rate,
      compute_cost_usd: billableMs / 1000 * rate,
    };
  });
  const byEffort = {};
  for (const effort of allowedEfforts) {
    const samples = priced.filter((record) => record.reasoning_effort === effort);
    if (samples.length) byEffort[effort] = summarizeGroup(samples);
  }

  return {
    schema_version: 2,
    attempts: priced.length,
    by_reasoning_effort: byEffort,
    records: priced,
  };
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const input = process.argv[2];
  if (!input) throw new Error("usage: npm run benchmark:summarize -- benchmark.json");
  process.stdout.write(`${JSON.stringify(summarizeBenchmark(JSON.parse(readFileSync(input, "utf8"))), null, 2)}\n`);
}
