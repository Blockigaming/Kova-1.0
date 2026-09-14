import { readFile } from "node:fs/promises";

const load = async (name) => JSON.parse(await readFile(new URL(`../config/${name}`, import.meta.url)));
const [
  candidate, stack, runpod, catalog, economics, identity, inference, hardware, surface,
  activity, completion, evaluations, nova, cosmo, architecture, routes,
] = await Promise.all([
  "candidate.v1.json", "training-stack.v1.json", "runpod-serverless.v1.json",
  "model-catalog.v1.json", "economics.v1.json", "identity.v1.json",
  "inference-contract.v1.json", "hardware-benchmark.v1.json", "product-surface.v1.json",
  "activity-event.v1.json", "completion-target.v1.json", "evaluation-gates.v1.json",
  "nova-candidate.v1.json", "cosmo-candidate.v1.json", "provider-architecture.v1.json",
  "route-policy.v1.json",
].map(load));

if (candidate.base_model !== "Qwen/Qwen3.8-27B" || !/^[a-f0-9]{40}$/u.test(candidate.base_revision)) {
  throw new Error("unexpected_or_unpinned_self_hosted_candidate");
}
if (candidate.execution.authorized !== false || stack.status !== "planning_only" || stack.execution_authorized !== false) {
  throw new Error("planning_only_required");
}
if (runpod.worker_type !== "flex" || runpod.active_workers !== 0) throw new Error("runpod_must_scale_to_zero");
if (runpod.billing.usage_model !== "metered_pay_per_second" || runpod.billing.flat_rate_plan !== false) {
  throw new Error("runpod_must_use_metered_billing");
}
if (runpod.billing.auto_pay_enabled !== false || runpod.billing.automatic_credit_reload_allowed !== false) {
  throw new Error("automatic_credit_reload_must_be_disabled");
}
if (
  runpod.safety.paid_execution_authorized !== false ||
  runpod.safety.deployment_authorized !== false ||
  runpod.safety.production_routing_authorized !== false
) {
  throw new Error("runpod_paid_actions_must_be_blocked");
}

if (economics.target_gross_margin !== 0.426 || economics.cost_fraction !== 0.574) throw new Error("unexpected_margin_target");
if (
  economics.enforcement.pricing_status !== "blocked_until_benchmarked" ||
  economics.enforcement.require_per_model_benchmark !== true ||
  economics.enforcement.require_per_effort_benchmark !== true ||
  economics.enforcement.require_usage_telemetry !== true ||
  economics.enforcement.require_periodic_recalibration !== true ||
  economics.enforcement.allow_unmeasured_price_publication !== false
) throw new Error("unmeasured_prices_must_be_blocked");

const requiredBehaviors = [
  "identify_as_kova", "truthful_active_provider_and_upstream_disclosure_when_asked",
  "do_not_claim_profile_names_are_separate_foundation_weights", "preserve_required_license_notices",
  "tool_result_grounding", "no_hidden_chain_of_thought", "contextual_not_forced_plus_recommendations",
];
const requiredIdentityText = [
  "You are Kova", "Do not claim", "Cosmo, Orion, and Nova", "provider and upstream model",
  "Never claim a tool action", "Do not reveal hidden chain-of-thought",
];
if (
  identity.assistant_name !== "Kova" ||
  !requiredBehaviors.every((behavior) => identity.required_behaviors.includes(behavior)) ||
  !requiredIdentityText.every((value) => identity.system_identity.includes(value)) ||
  !identity.forbidden_claims.includes("kova_foundation_trained_from_scratch")
) throw new Error("truthful_kova_identity_required");

if (inference.model !== candidate.base_model || inference.model_revision !== candidate.base_revision) {
  throw new Error("benchmark_worker_must_match_pinned_candidate");
}
for (const field of ["attempt_id", "outcome", "model", "model_revision", "measurement_source", "cold_start", "gpu_rate_per_second_usd"]) {
  if (!inference.response_usage.required.includes(field)) throw new Error(`inference_telemetry_missing:${field}`);
}
if (
  inference.safety.paid_execution_authorized !== false ||
  inference.safety.accept_arbitrary_model_from_request !== false ||
  inference.safety.return_hidden_reasoning !== false
) throw new Error("inference_must_remain_source_only_and_pinned");
if (hardware.model !== candidate.base_model || hardware.paid_benchmark_authorized !== false) {
  throw new Error("hardware_benchmark_must_match_candidate_and_stay_blocked");
}
if (hardware.minimum_unquantized_vram_gb < 80 || hardware.candidates.some((gpu) => gpu.vram_gb < 80 || gpu.benchmark_complete !== false)) {
  throw new Error("unquantized_candidates_require_unbenchmarked_80gb_gpu");
}

