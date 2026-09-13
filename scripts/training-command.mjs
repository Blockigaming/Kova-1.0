import { readFile } from "node:fs/promises";
import process from "node:process";

const candidate = JSON.parse(await readFile(new URL("../config/candidate.v1.json", import.meta.url)));
const stack = JSON.parse(await readFile(new URL("../config/training-stack.v1.json", import.meta.url)));
const execute = process.argv.includes("--execute");
const command = [
  "swift", "sft", "--model", candidate.base_model,
  "--model_revision", candidate.base_revision,
  "--tuner_type", "lora",
  "--dataset", "/workspace/kova/dataset/train.jsonl",
  "--val_dataset", "/workspace/kova/dataset/validation.jsonl",
  "--torch_dtype", "bfloat16",
  "--num_train_epochs", "1",
  "--per_device_train_batch_size", "1",
  "--per_device_eval_batch_size", "1",
  "--gradient_accumulation_steps", "8",
  "--learning_rate", "1e-4",
  "--lora_rank", "8", "--lora_alpha", "32",
  "--target_modules", "all-linear",
  "--freeze_vit", "true", "--freeze_aligner", "true",
  "--max_length", String(candidate.training.maximum_length),
  "--save_steps", "10", "--save_total_limit", "2", "--logging_steps", "1",
  "--output_dir", "/workspace/kova/checkpoints",
];
if (!execute) {
  console.log(JSON.stringify({ mode: "dry-run", command, paid_resources_started: false }));
  process.exit(0);
}
const blockers = [];
if (candidate.execution.authorized !== true) blockers.push("candidate_not_authorized");
if (candidate.execution.single_gpu_compatibility_verified !== true) {
  blockers.push("single_gpu_compatibility_unverified");
}
if (stack.execution_authorized !== true) blockers.push("stack_not_authorized");
console.error(`Kova paid training blocked: ${blockers.join(", ")}`);
process.exit(1);
