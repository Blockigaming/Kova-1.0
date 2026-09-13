import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import process from "node:process";

const option = (name, fallback) =>
  process.argv.find((value) => value.startsWith(`${name}=`))?.slice(name.length + 1) ?? fallback;
const source = resolve(option("--source", "data/starter-v0.1.jsonl"));
const output = resolve(option("--output", "artifacts/dataset"));
const raw = await readFile(source, "utf8");
const records = raw.split(/\r?\n/u).filter(Boolean).map((line) => JSON.parse(line));
const splits = { train: [], validation: [] };

for (const record of records) {
  if (!(record.split in splits)) throw new Error(`unsupported_split:${record.split}`);
  splits[record.split].push(JSON.stringify({ messages: record.messages }));
}
if (!splits.train.length || !splits.validation.length) throw new Error("both_splits_required");
await mkdir(output, { recursive: true });
const files = {};
for (const [split, lines] of Object.entries(splits)) {
  const body = `${lines.join("\n")}\n`;
  const filename = `${split}.jsonl`;
  await writeFile(resolve(output, filename), body, { encoding: "utf8", flag: "wx" });
  files[split] = {
    filename,
    records: lines.length,
    sha256: createHash("sha256").update(body).digest("hex"),
  };
}
const manifest = {
  schema_version: 1,
  source_sha256: createHash("sha256").update(raw).digest("hex"),
  source_records: records.length,
  files,
  private_data_included: false,
};
await writeFile(resolve(output, "manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`, {
  encoding: "utf8",
  flag: "wx",
});
console.log(JSON.stringify(manifest));
