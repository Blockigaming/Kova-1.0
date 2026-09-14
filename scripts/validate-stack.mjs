import { readFile } from "node:fs/promises";

const load = async (name) => JSON.parse(await readFile(new URL(`../config/${name}`, import.meta.url)));
const [
  candidate, stack, runpod, catalog, economics, identity, inference, hardware, surface,
  activity, completion, evaluations, nova, cosmo, architecture, routes, ultraPlan,
  coreServing,
] = await Promise.all([
  "candidate.v1.json", "training-stack.v1.json", "runpod-serverless.v1.json",
  "model-catalog.v1.json", "economics.v1.json", "identity.v1.json",
  "inference-contract.v1.json", "hardware-benchmark.v1.json", "product-surface.v1.json",
  "activity-event.v1.json", "completion-target.v1.json", "evaluation-gates.v1.json",
  "nova-candidate.v1.json", "cosmo-candidate.v1.json", "provider-architecture.v1.json",
  "route-policy.v1.json", "ultra-orchestration.v1.json",
  "core-serving.v1.json",
].map(load));

if (candidate.base_model !== "Qwen/Qwen3.8-27B" || !/^[a-f0-9]{40}$/u.test(candidate.base_revision)) {
  throw new Error("unexpected_or_unpinned_self_hosted_candidate");
}
if (candidate.execution.authorized !== false || stack.status !== "planning_only" || stack.execution_authorized !== false) {
  throw new Error("planning_only_required");
}
if (runpod.provider !== "runpod_serverless" || runpod.worker_type !== "flex" || runpod.active_workers !== 0) {
  throw new Error("runpod_must_scale_to_zero");
}
if (
  runpod.physical_endpoint_count !== 2 || runpod.endpoints.length !== 2 ||
  runpod.endpoints.map((endpoint) => endpoint.id).join(",") !== "kova-core,kova-ultra" ||
  runpod.endpoints.some((endpoint) =>
    endpoint.name_reserved !== endpoint.id ||
    endpoint.deployed !== false || endpoint.worker_type !== "flex" || endpoint.active_workers !== 0 ||
    endpoint.max_workers !== 1 || endpoint.flashboot_required !== true ||
    endpoint.cached_model_required !== true || endpoint.streaming_required !== true
  )
) throw new Error("two_blocked_scale_to_zero_runpod_endpoints_required");
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
for (const field of [
  "record_type", "request_id", "attempt_id", "outcome", "model", "model_revision", "route_id",
  "stage_id", "public_response", "worker_lifecycle_id", "measurement_source", "cold_start",
  "time_to_first_token_ms", "gpu_rate_per_second_usd", "gpu_type_id", "gpu_count",
  "serving_engine", "endpoint_type", "container_image_digest",
]) {
  if (!inference.telemetry.attempt_record_required.includes(field)) throw new Error(`inference_attempt_telemetry_missing:${field}`);
}
for (const field of ["record_type", "close_event_id", "worker_lifecycle_id", "attributed_idle_timeout_ms"]) {
  if (!inference.telemetry.lifecycle_close_record_required.includes(field)) throw new Error(`inference_lifecycle_telemetry_missing:${field}`);
}
if (inference.telemetry.lifecycle_close_source !== "trusted_runtime_shutdown_observation") throw new Error("trusted_lifecycle_close_required");
if (
  inference.safety.paid_execution_authorized !== false ||
  inference.safety.accept_arbitrary_model_from_request !== false ||
  inference.safety.return_hidden_reasoning !== false
) throw new Error("inference_must_remain_source_only_and_pinned");
if (
  inference.request.allowed_client_message_roles.join(",") !== "user,assistant" ||
  inference.request.caller_supplied_tool_results_allowed !== false
) throw new Error("caller_tool_results_must_be_rejected");
if (hardware.model !== candidate.base_model || hardware.paid_benchmark_authorized !== false) {
  throw new Error("hardware_benchmark_must_match_candidate_and_stay_blocked");
}
if (hardware.minimum_unquantized_vram_gb < 80 || hardware.candidates.some((gpu) => gpu.vram_gb < 80 || gpu.benchmark_complete !== false)) {
  throw new Error("unquantized_candidates_require_unbenchmarked_80gb_gpu");
}

