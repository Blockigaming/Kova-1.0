import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
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
