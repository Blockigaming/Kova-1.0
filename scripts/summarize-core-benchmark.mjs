import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

const serving = JSON.parse(readFileSync(new URL("../config/core-serving.v1.json", import.meta.url), "utf8"));
const routePolicy = JSON.parse(readFileSync(new URL("../config/route-policy.v1.json", import.meta.url), "utf8"));
const candidates = new Map(serving.candidates.map((candidate) => [candidate.model, candidate]));
const outcomes = new Set(["success", "failed"]);
const recordTypes = new Set(["attempt", "lifecycle_close"]);
const commonRequired = [
  "record_type", "worker_lifecycle_id", "model", "model_revision", "gpu_type_id",
  "gpu_count", "serving_engine", "endpoint_type", "container_image_digest",
  "gpu_rate_per_second_usd", "measurement_source",
];
const attemptRequired = [
  "request_id", "attempt_id", "outcome", "route_id", "stage_id", "public_response",
  "cold_start", "reasoning_effort", "worker_start_ms", "model_load_ms", "queue_ms", "inference_ms",
  "time_to_first_token_ms", "input_tokens", "output_tokens",
];
const closeRequired = ["close_event_id", "attributed_idle_timeout_ms"];

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
  routeSpecs.set(route.id, {stages, public_stage: stages.at(-1), reasoning_effort: route.reasoning_effort});
}
for (const family of routePolicy.work.families) {
  for (const effort of routePolicy.work.effort_profiles.filter((item) => item.engine === "kova-core")) {
    const routeId = `work:${family}:${effort.name.toLowerCase().replaceAll(" ", "-")}`;
    const stages = stageIds(effort);
    routeSpecs.set(routeId, {stages, public_stage: stages.at(-1), reasoning_effort: effort.reasoning_effort});
  }
}

export const coreConfigurationKey = (record) => [
  `${record.model}@${record.model_revision}`,
  `${record.gpu_type_id}x${record.gpu_count}`,
  record.serving_engine,
  record.endpoint_type,
  record.container_image_digest,
].join("|");

const configurationFrom = (record) => ({
  model: record.model,
  model_revision: record.model_revision,
  quantization: candidates.get(record.model).quantization,
  gpu_type_id: record.gpu_type_id,
  gpu_count: record.gpu_count,
  serving_engine: record.serving_engine,
  endpoint_type: record.endpoint_type,
  container_image_digest: record.container_image_digest,
});

function summarizeGroup(records, routeId, allocations) {
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
  const inferenceCost = records.reduce((total, record) => total + record.inference_cost_usd, 0);
  const startupCost = allocations.reduce((total, item) => total + item.startup_cost_usd, 0);
  const idleCost = allocations.reduce((total, item) => total + item.idle_cost_usd, 0);
  const totalComputeCost = inferenceCost + startupCost + idleCost;
  return {
    attempts: records.length,
    worker_lifecycles: new Set(records.map((record) => record.worker_lifecycle_id)).size,
    logical_requests: requestIds.size,
    successful_requests: successfulRequests.size,
    failed_attempts: records.length - successfulAttempts.length,
    total_attributable_compute_cost_usd: totalComputeCost,
    total_inference_cost_usd: inferenceCost,
    allocated_startup_cost_usd: startupCost,
    allocated_idle_cost_usd: idleCost,
    average_compute_cost_per_successful_request_usd:
      successfulRequests.size ? totalComputeCost / successfulRequests.size : null,
    startup_share_of_compute_percent: totalComputeCost > 0 ? startupCost / totalComputeCost * 100 : null,
    idle_share_of_compute_percent: totalComputeCost > 0 ? idleCost / totalComputeCost * 100 : null,
    average_success_stage_latency_ms: average(successfulAttempts, "inference_ms"),
    average_public_time_to_first_token_ms: average(successfulPublicAttempts, "time_to_first_token_ms"),
    average_public_output_tokens: average(successfulPublicAttempts, "output_tokens"),
  };
}

