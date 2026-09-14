import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";
import { realizedMargin, requiredPrice } from "../scripts/price-floor.mjs";

const root = fileURLToPath(new URL("..", import.meta.url));
for (const script of ["validate-data.mjs", "validate-stack.mjs"]) {
  test(`${script} passes`, () => {
    const result = spawnSync(process.execPath, [join(root, "scripts", script)], { encoding: "utf8" });
    assert.equal(result.status, 0, result.stderr);
  });
}

test("dataset compiler creates hashed isolated splits", () => {
  const output = mkdtempSync(join(tmpdir(), "kova-data-"));
  const result = spawnSync(
    process.execPath,
    [join(root, "scripts/compile-dataset.mjs"), `--output=${output}`],
    { cwd: root, encoding: "utf8" },
  );
  assert.equal(result.status, 0, result.stderr);
  const manifest = JSON.parse(readFileSync(join(output, "manifest.json"), "utf8"));
  assert.equal(manifest.source_records, 4);
  assert.equal(manifest.files.train.records, 3);
  assert.equal(manifest.files.validation.records, 1);
  assert.match(manifest.files.train.sha256, /^[a-f0-9]{64}$/u);
});

test("training defaults to dry-run and paid execution stays blocked", () => {
  const script = join(root, "scripts/training-command.mjs");
  const dryRun = spawnSync(process.execPath, [script], { cwd: root, encoding: "utf8" });
  assert.equal(dryRun.status, 0, dryRun.stderr);
  assert.equal(JSON.parse(dryRun.stdout).paid_resources_started, false);
  const execute = spawnSync(process.execPath, [script, "--execute"], {
    cwd: root,
    encoding: "utf8",
  });
  assert.equal(execute.status, 1);
  assert.match(execute.stderr, /paid training blocked/i);
});

test("Runpod plan scales to zero and stays blocked from paid execution", () => {
  const config = JSON.parse(readFileSync(join(root, "config/runpod-serverless.v1.json"), "utf8"));
  assert.equal(config.worker_type, "flex");
  assert.equal(config.active_workers, 0);
  assert.equal(config.billing.usage_model, "metered_pay_per_second");
  assert.equal(config.billing.flat_rate_plan, false);
  assert.equal(config.billing.auto_pay_enabled, false);
  assert.equal(config.billing.automatic_credit_reload_allowed, false);
  assert.equal(config.safety.paid_execution_authorized, false);
  assert.equal(config.safety.deployment_authorized, false);
});

test("model catalog keeps both unselected engines and all public profiles blocked", () => {
  const catalog = JSON.parse(readFileSync(join(root, "config/model-catalog.v1.json"), "utf8"));
  assert.deepEqual(catalog.physical_engines.map((engine) => engine.id), ["kova-core", "kova-ultra"]);
  for (const engine of catalog.physical_engines) {
    assert.equal(engine.upstream_model, null, engine.id);
    assert.equal(engine.deployment_ready, false, engine.id);
  }
  for (const profile of catalog.public_profiles) {
    assert.equal(profile.separate_foundation_weights, false, profile.id);
    assert.equal(profile.deployment_ready, false, profile.id);
  }
});

test("price floor targets a 42.6% gross margin before rounding", () => {
  const price = requiredPrice(0.574);
  assert.ok(Math.abs(price - 1) < 1e-12);
  assert.ok(Math.abs(realizedMargin(0.574, price) - 0.426) < 1e-12);
});

test("product target contains six chat modes and eighteen Work combinations", () => {
  const surface = JSON.parse(readFileSync(join(root, "config/product-surface.v1.json"), "utf8"));
  assert.deepEqual(surface.chat_modes.map((mode) => mode.display_name), [
    "Instant", "Medium", "High", "Extra High", "Max", "Ultra",
  ]);
  assert.equal(surface.work_families.length * surface.work_efforts.length, 18);
  assert.equal(surface.chat_modes.find((mode) => mode.id === "instant").activity_updates, false);
  assert.equal(surface.chat_modes.find((mode) => mode.id === "ultra").activity_updates, true);
  assert.ok(surface.chat_modes.slice(0, 5).every((mode) => mode.engine === "kova-core"));
  assert.equal(surface.chat_modes.at(-1).engine, "kova-ultra");
});

test("provider architecture preserves Azure and exposes Cloudflare billing tradeoff", () => {
  const config = JSON.parse(readFileSync(join(root, "config/provider-architecture.v1.json"), "utf8"));
  assert.equal(config.application_plane.provider, "azure_container_apps");
  assert.equal(config.application_plane.delete_existing_azure_deployments, false);
  const core = config.engines.find((engine) => engine.id === "kova-core");
  assert.equal(core.provider, "cloudflare_workers_ai");
  assert.equal(core.selected_model, null);
  assert.equal(core.billing.satisfies_no_flat_fee_and_no_prepaid_credits, false);
  const ultra = config.engines.find((engine) => engine.id === "kova-ultra");
  assert.equal(ultra.provider, "runpod_serverless");
  assert.equal(ultra.active_workers, 0);
});