if (
  architecture.status !== "planning_only" || architecture.application_plane.provider !== "azure_container_apps" ||
  architecture.edge_plane.provider !== "cloudflare" || architecture.edge_plane.inference_allowed !== false
) {
  throw new Error("azure_application_plane_must_be_preserved");
}
if (
  architecture.application_plane.delete_existing_azure_deployments !== false ||
  architecture.application_plane.production_routing_authorized !== false ||
  architecture.global_guards.paid_or_production_actions_authorized !== false
) throw new Error("unverified_migration_actions_must_be_blocked");
const core = architecture.engines.find((engine) => engine.id === "kova-core");
const ultra = architecture.engines.find((engine) => engine.id === "kova-ultra");
if (
  architecture.inference_decision.provider !== "runpod_serverless" ||
  architecture.inference_decision.physical_endpoint_count !== 2 ||
  architecture.inference_decision.cloudflare_workers_ai_status !== "rejected_as_primary_inference_backend" ||
  architecture.inference_decision.do_not_claim_cloudflare_benchmark_evidence !== true ||
  architecture.global_guards.one_core_endpoint_serves_all_core_profiles !== true
) throw new Error("two_runpod_engine_decision_required");
if (
  !core || !ultra || [core, ultra].some((engine) =>
    engine.provider !== "runpod_serverless" || engine.endpoint_deployed !== false ||
    engine.worker_type !== "flex" || engine.active_workers !== 0 || engine.selected_model !== null ||
    engine.selected_quantization !== null || engine.selected_gpu !== null ||
    engine.selected_serving_engine !== null || engine.paid_execution_authorized !== false ||
    engine.deployment_authorized !== false || engine.production_routing_authorized !== false
  ) || core.endpoint_name_reserved !== "kova-core" || ultra.endpoint_name_reserved !== "kova-ultra" ||
  ultra.hidden_chain_of_thought_exposed !== false
) throw new Error("both_runpod_engines_must_be_unselected_scale_to_zero_and_blocked");
if (
  coreServing.status !== "source_only_selection_blocked" || coreServing.engine !== "kova-core" ||
  coreServing.provider !== "runpod_serverless" || coreServing.endpoint_name_reserved !== "kova-core" ||
  coreServing.endpoint_deployed !== false || coreServing.selected_serving_engine !== null ||
  coreServing.selected_candidate_id !== null || coreServing.selected_gpu !== null ||
  coreServing.container_image_digest !== null || coreServing.native_context_tokens !== 262144 ||
  coreServing.reasoning_efforts.join(",") !== "low,medium,xhigh" ||
  coreServing.endpoint_type_candidates.join(",") !== "queue_based,load_balancing" ||
  coreServing.container_policy.prebuilt_image_required !== true ||
  coreServing.container_policy.runtime_package_installs_allowed !== false ||
  coreServing.container_policy.streaming_required !== true ||
  coreServing.container_policy.hidden_reasoning_must_be_filtered !== true ||
  Object.values(coreServing.safety).some((value) => value !== false)
) throw new Error("runpod_core_serving_selection_must_stay_blocked");
const bf16Core = coreServing.candidates.find((model) => model.model === candidate.base_model);
const fp8Core = coreServing.candidates.find((model) => model.model === cosmo.base_model);
if (
  coreServing.candidates.length !== 2 || !bf16Core || !fp8Core ||
  bf16Core.revision !== candidate.base_revision || bf16Core.license !== candidate.base_license ||
  fp8Core.revision !== cosmo.base_revision || fp8Core.license !== cosmo.base_license ||
  coreServing.candidates.some((model) =>
    model.context_tokens !== 262144 || model.compatibility_verified !== false || model.benchmark_complete !== false
  )
) throw new Error("verified_unbenchmarked_core_candidates_required");
if (
  ultraPlan.status !== "source_only" || ultraPlan.engine !== "kova-ultra" ||
  ultraPlan.provider !== "runpod_serverless" || ultraPlan.worker_type !== "flex" ||
  ultraPlan.endpoint_name_reserved !== "kova-ultra" || ultraPlan.endpoint_deployed !== false ||
  ultraPlan.active_workers !== 0 || ultraPlan.required_entitlement !== "pro" ||
  ultraPlan.minimum_specialists !== 2 || ultraPlan.maximum_specialists !== 5 ||
  ultraPlan.maximum_debate_rounds !== 1 || ultraPlan.selected_model !== null ||
  ultraPlan.required_stages.join(",") !== "specialists,disagreement_check,judge,conditional_debate,synthesis" ||
  ultraPlan.hidden_chain_of_thought_exposed !== false ||
  ultraPlan.paid_execution_authorized !== false || ultraPlan.deployment_authorized !== false ||
  ultraPlan.production_routing_authorized !== false
) throw new Error("ultra_orchestration_must_be_bounded_and_blocked");

