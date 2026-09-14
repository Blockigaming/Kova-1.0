import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

const architecture = JSON.parse(readFileSync(new URL("../config/provider-architecture.v1.json", import.meta.url), "utf8"));
const core = architecture.engines.find((engine) => engine.id === "kova-core");
const candidates = new Map(core.candidate_models.map((candidate) => [candidate.model, candidate]));
const routes = new Set(["instant", "medium", "high", "extra-high", "max"]);
const outcomes = new Set(["success", "failed"]);
const required = [
  "request_id", "attempt_id", "outcome", "model", "provider_model_version", "route_id",
  "stage_id", "input_tokens", "output_tokens", "latency_ms", "time_to_first_token_ms",
  "measurement_source", "public_response",
];

const average = (records, key) => records.length
  ? records.reduce((total, record) => total + record[key], 0) / records.length
  : null;

function summarizeGroup(records) {
  const successfulAttempts = records.filter((record) => record.outcome === "success");
  const successfulPublicAttempts = successfulAttempts.filter((record) => record.public_response);
  const requestIds = new Set(records.map((record) => record.request_id));
  const successfulRequests = new Set(successfulPublicAttempts.map((record) => record.request_id));
  const totalCost = records.reduce((total, record) => total + record.inference_cost_usd, 0);
  return {
    attempts: records.length,
    logical_requests: requestIds.size,
    successful_requests: successfulRequests.size,
    failed_attempts: records.length - successfulAttempts.length,
    total_inference_cost_usd: totalCost,
    average_inference_cost_per_successful_request_usd: successfulRequests.size ? totalCost / successfulRequests.size : null,
    average_success_stage_latency_ms: average(successfulAttempts, "latency_ms"),
    average_public_time_to_first_token_ms: average(successfulPublicAttempts, "time_to_first_token_ms"),
    average_public_output_tokens: average(successfulPublicAttempts, "output_tokens"),
  };
}

export function summarizeCoreBenchmark(records) {
  if (!Array.isArray(records) || records.length === 0) throw new Error("Core benchmark requires records");
  const seenAttempts = new Set();
  for (const [index, record] of records.entries()) {
    for (const field of required) if (!(field in record)) throw new Error(`record ${index} missing ${field}`);
    for (const field of ["request_id", "attempt_id", "provider_model_version", "stage_id"]) {
      if (typeof record[field] !== "string" || !record[field]) throw new Error(`record ${index} invalid ${field}`);
    }
    if (seenAttempts.has(record.attempt_id)) throw new Error(`record ${index} duplicate attempt_id`);
    seenAttempts.add(record.attempt_id);
    if (!candidates.has(record.model)) throw new Error(`record ${index} unverified model`);
    if (!routes.has(record.route_id)) throw new Error(`record ${index} invalid route_id`);
    if (!outcomes.has(record.outcome)) throw new Error(`record ${index} invalid outcome`);
    if (typeof record.public_response !== "boolean") throw new Error(`record ${index} invalid public_response`);
    if (record.measurement_source !== "cloudflare_response_usage_and_server_clock") throw new Error(`record ${index} invalid measurement_source`);
    for (const field of ["input_tokens", "output_tokens", "latency_ms", "time_to_first_token_ms"]) {
      if (!Number.isFinite(record[field]) || record[field] < 0) throw new Error(`record ${index} invalid ${field}`);
    }
    if (record.time_to_first_token_ms > record.latency_ms) throw new Error(`record ${index} first token exceeds latency`);
  }

  const priced = records.map((record) => {
    const price = candidates.get(record.model);
    const inputCost = record.input_tokens / 1_000_000 * price.input_usd_per_million_tokens;
    const outputCost = record.output_tokens / 1_000_000 * price.output_usd_per_million_tokens;
    return {...record, inference_cost_usd: inputCost + outputCost};
  });
  const byModel = {};
  for (const record of priced) {
    const modelKey = `${record.model}@${record.provider_model_version}`;
    byModel[modelKey] ??= {model: record.model, provider_model_version: record.provider_model_version, by_route: {}};
  }
  for (const [modelKey, modelGroup] of Object.entries(byModel)) {
    for (const routeId of routes) {
      const group = priced.filter((record) =>
        `${record.model}@${record.provider_model_version}` === modelKey && record.route_id === routeId,
      );
      if (group.length) modelGroup.by_route[routeId] = summarizeGroup(group);
    }
  }
  return {
    schema_version: 1,
    pricing_source_verified_on: architecture.source_evidence_verified_on,
    cost_scope: "cloudflare_inference_only_not_total_attributable_customer_cost",
    attempts: priced.length,
    by_model: byModel,
    records: priced,
  };
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const input = process.argv[2];
  if (!input) throw new Error("usage: npm run benchmark:core:summarize -- benchmark.json");
  process.stdout.write(`${JSON.stringify(summarizeCoreBenchmark(JSON.parse(readFileSync(input, "utf8"))), null, 2)}\n`);
}
