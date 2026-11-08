import path from "node:path";
import { isObj, loadVersionedJson } from "@/lib/desk/versioned-json";
import type { UiMonthly } from "@/lib/desk/monthly-text";

export * from "@/lib/desk/monthly-text";

/** Written by precompute_ui_monthly.py after every data update (schema version 1). */
export const MONTHLY_FILE = "ui_monthly.json";
export const MONTHLY_VERSION = 1;
const DEFAULT_DATA_DIR = process.env.DATA_DIR ?? "..";

export type MonthlyResult =
  | { ok: true; data: UiMonthly }
  | { ok: false; reason: "missing" | "invalid" | "version" };

function hasShape(v: Record<string, unknown>): boolean {
  const { rebalances } = v;
  return (
    Array.isArray(v.ranking) && Array.isArray(v.checks) && Array.isArray(v.top5) &&
    isObj(v.filters) && isObj(v.closes) && isObj(rebalances) && Array.isArray(rebalances.rows)
  );
}

/** Read and check the saved Monthly page data. Never throws: a broken file becomes an empty state. */
export async function loadMonthly(dataDir: string = DEFAULT_DATA_DIR): Promise<MonthlyResult> {
  const res = await loadVersionedJson(path.join(dataDir, MONTHLY_FILE), MONTHLY_VERSION, hasShape);
  return res.ok ? { ok: true, data: res.value as unknown as UiMonthly } : res;
}
