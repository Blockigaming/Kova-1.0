#!/usr/bin/env node

import { pathToFileURL } from "node:url";

const TARGET_MARGIN = 0.426;

function parseCost(raw) {
  const cost = Number(raw);
  if (!Number.isFinite(cost) || cost <= 0) {
    throw new Error("Usage: node scripts/price-floor.mjs <positive-attributable-cost-usd>");
  }
  return cost;
}

export function requiredPrice(cost, targetMargin = TARGET_MARGIN) {
  if (!Number.isFinite(cost) || cost <= 0) throw new TypeError("cost must be positive");
  if (!Number.isFinite(targetMargin) || targetMargin < 0 || targetMargin >= 1) {
    throw new TypeError("targetMargin must be between 0 and 1");
  }
  return cost / (1 - targetMargin);
}

export function realizedMargin(cost, price) {
  if (!Number.isFinite(cost) || cost < 0) throw new TypeError("cost must be non-negative");
  if (!Number.isFinite(price) || price <= 0) throw new TypeError("price must be positive");
  return (price - cost) / price;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try {
    const cost = parseCost(process.argv[2]);
    const price = requiredPrice(cost);
    process.stdout.write(`${JSON.stringify({
      attributable_cost_usd: cost,
      target_gross_margin: TARGET_MARGIN,
      minimum_unrounded_price_usd: price,
      verification: "benchmark_required_before_publication"
    }, null, 2)}\n`);
  } catch (error) {
    process.stderr.write(`${error.message}\n`);
    process.exitCode = 1;
  }
}