const expectedChatModes = ["instant", "medium", "high", "extra-high", "max", "ultra"];
if (
  surface.assistant_name !== "Kova" || surface.auto_route.id !== "kova-auto" ||
  surface.auto_route.classifier_implemented !== true || surface.auto_route.deployment_ready !== false
) {
  throw new Error("blocked_kova_auto_surface_required");
}
if (surface.chat_modes.map((mode) => mode.id).join(",") !== expectedChatModes.join(",")) throw new Error("six_ordered_chat_modes_required");
if (
  surface.chat_modes.map((mode) => mode.display_name).join(",") !==
  "Kova 5.6 Cosmo,Kova 5.6 Orion,Kova 5.6 Nova,Nova Extra High,Nova Max,Kova Ultra"
) throw new Error("product_surface_kova_names_invalid");
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
if (
  !routes.caller_forbidden_fields.includes("model") ||
  !routes.caller_forbidden_fields.includes("engine") ||
  !routes.caller_forbidden_fields.includes("behavior_contract_id")
) {
  throw new Error("route_provider_and_model_must_be_server_controlled");
}
if (
  routes.work.family_profiles.length !== 3 ||
  new Set(routes.work.family_profiles.map((profile) => profile.behavior_contract_id)).size !== 3 ||
  new Set(routes.work.family_profiles.map((profile) => profile.answer_style)).size !== 3 ||
  new Set(routes.work.family_profiles.map((profile) => profile.tool_posture)).size !== 3
) throw new Error("work_families_require_distinct_behavior_contracts");
if (
  routes.work.effort_profiles.length !== 6 ||
  routes.work.effort_profiles.map((profile) => profile.name).join(",") !== routes.work.efforts.join(",") ||
  routes.work.effort_profiles.slice(0, 5).some((profile) => profile.engine !== "kova-core") ||
  routes.work.effort_profiles[5].engine !== "kova-ultra"
) throw new Error("work_effort_route_contracts_invalid");

if (surface.deep_mode_experience.hidden_chain_of_thought_exposed !== false || activity.rules.may_expose_hidden_reasoning !== false) {
  throw new Error("hidden_reasoning_must_stay_private");
}
if (activity.rules.must_follow_real_runtime_or_tool_event !== true || activity.rules.may_claim_unstarted_action !== false) {
  throw new Error("activity_must_be_truthfully_grounded");
}
if (!activity.required_fields.includes("grounding_operation_id")) throw new Error("activity_runtime_grounding_id_required");
if (completion.baseline_percent !== 0 || completion.current_verified_percent !== 22 || completion.live_model_routes !== 0 || completion.target_model_routes !== 25) {
  throw new Error("completion_progress_contract_mismatch");
}
if (
  evaluations.status !== "all_routes_blocked" || evaluations.target_routes !== 25 ||
  evaluations.passing_routes.length !== 0 ||
  evaluations.offline_contract_evidence.status !== "passed" ||
  evaluations.offline_contract_evidence.route_contracts_checked !== 25 ||
  evaluations.offline_contract_evidence.actual_model_outputs_evaluated !== false ||
  evaluations.offline_contract_evidence.quality_or_factuality_claimed !== false ||
  evaluations.offline_contract_evidence.paid_provider_calls !== 0 ||
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
if (
  catalog.user_facing_hierarchy.map((mode) => mode.display_name).join(",") !==
  "Kova Auto,Kova 5.6 Cosmo,Kova 5.6 Orion,Kova 5.6 Nova,Nova Extra High,Nova Max,Kova Ultra"
) throw new Error("final_kova_mode_hierarchy_required");

console.log("Validated Kova two-engine planning stack; paid execution and production routing remain blocked.");
