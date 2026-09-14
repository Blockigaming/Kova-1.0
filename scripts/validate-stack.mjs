import { readFile } from "node:fs/promises";

const candidate = JSON.parse(await readFile(new URL("../config/candidate.v1.json", import.meta.url)));
const stack = JSON.parse(await readFile(new URL("../config/training-stack.v1.json", import.meta.url)));
const runpod = JSON.parse(await readFile(new URL("../config/runpod-serverless.v1.json", import.meta.url)));
const catalog = JSON.parse(await readFile(new URL("../config/model-catalog.v1.json", import.meta.url)));
const economics = JSON.parse(await readFile(new URL("../config/economics.v1.json", import.meta.url)));
const identity = JSON.parse(await readFile(new URL("../config/identity.v1.json", import.meta.url)));
const inference = JSON.parse(await readFile(new URL("../config/inference-contract.v1.json", import.meta.url)));
if (candidate.base_model !== "Qwen/Qwen3.8-27B") throw new Error("unexpected_model");
if (!/^[a-f0-9]{40}$/u.test(candidate.base_revision)) throw new Error("unpinned_revision");
if (candidate.execution.authorized !== false) throw new Error("execution_must_be_blocked");
if (stack.status !== "planning_only" || stack.execution_authorized !== false) {
  throw new Error("planning_only_required");
}
if (runpod.worker_type !== "flex" || runpod.active_workers !== 0) {
  throw new Error("runpod_must_scale_to_zero");
}
if (runpod.billing.usage_model !== "metered_pay_per_second" || runpod.billing.flat_rate_plan !== false) {
  throw new Error("runpod_must_use_metered_billing");
}
if (runpod.billing.auto_pay_enabled !== false || runpod.billing.automatic_credit_reload_allowed !== false) {
  throw new Error("automatic_credit_reload_must_be_disabled");
}
if (runpod.safety.paid_execution_authorized !== false || runpod.safety.deployment_authorized !== false || runpod.safety.production_routing_authorized !== false) {
  throw new Error("runpod_paid_actions_must_be_blocked");
}
if (economics.target_gross_margin !== 0.426 || economics.cost_fraction !== 0.574) {
  throw new Error("unexpected_margin_target");
}
if (
  economics.enforcement.pricing_status !== "blocked_until_benchmarked" ||
  economics.enforcement.require_per_model_benchmark !== true ||
  economics.enforcement.require_per_effort_benchmark !== true ||
  economics.enforcement.require_usage_telemetry !== true ||
  economics.enforcement.require_periodic_recalibration !== true ||
  economics.enforcement.allow_unmeasured_price_publication !== false
) {
  throw new Error("unmeasured_prices_must_be_blocked");
}
const requiredBehaviors = [
  "identify_as_kova", "truthful_upstream_disclosure_when_asked", "preserve_required_license_notices",
  "tool_result_grounding", "no_hidden_chain_of_thought", "contextual_not_forced_plus_recommendations",
];
const requiredIdentityText = ["You are Kova", "Do not claim", "Qwen", "Never claim a tool action", "Do not reveal hidden chain-of-thought"];
if (
  identity.assistant_name !== "Kova" ||
  !requiredBehaviors.every((behavior) => identity.required_behaviors.includes(behavior)) ||
  !requiredIdentityText.every((text) => identity.system_identity.includes(text)) ||
  !identity.forbidden_claims.includes("kova_foundation_trained_from_scratch")
) {
  throw new Error("truthful_kova_identity_required");
}
if (inference.model !== candidate.base_model || inference.model_revision !== candidate.base_revision) {
  throw new Error("inference_model_must_match_pinned_candidate");
}
if (inference.safety.paid_execution_authorized !== false || inference.safety.accept_arbitrary_model_from_request !== false) {
  throw new Error("inference_must_remain_source_only_and_pinned");
}
for (const model of catalog.models) {
  if (!model.upstream_model && model.deployment_ready !== false) {
    throw new Error(`unverified_model_enabled:${model.id}`);
  }
  if (model.deployment_ready === true) {
    if (!model.upstream_revision || !/^[a-f0-9]{40}$/u.test(model.upstream_revision) || model.license !== "Apache-2.0") {
      throw new Error(`deployment_ready_model_missing_verified_metadata:${model.id}`);
    }
  }
}
console.log("Validated Kova planning stack; paid execution remains blocked.");
