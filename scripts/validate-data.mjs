import { readFile } from "node:fs/promises";

const body = await readFile(new URL("../data/starter-v0.1.jsonl", import.meta.url), "utf8");
const rows = body.split(/\r?\n/u).filter(Boolean).map((line) => JSON.parse(line));
const ids = new Set();
const splits = new Set();
for (const row of rows) {
  if (!row.id || ids.has(row.id)) throw new Error("invalid_or_duplicate_id");
  ids.add(row.id);
  if (!["train", "validation"].includes(row.split)) throw new Error("invalid_split");
  splits.add(row.split);
  if (!Array.isArray(row.messages) || row.messages.length < 2) throw new Error("invalid_messages");
  if (!row.provenance?.source || !row.provenance?.license) throw new Error("missing_provenance");
  if (row.provenance.private_data !== false) throw new Error("private_data_prohibited");
}
if (!splits.has("train") || !splits.has("validation")) throw new Error("missing_split");
console.log(`Validated ${rows.length} public-safe Kova records.`);
