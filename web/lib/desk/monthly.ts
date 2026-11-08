import fs from "node:fs/promises";
import path from "node:path";
import type { UiMonthly } from "@/lib/desk/monthly-text";

export * from "@/lib/desk/monthly-text";

/** Written by precompute_ui_monthly.py after every data update (schema version 1). */
export const MONTHLY_FILE = "ui_monthly.json";
export const MONTHLY_VERSION = 1;
const DEFAULT_DATA_DIR = process.env.DATA_DIR ?? "..";

export type MonthlyResult =
  | { ok: true; data: UiMonthly }
  | { ok: false; reason: "missing" | "invalid" | "version" };

const isObj = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null;

function hasShape(v: Record<string, unknown>): boolean {
  const { rebalances } = v;
  return (
    Array.isArray(v.ranking) && Array.isArray(v.checks) && Array.isArray(v.top5) &&
    isObj(v.filters) && isObj(v.closes) && isObj(rebalances) && Array.isArray(rebalances.rows)
  );
}

/** Read and check the saved Monthly page data. Never throws: a broken file becomes an empty state. */
export async function loadMonthly(dataDir: string = DEFAULT_DATA_DIR): Promise<MonthlyResult> {
  let text: string;
  try {
    text = await fs.readFile(path.join(dataDir, MONTHLY_FILE), "utf-8");
  } catch {
    return { ok: false, reason: "missing" };
  }
  let raw: unknown;
  try {
    raw = JSON.parse(text);
  } catch {
    return { ok: false, reason: "invalid" };
  }
  if (!isObj(raw)) return { ok: false, reason: "invalid" };
  if (raw.version !== MONTHLY_VERSION) {
    return typeof raw.version === "number" ? { ok: false, reason: "version" } : { ok: false, reason: "invalid" };
  }
  if (!hasShape(raw)) return { ok: false, reason: "invalid" };
  return { ok: true, data: raw as unknown as UiMonthly };
}
