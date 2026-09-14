import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

const required = [
  "request_id", "cold_start", "worker_start_ms", "model_load_ms", "queue_ms",
  "inference_ms", "idle_timeout_ms", "input_tokens", "output_tokens",
  "gpu_rate_per_second_usd",
];

export function summarizeBenchmark(records) {
  if (!Array.isArray(records) || records.length === 0) throw new Error("benchmark requires records");
  for (const [index, record] of records.entries()) {
    for (const key of required) {
      if (!(key in record)) throw new Error(`record ${index} missing ${key}`);
    }
    for (const key of required.slice(2)) {
      if (!Number.isFinite(record[key]) || record[key] < 0) throw new Error(`record ${index} invalid ${key}`);
    }
  }

  const priced = records.map((record) => {
    const billableMs = record.worker_start_ms + record.model_load_ms + record.inference_ms + record.idle_timeout_ms;
    return { ...record, billable_ms: billableMs, compute_cost_usd: billableMs / 1000 * record.gpu_rate_per_second_usd };
  });
  const warm = priced.filter((record) => !record.cold_start);
  const cold = priced.filter((record) => record.cold_start);
  const average = (items, key) => items.length ? items.reduce((sum, item) => sum + item[key], 0) / items.length : null;
  const warmCost = average(warm, "compute_cost_usd");
  const coldCost = average(cold, "compute_cost_usd");

  return {
    schema_version: 1,
    samples: priced.length,
    cold_samples: cold.length,
    warm_samples: warm.length,
    average_cold_compute_cost_usd: coldCost,
    average_warm_compute_cost_usd: warmCost,
    cold_start_cost_increase_percent: coldCost !== null && warmCost > 0 ? (coldCost / warmCost - 1) * 100 : null,
    average_output_tokens: average(priced, "output_tokens"),
    records: priced,
  };
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const input = process.argv[2];
  if (!input) throw new Error("usage: npm run benchmark:summarize -- benchmark.json");
  process.stdout.write(`${JSON.stringify(summarizeBenchmark(JSON.parse(readFileSync(input, "utf8"))), null, 2)}\n`);
}
