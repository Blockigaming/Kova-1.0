import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

const serving = JSON.parse(readFileSync(new URL("../config/core-serving.v1.json", import.meta.url), "utf8"));
const routePolicy = JSON.parse(readFileSync(new URL("../config/route-policy.v1.json", import.meta.url), "utf8"));
const candidates = new Map(serving.candidates.map((candidate) => [candidate.model, candidate]));
const outcomes = new Set(["success", "failed"]);
const required = [
  "request_id", "attempt_id", "worker_lifecycle_id", "lifecycle_closed", "outcome",
  "model", "model_revision", "route_id", "stage_id", "public_response", "cold_start",
  "worker_start_ms", "model_load_ms", "queue_ms", "inference_ms",
  "attributed_idle_timeout_ms", "time_to_first_token_ms", "input_tokens", "output_tokens",
  "gpu_rate_per_second_usd", "measurement_source",
];
const durationFields = [
  "worker_start_ms", "model_load_ms", "queue_ms", "inference_ms",
  "attributed_idle_timeout_ms", "time_to_first_token_ms",
];

const average = (records, key) => records.length
  ? records.reduce((total, record) => total + record[key], 0) / records.length
  : null;

const stageIds = (policy) => {
  const stages = [];
  for (const [phase, field] of [
    ["planning", "planning_passes"], ["answer", "answer_passes"],
    ["critic", "critic_passes"], ["verification", "verification_passes"],
  ]) {
    for (let index = 1; index <= (policy[field] ?? 0); index += 1) stages.push(`${phase}-${index}`);
  }
  return stages;
};

const routeSpecs = new Map();
for (const route of routePolicy.chat.filter((item) => item.engine === "kova-core")) {
  const stages = stageIds(route);
  routeSpecs.set(route.id, {stages, public_stage: stages.at(-1)});
}
for (const family of routePolicy.work.families) {
  for (const effort of routePolicy.work.effort_profiles.filter((item) => item.engine === "kova-core")) {
    const routeId = `work:${family}:${effort.name.toLowerCase().replaceAll(" ", "-")}`;
    const stages = stageIds(effort);
    routeSpecs.set(routeId, {stages, public_stage: stages.at(-1)});
  }
}

function summarizeGroup(records, routeId) {
  const spec = routeSpecs.get(routeId);
  const successfulAttempts = records.filter((record) => record.outcome === "success");
  const requestIds = new Set(records.map((record) => record.request_id));
  const successfulRequests = new Set([...requestIds].filter((requestId) => {
    const attempts = successfulAttempts.filter((record) => record.request_id === requestId);
    return spec.stages.every((stageId) => attempts.some((record) => record.stage_id === stageId));
  }));
  const successfulPublicAttempts = successfulAttempts.filter((record) =>
    record.stage_id === spec.public_stage && successfulRequests.has(record.request_id),
  );
  const totalComputeCost = records.reduce((total, record) => total + record.compute_cost_usd, 0);
  const totalStartupCost = records.reduce((total, record) => total + record.startup_cost_usd, 0);
  const totalIdleCost = records.reduce((total, record) => total + record.idle_cost_usd, 0);
  return {
    attempts: records.length,
    worker_lifecycles: new Set(records.map((record) => record.worker_lifecycle_id)).size,
    logical_requests: requestIds.size,
    successful_requests: successfulRequests.size,
    failed_attempts: records.length - successfulAttempts.length,
    total_attributable_compute_cost_usd: totalComputeCost,
    average_compute_cost_per_successful_request_usd:
      successfulRequests.size ? totalComputeCost / successfulRequests.size : null,
    startup_share_of_compute_percent: totalComputeCost > 0 ? totalStartupCost / totalComputeCost * 100 : null,
    idle_share_of_compute_percent: totalComputeCost > 0 ? totalIdleCost / totalComputeCost * 100 : null,
    average_success_stage_latency_ms: average(successfulAttempts, "inference_ms"),
    average_public_time_to_first_token_ms: average(successfulPublicAttempts, "time_to_first_token_ms"),
    average_public_output_tokens: average(successfulPublicAttempts, "output_tokens"),
  };
}