export function summarizeCoreBenchmark(records) {
  if (!Array.isArray(records) || records.length === 0) throw new Error("Core benchmark requires records");
  const seenRecordIds = new Set();
  const requestIdentities = new Map();
  const requestRoutes = new Map();
  const lifecycles = new Map();
  const attempts = [];
  const closes = [];

  for (const [index, record] of records.entries()) {
    for (const field of commonRequired) if (!(field in record)) throw new Error(`record ${index} missing ${field}`);
    if (!recordTypes.has(record.record_type)) throw new Error(`record ${index} invalid record_type`);
    const allowedFields = new Set([
      ...commonRequired,
      ...(record.record_type === "attempt" ? attemptRequired : closeRequired),
    ]);
    const extraFields = Object.keys(record).filter((field) => !allowedFields.has(field));
    if (extraFields.length) throw new Error(`record ${index} unsupported fields:${extraFields.sort().join(",")}`);
    for (const field of ["worker_lifecycle_id", "model", "model_revision", "gpu_type_id", "serving_engine", "endpoint_type", "container_image_digest"]) {
      if (typeof record[field] !== "string" || !record[field].trim()) throw new Error(`record ${index} invalid ${field}`);
    }
    const candidate = candidates.get(record.model);
    if (!candidate || candidate.revision !== record.model_revision) throw new Error(`record ${index} unverified model revision`);
    if (!Number.isInteger(record.gpu_count) || record.gpu_count < 1 || record.gpu_count > 8) {
      throw new Error(`record ${index} invalid gpu_count`);
    }
    if (!serving.serving_engine_candidates.includes(record.serving_engine)) throw new Error(`record ${index} invalid serving_engine`);
    if (!serving.endpoint_type_candidates.includes(record.endpoint_type)) throw new Error(`record ${index} invalid endpoint_type`);
    if (!/^sha256:[a-f0-9]{64}$/u.test(record.container_image_digest)) throw new Error(`record ${index} invalid container_image_digest`);
    if (!Number.isFinite(record.gpu_rate_per_second_usd) || record.gpu_rate_per_second_usd <= 0) {
      throw new Error(`record ${index} invalid gpu_rate_per_second_usd`);
    }
    if (record.measurement_source !== "server_provider_runtime") throw new Error(`record ${index} invalid measurement_source`);

    const configurationKey = coreConfigurationKey(record);
    const lifecycle = lifecycles.get(record.worker_lifecycle_id) ?? {
      configuration_key: configurationKey,
      configuration: configurationFrom(record),
      attempts: [],
      closes: [],
      rates: new Set(),
    };
    if (lifecycle.configuration_key !== configurationKey) {
      throw new Error(`lifecycle ${record.worker_lifecycle_id} mixes serving configurations`);
    }
    lifecycle.rates.add(record.gpu_rate_per_second_usd);

    if (record.record_type === "attempt") {
      for (const field of attemptRequired) if (!(field in record)) throw new Error(`record ${index} missing ${field}`);
      for (const field of ["request_id", "attempt_id", "stage_id", "route_id"]) {
        if (typeof record[field] !== "string" || !record[field]) throw new Error(`record ${index} invalid ${field}`);
      }
      if (seenRecordIds.has(`attempt:${record.attempt_id}`)) throw new Error(`record ${index} duplicate attempt_id`);
      seenRecordIds.add(`attempt:${record.attempt_id}`);
      const routeSpec = routeSpecs.get(record.route_id);
      if (!routeSpec) throw new Error(`record ${index} invalid route_id`);
      if (!outcomes.has(record.outcome)) throw new Error(`record ${index} invalid outcome`);
      if (!["low", "medium", "xhigh"].includes(record.reasoning_effort)) throw new Error(`record ${index} invalid reasoning_effort`);
      if (record.reasoning_effort !== routeSpec.reasoning_effort) throw new Error(`record ${index} reasoning_effort does not match route`);
      for (const field of ["public_response", "cold_start"]) {
        if (typeof record[field] !== "boolean") throw new Error(`record ${index} invalid ${field}`);
      }
      if (!routeSpec.stages.includes(record.stage_id)) throw new Error(`record ${index} invalid stage_id for route`);
      if (record.public_response !== (record.stage_id === routeSpec.public_stage)) {
        throw new Error(`record ${index} public_response does not match route DAG`);
      }
      for (const field of ["worker_start_ms", "model_load_ms", "queue_ms", "inference_ms"]) {
        if (!Number.isFinite(record[field]) || record[field] < 0) throw new Error(`record ${index} invalid ${field}`);
      }
      for (const field of ["input_tokens", "output_tokens"]) {
        if (!Number.isInteger(record[field]) || record[field] < 0) throw new Error(`record ${index} invalid ${field}`);
      }
      const firstToken = record.time_to_first_token_ms;
      if (firstToken !== null && (!Number.isFinite(firstToken) || firstToken < 0)) {
        throw new Error(`record ${index} invalid time_to_first_token_ms`);
      }
      if (!record.public_response && firstToken !== null) {
        throw new Error(`record ${index} private stage must not claim first-token timing`);
      }
      if (record.public_response && record.outcome === "success" && firstToken === null) {
        throw new Error(`record ${index} successful public stage missing first-token timing`);
      }
      if (firstToken !== null && firstToken > record.inference_ms) throw new Error(`record ${index} first token exceeds inference`);
      const startupMs = record.worker_start_ms + record.model_load_ms;
      if (record.cold_start && startupMs <= 0) throw new Error(`record ${index} cold attempt missing measured startup`);
      if (!record.cold_start && startupMs !== 0) throw new Error(`record ${index} warm attempt contains startup attribution`);

      const requestIdentity = `${configurationKey}|${record.route_id}`;
      const priorRequestIdentity = requestIdentities.get(record.request_id);
      if (priorRequestIdentity && priorRequestIdentity !== requestIdentity) {
        throw new Error(`request ${record.request_id} mixes serving configuration or route`);
      }
      requestIdentities.set(record.request_id, requestIdentity);
      requestRoutes.set(record.request_id, record.route_id);
      lifecycle.attempts.push(record);
      attempts.push(record);
    } else {
      for (const field of closeRequired) {
        if (!(field in record)) throw new Error(`record ${index} missing ${field}`);
      }
      if (typeof record.close_event_id !== "string" || !record.close_event_id) throw new Error(`record ${index} invalid close_event_id`);
      if (seenRecordIds.has(`close:${record.close_event_id}`)) throw new Error(`record ${index} duplicate close_event_id`);
      seenRecordIds.add(`close:${record.close_event_id}`);
      if (!Number.isFinite(record.attributed_idle_timeout_ms) || record.attributed_idle_timeout_ms <= 0) {
        throw new Error(`record ${index} lifecycle close missing measured idle tail`);
      }
      lifecycle.closes.push(record);
      closes.push(record);
    }
    lifecycles.set(record.worker_lifecycle_id, lifecycle);
  }

  for (const [lifecycleId, lifecycle] of lifecycles) {
    if (!lifecycle.attempts.length) throw new Error(`lifecycle ${lifecycleId} has no attempts`);
    if (lifecycle.attempts.filter((record) => record.cold_start).length !== 1) {
      throw new Error(`lifecycle ${lifecycleId} requires exactly one cold-start attribution`);
    }
    if (lifecycle.closes.length !== 1) throw new Error(`lifecycle ${lifecycleId} requires exactly one close event`);
    if (lifecycle.rates.size !== 1) throw new Error(`lifecycle ${lifecycleId} mixes GPU rates`);
  }

  const pricedAttempts = attempts.map((record) => {
    const rate = record.gpu_rate_per_second_usd;
    const startupMs = record.worker_start_ms + record.model_load_ms;
    return {
      ...record,
      startup_ms: startupMs,
      startup_cost_usd: startupMs / 1000 * rate,
      inference_cost_usd: record.inference_ms / 1000 * rate,
      configuration_key: coreConfigurationKey(record),
    };
  });
  const pricedCloses = closes.map((record) => ({
    ...record,
    idle_cost_usd: record.attributed_idle_timeout_ms / 1000 * record.gpu_rate_per_second_usd,
    configuration_key: coreConfigurationKey(record),
  }));

  const lifecycleAllocations = [];
  for (const [lifecycleId, lifecycle] of lifecycles) {
    const lifecycleAttempts = pricedAttempts.filter((record) => record.worker_lifecycle_id === lifecycleId);
    const close = pricedCloses.find((record) => record.worker_lifecycle_id === lifecycleId);
    const requestIds = [...new Set(lifecycleAttempts.map((record) => record.request_id))];
    const startupCost = lifecycleAttempts.reduce((total, record) => total + record.startup_cost_usd, 0);
    for (const requestId of requestIds) {
      lifecycleAllocations.push({
        worker_lifecycle_id: lifecycleId,
        configuration_key: lifecycle.configuration_key,
        request_id: requestId,
        route_id: requestRoutes.get(requestId),
        allocation_policy: "equal_share_per_logical_request_in_lifecycle",
        startup_cost_usd: startupCost / requestIds.length,
        idle_cost_usd: close.idle_cost_usd / requestIds.length,
      });
    }
  }

  const byConfiguration = {};
  for (const record of pricedAttempts) {
    const key = record.configuration_key;
    byConfiguration[key] ??= {configuration: configurationFrom(record), by_route: {}};
  }
  for (const [configurationKey, configurationGroup] of Object.entries(byConfiguration)) {
    for (const routeId of routeSpecs.keys()) {
      const group = pricedAttempts.filter((record) => record.configuration_key === configurationKey && record.route_id === routeId);
      if (group.length) {
        const allocations = lifecycleAllocations.filter((item) => item.configuration_key === configurationKey && item.route_id === routeId);
        configurationGroup.by_route[routeId] = summarizeGroup(group, routeId, allocations);
      }
    }
  }

  const totalStartupCost = pricedAttempts.reduce((total, record) => total + record.startup_cost_usd, 0);
  const totalInferenceCost = pricedAttempts.reduce((total, record) => total + record.inference_cost_usd, 0);
  const totalIdleCost = pricedCloses.reduce((total, record) => total + record.idle_cost_usd, 0);
  return {
    schema_version: 4,
    provider: "runpod_serverless",
    cost_scope: "runpod_compute_only_excludes_storage_app_tools_payment_and_taxes",
    lifecycle_overhead_allocation: "equal_share_per_logical_request_in_lifecycle",
    timing_contract: "worker_start_model_load_inference_and_idle_tail_are_nonoverlapping_server_measured_phases;ttft_is_public_stream_first_visible_delta_or_null_when_unavailable",
    attempts: pricedAttempts.length,
    worker_lifecycles: lifecycles.size,
    total_attributable_compute_cost_usd: totalStartupCost + totalInferenceCost + totalIdleCost,
    by_configuration: byConfiguration,
    lifecycle_allocations: lifecycleAllocations,
    attempt_records: pricedAttempts,
    lifecycle_close_records: pricedCloses,
  };
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const input = process.argv[2];
  if (!input) throw new Error("usage: npm run benchmark:core:summarize -- benchmark.json");
  process.stdout.write(`${JSON.stringify(summarizeCoreBenchmark(JSON.parse(readFileSync(input, "utf8"))), null, 2)}\n`);
}