if (architecture.status !== "planning_only" || architecture.application_plane.provider !== "azure_container_apps") {
  throw new Error("azure_application_plane_must_be_preserved");
}
if (
  architecture.application_plane.delete_existing_azure_deployments !== false ||
  architecture.application_plane.production_routing_authorized !== false ||
  architecture.global_guards.paid_or_production_actions_authorized !== false
) throw new Error("unverified_migration_actions_must_be_blocked");
const core = architecture.engines.find((engine) => engine.id === "kova-core");
const ultra = architecture.engines.find((engine) => engine.id === "kova-ultra");
if (!core || core.provider !== "cloudflare_workers_ai" || core.selected_model !== null || core.selection_status !== "benchmark_required") {
  throw new Error("cloudflare_core_selection_must_stay_benchmark_blocked");
}
const coreCandidate = core.candidate_models.find((model) => model.model === "@cf/qwen/qwen3.8-27b");
if (!coreCandidate || coreCandidate.context_tokens !== 262144 || coreCandidate.input_usd_per_million_tokens !== 0.45 || coreCandidate.output_usd_per_million_tokens !== 3.2) {
  throw new Error("verified_cloudflare_qwen_candidate_required");
}
if (
  core.paid_execution_authorized !== false || core.production_routing_authorized !== false ||
  core.require_trusted_provider_token_count_before_request !== true ||
  core.billing.inference_metered_by_usage !== true ||
  core.billing.satisfies_no_flat_fee_and_no_prepaid_credits !== false ||
  core.billing.workers_paid_minimum_usd_per_month !== 5
) throw new Error("cloudflare_billing_tradeoff_must_be_explicit_and_blocked");
if (
  !ultra || ultra.provider !== "runpod_serverless" || ultra.worker_type !== "flex" ||
  ultra.active_workers !== 0 || ultra.selected_model !== null ||
  ultra.paid_execution_authorized !== false || ultra.production_routing_authorized !== false ||
  ultra.hidden_chain_of_thought_exposed !== false
) throw new Error("ultra_must_be_unselected_scale_to_zero_and_blocked");

const expectedChatModes = ["instant", "medium", "high", "extra-high", "max", "ultra"];
if (
  surface.assistant_name !== "Kova" || surface.auto_route.id !== "kova-auto" ||
  surface.auto_route.classifier_implemented !== true || surface.auto_route.deployment_ready !== false
) {
  throw new Error("blocked_kova_auto_surface_required");
}
if (surface.chat_modes.map((mode) => mode.id).join(",") !== expectedChatModes.join(",")) throw new Error("six_ordered_chat_modes_required");
if (surface.chat_modes.slice(0, 5).some((mode) => mode.engine !== "kova-core")) throw new Error("auto_through_max_must_use_core");
if (surface.chat_modes.find((mode) => mode.id === "ultra").engine !== "kova-ultra") throw new Error("ultra_must_change_engine");
if (surface.chat_modes.find((mode) => mode.id === "instant").activity_updates !== false) throw new Error("instant_must_respond_directly");
for (const id of ["high", "extra-high", "max", "ultra"]) {
  if (surface.chat_modes.find((mode) => mode.id === id).activity_updates !== true) throw new Error(`deep_mode_requires_activity:${id}`);
}
if (surface.chat_modes.some((mode) => mode.deployment_ready !== false)) throw new Error("all_chat_modes_must_stay_blocked");
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
if (surface.effort_profiles.slice(0, 5).some((profile) => profile.engine !== "kova-core") || surface.effort_profiles[5].engine !== "kova-ultra") {
  throw new Error("work_ultra_must_change_engine");
}

if (
  routes.shared_core_weights !== true || routes.chat.length !== 6 ||
  routes.auto.classifier_implemented !== true || routes.auto.classifier_type !== "deterministic_server_rules_v1" ||
  routes.auto.free_plan_route_cap !== "instant" || routes.auto.ultra_entitlement !== "pro" ||
  routes.auto.ultra_budget_gate_required !== true || routes.auto.production_ready !== false
) {
  throw new Error("route_policy_must_be_source_only_and_fail_closed");
}
if (routes.chat.slice(0, 5).some((route) => route.engine !== "kova-core") || routes.chat[5].engine !== "kova-ultra") {
  throw new Error("route_policy_engine_boundary_invalid");
}
if (routes.chat[0].answer_passes !== 1 || routes.chat[0].activity_updates !== false) throw new Error("instant_route_must_be_one_pass");
if (!routes.caller_forbidden_fields.includes("model") || !routes.caller_forbidden_fields.includes("engine")) {
  throw new Error("route_provider_and_model_must_be_server_controlled");
}

if (surface.deep_mode_experience.hidden_chain_of_thought_exposed !== false || activity.rules.may_expose_hidden_reasoning !== false) {
  throw new Error("hidden_reasoning_must_stay_private");
}
if (activity.rules.must_follow_real_runtime_or_tool_event !== true || activity.rules.may_claim_unstarted_action !== false) {
  throw new Error("activity_must_be_truthfully_grounded");
}
if (completion.baseline_percent !== 0 || completion.current_verified_percent !== 18 || completion.live_model_routes !== 0 || completion.target_model_routes !== 25) {
  throw new Error("completion_progress_contract_mismatch");
}
if (
  evaluations.status !== "all_routes_blocked" || evaluations.target_routes !== 25 ||
  evaluations.passing_routes.length !== 0 ||
  Object.values(evaluations.release_policy).some((value) => value !== false) ||
  !evaluations.required_per_route.includes("truthful_selected_provider_and_upstream_model_disclosure_when_asked")
) {
  throw new Error("all_routes_require_real_evaluation_evidence");
}

const evaluated = catalog.evaluated_self_hosted_candidates;
for (const source of [candidate, cosmo, nova]) {
  if (!evaluated.some((item) => item.model === source.base_model && item.revision === source.base_revision && item.license === source.base_license)) {
    throw new Error(`catalog_missing_verified_candidate:${source.base_model}`);
  }
}
if (cosmo.runpod.paid_benchmark_authorized !== false || nova.execution.authorized !== false) {
  throw new Error("candidate_specific_paid_execution_must_stay_blocked");
}
if (catalog.physical_engines.some((engine) => engine.deployment_ready !== false || engine.upstream_model !== null)) {
  throw new Error("unselected_physical_engines_must_stay_blocked");
}
if (catalog.public_profiles.some((profile) => profile.deployment_ready !== false || profile.separate_foundation_weights !== false)) {
  throw new Error("public_profiles_must_be_truthful_and_blocked");
}

console.log("Validated Kova two-engine planning stack; paid execution and production routing remain blocked.");
