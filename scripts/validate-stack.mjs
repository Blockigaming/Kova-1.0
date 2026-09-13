import { readFile } from "node:fs/promises";

const candidate = JSON.parse(await readFile(new URL("../config/candidate.v1.json", import.meta.url)));
const stack = JSON.parse(await readFile(new URL("../config/training-stack.v1.json", import.meta.url)));
if (candidate.base_model !== "Qwen/Qwen3.8-27B") throw new Error("unexpected_model");
if (!/^[a-f0-9]{40}$/u.test(candidate.base_revision)) throw new Error("unpinned_revision");
if (candidate.execution.authorized !== false) throw new Error("execution_must_be_blocked");
if (stack.status !== "planning_only" || stack.execution_authorized !== false) {
  throw new Error("planning_only_required");
}
console.log("Validated Kova planning stack; paid execution remains blocked.");
