import { readFile } from "node:fs/promises";

const candidate = JSON.parse(await readFile(new URL("../config/candidate.v1.json", import.meta.url)));
const stack = JSON.parse(await readFile(new URL("../config/training-stack.v1.json", import.meta.url)));
const runpod = JSON.parse(await readFile(new URL("../config/runpod-serverless.v1.json", import.meta.url)));
const catalog = JSON.parse(await readFile(new URL("../config/model-catalog.v1.json", import.meta.url)));
const economics = JSON.parse(await readFile(new URL("../config/economics.v1.json", import.meta.url)));
const identity = JSON.parse(await readFile(new URL("../config/identity.v1.json", import.meta.url)));
const inference = JSON.parse(await readFile(new URL("../config/inference-contract.v1.json", import.meta.url)));
const hardware = JSON.parse(await readFile(new URL("../config/hardware-benchmark.v1.json", import.meta.url)));
const surface = JSON.parse(await readFile(new URL("../config/product-surface.v1.json", import.meta.url)));
const activity = JSON.parse(await readFile(new URL("../config/activity-event.v1.json", import.meta.url)));
const completion = JSON.parse(await readFile(new URL("../config/completion-target.v1.json", import.meta.url)));
const evaluations = JSON.parse(await readFile(new URL("../config/evaluation-gates.v1.json", import.meta.url)));
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
if (
  inference.safety.paid_execution_authorized !== false ||
  inference.safety.accept_arbitrary_model_from_request !== false ||
  inference.safety.return_hidden_reasoning !== false
) {
  throw new Error("inference_must_remain_source_only_and_pinned");
}
if (hardware.model !== candidate.base_model || hardware.paid_benchmark_authorized !== false) {
  throw new Error("hardware_benchmark_must_match_candidate_and_stay_blocked");
}
if (hardware.minimum_unquantized_vram_gb < 80 || hardware.candidates.some((gpu) => gpu.vram_gb < 80 || gpu.benchmark_complete !== false)) {
  throw new Error("unquantized_candidates_require_unbenchmarked_80gb_gpu");
}
const expectedChatModes = ["instant", "medium", "high", "extra-high", "max", "ultra"];
if (surface.assistant_name !== "Kova" || surface.auto_route.id !== "kova-auto") {
  throw new Error("kova_auto_surface_required");
}
if (surface.chat_modes.map((mode) => mode.id).join(",") !== expectedChatModes.join(",")) {
  throw new Error("six_ordered_chat_modes_required");
}
if (surface.chat_modes.find((mode) => mode.id === "instant").activity_updates !== false) {
  throw new Error("instant_must_respond_directly");
}
for (const id of ["high", "extra-high", "max", "ultra"]) {
  if (surface.chat_modes.find((mode) => mode.id === id).activity_updates !== true) {
    throw new Error(`deep_mode_requires_activity:${id}`);
  }
}
if (surface.work_families.map((family) => family.display_name).join(",") !== "Kova 5.6 Cosmo,Kova 5.6 Orion,Kova 5.6 Nova") {
  throw new Error("three_kova_work_families_required");
}
if (surface.work_efforts.length !== 6 || surface.work_families.length * surface.work_efforts.length !== 18) {
  throw new Error("eighteen_work_combinations_required");
}
if (surface.effort_profiles.length !== 6 || surface.effort_profiles.map((profile) => profile.name).join(",") !== surface.work_efforts.join(",")) {
  throw new Error("six_distinct_work_effort_profiles_required");
}
if (surface.effort_profiles.some((profile, index, profiles) => index > 0 && profile.maximum_output_tokens <= profiles[index - 1].maximum_output_tokens)) {
  throw new Error("work_effort_budgets_must_increase");
}
if (surface.deep_mode_experience.hidden_chain_of_thought_exposed !== false || activity.rules.may_expose_hidden_reasoning !== false) {
  throw new Error("hidden_reasoning_must_stay_private");
}
if (activity.rules.must_follow_real_runtime_or_tool_event !== true || activity.rules.may_claim_unstarted_action !== false) {
  throw new Error("activity_must_be_truthfully_grounded");
}
if (completion.baseline_percent !== 0 || completion.current_verified_percent !== 10 || completion.live_model_routes !== 0 || completion.target_model_routes !== 25) {
  throw new Error("completion_progress_contract_mismatch");
}
if (evaluations.target_routes !== 25 || evaluations.passing_routes.length !== 0 || evaluations.release_policy.allow_name_only_mode_variants !== false) {
  throw new Error("all_routes_require_real_evaluation_evidence");
}
for (const model of catalog.models) {
  if (!model.upstream_model && model.deployment_ready !== false) {
    throw new Error(`unverified_model_enabled:${model.id}`);
  }
  if (model.deployment_ready === true) {
    if (model.upstream_model !== candidate.base_model || model.upstream_revision !== candidate.base_revision || model.license !== candidate.base_license) {
      throw new Error(`deployment_ready_model_missing_verified_metadata:${model.id}`);
    }
  }
}
console.log("Validated Kova planning stack; paid execution remains blocked.");