export function summarizeCoreBenchmark(records) {
  if (!Array.isArray(records) || records.length === 0) throw new Error("Core benchmark requires records");
  const seenAttempts = new Set();
  const requestIdentities = new Map();
  const lifecycles = new Map();
  for (const [index, record] of records.entries()) {
    for (const field of required) if (!(field in record)) throw new Error(`record ${index} missing ${field}`);
    for (const field of ["request_id", "attempt_id", "worker_lifecycle_id", "stage_id"]) {
      if (typeof record[field] !== "string" || !record[field]) throw new Error(`record ${index} invalid ${field}`);
    }
    if (seenAttempts.has(record.attempt_id)) throw new Error(`record ${index} duplicate attempt_id`);
    seenAttempts.add(record.attempt_id);
    const candidate = candidates.get(record.model);
    if (!candidate || candidate.revision !== record.model_revision) throw new Error(`record ${index} unverified model revision`);
    const routeSpec = routeSpecs.get(record.route_id);
    if (!routeSpec) throw new Error(`record ${index} invalid route_id`);
    if (!outcomes.has(record.outcome)) throw new Error(`record ${index} invalid outcome`);
    for (const field of ["public_response", "cold_start", "lifecycle_closed"]) {
      if (typeof record[field] !== "boolean") throw new Error(`record ${index} invalid ${field}`);
    }
    if (!routeSpec.stages.includes(record.stage_id)) throw new Error(`record ${index} invalid stage_id for route`);
    if (record.public_response !== (record.stage_id === routeSpec.public_stage)) {
      throw new Error(`record ${index} public_response does not match route DAG`);
    }
    if (record.measurement_source !== "server_provider_runtime") throw new Error(`record ${index} invalid measurement_source`);
    for (const field of durationFields) {
      if (!Number.isFinite(record[field]) || record[field] < 0) throw new Error(`record ${index} invalid ${field}`);
    }
    for (const field of ["input_tokens", "output_tokens"]) {
      if (!Number.isInteger(record[field]) || record[field] < 0) throw new Error(`record ${index} invalid ${field}`);
    }
    if (!Number.isFinite(record.gpu_rate_per_second_usd) || record.gpu_rate_per_second_usd <= 0) {
      throw new Error(`record ${index} invalid gpu_rate_per_second_usd`);
    }
    if (record.time_to_first_token_ms > record.inference_ms) throw new Error(`record ${index} first token exceeds inference`);
    if (!record.cold_start && (record.worker_start_ms > 0 || record.model_load_ms > 0)) {
      throw new Error(`record ${index} warm attempt contains startup attribution`);
    }
    if (!record.lifecycle_closed && record.attributed_idle_timeout_ms > 0) {
      throw new Error(`record ${index} open lifecycle contains idle-tail attribution`);
    }

    const requestIdentity = `${record.model}@${record.model_revision}:${record.route_id}`;
    const priorRequestIdentity = requestIdentities.get(record.request_id);
    if (priorRequestIdentity && priorRequestIdentity !== requestIdentity) {
      throw new Error(`request ${record.request_id} mixes model revision or route`);
    }
    requestIdentities.set(record.request_id, requestIdentity);

    const lifecycle = lifecycles.get(record.worker_lifecycle_id) ?? {
      identity: requestIdentity,
      records: [],
    };
    if (lifecycle.identity !== requestIdentity) {
      throw new Error(`lifecycle ${record.worker_lifecycle_id} mixes model revision or route`);
    }
    lifecycle.records.push(record);
    lifecycles.set(record.worker_lifecycle_id, lifecycle);
  }

  for (const [lifecycleId, lifecycle] of lifecycles) {
    if (lifecycle.records.filter((record) => record.cold_start).length !== 1) {
      throw new Error(`lifecycle ${lifecycleId} requires exactly one cold-start attribution`);
    }
    if (lifecycle.records.filter((record) => record.lifecycle_closed).length !== 1) {
      throw new Error(`lifecycle ${lifecycleId} requires exactly one closed-tail attribution`);
    }
    const rates = new Set(lifecycle.records.map((record) => record.gpu_rate_per_second_usd));
    if (rates.size !== 1) throw new Error(`lifecycle ${lifecycleId} mixes GPU rates`);
  }

  const priced = records.map((record) => {
    const rate = record.gpu_rate_per_second_usd;
    const startupMs = record.worker_start_ms + record.model_load_ms;
    const billableMs = startupMs + record.inference_ms + record.attributed_idle_timeout_ms;
    return {
      ...record,
      startup_ms: startupMs,
      billable_ms: billableMs,
      startup_cost_usd: startupMs / 1000 * rate,
      inference_cost_usd: record.inference_ms / 1000 * rate,
      idle_cost_usd: record.attributed_idle_timeout_ms / 1000 * rate,
      compute_cost_usd: billableMs / 1000 * rate,
    };
  });
  const byModel = {};
  for (const record of priced) {
    const modelKey = `${record.model}@${record.model_revision}`;
    byModel[modelKey] ??= {model: record.model, model_revision: record.model_revision, by_route: {}};
  }
  for (const [modelKey, modelGroup] of Object.entries(byModel)) {
    for (const routeId of routeSpecs.keys()) {
      const group = priced.filter((record) =>
        `${record.model}@${record.model_revision}` === modelKey && record.route_id === routeId,
      );
      if (group.length) modelGroup.by_route[routeId] = summarizeGroup(group, routeId);
    }
  }
  return {
    schema_version: 2,
    provider: "runpod_serverless",
    cost_scope: "runpod_compute_only_excludes_storage_app_tools_payment_and_taxes",
    attempts: priced.length,
    worker_lifecycles: lifecycles.size,
    by_model: byModel,
    records: priced,
  };
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const input = process.argv[2];
  if (!input) throw new Error("usage: npm run benchmark:core:summarize -- benchmark.json");
  process.stdout.write(`${JSON.stringify(summarizeCoreBenchmark(JSON.parse(readFileSync(input, "utf8"))), null, 2)}\n`);
}
