import { createHash } from "node:crypto";
import { readdir, readFile, stat, writeFile } from "node:fs/promises";
import { join, resolve } from "node:path";
import process from "node:process";

const directory = resolve(
  process.argv.find((value) => value.startsWith("--directory="))?.slice(12) ?? "artifacts/checkpoint",
);
const output = resolve(
  process.argv.find((value) => value.startsWith("--output="))?.slice(9) ??
    "artifacts/checkpoint-manifest.json",
);
const names = (await readdir(directory)).sort();
if (!names.length) throw new Error("empty_checkpoint");
const files = [];
for (const name of names) {
  const path = join(directory, name);
  if (!(await stat(path)).isFile()) continue;
  const body = await readFile(path);
  files.push({ name, bytes: body.length, sha256: createHash("sha256").update(body).digest("hex") });
}
if (!files.some(({ name }) => name === "adapter_config.json")) {
  throw new Error("adapter_config_missing");
}
await writeFile(output, `${JSON.stringify({ schema_version: 1, files }, null, 2)}\n`, {
  encoding: "utf8",
  flag: "wx",
});
console.log(`Recorded ${files.length} checkpoint files.`);
