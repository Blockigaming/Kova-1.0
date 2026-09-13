import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";

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
