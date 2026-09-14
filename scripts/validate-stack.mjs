import { readFile } from "node:fs/promises";

const candidate = JSON.parse(await readFile(new URL("../config/candidate.v1.json", import.meta.url)));
const stack = JSON.parse(await readFile(new URL("../config/training-stack.v1.json", import.meta.url)));
const runpod = JSON.parse(await readFile(new URL("../config/runpod-serverless.v1.json", import.meta.url)));
const catalog = JSON.parse(await readFile(new URL("../config/model-catalog.v1.json", import.meta.url)));
const economics = JSON.parse(await readFile(new URL("../config/economics.v1.json", import.meta.url)));
const identity = JSON.parse(await readFile(new URL("../config/identity.v1.json", import.meta.url)));
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
if (runpod.safety.paid_execution_authorized !== false || runpod.safety.deployment_authorized !== false) {
  throw new Error("runpod_paid_actions_must_be_blocked");
}
if (economics.target_gross_margin !== 0.426 || economics.cost_fraction !== 0.574) {
  throw new Error("unexpected_margin_target");
}
if (economics.enforcement.allow_unmeasured_price_publication !== false) {
  throw new Error("unmeasured_prices_must_be_blocked");
}
if (identity.assistant_name !== "Kova" || !identity.forbidden_claims.includes("kova_foundation_trained_from_scratch")) {
  throw new Error("truthful_kova_identity_required");
}
for (const model of catalog.models) {
  if (!model.upstream_model && model.deployment_ready !== false) {
    throw new Error(`unverified_model_enabled:${model.id}`);
  }
}
console.log("Validated Kova planning stack; paid execution remains blocked.");
