import path from "node:path";
import { isObj, loadVersionedJson } from "@/lib/desk/versioned-json";
import type { UiMomentum } from "@/lib/desk/momentum-text";

export * from "@/lib/desk/momentum-text";

/** Written by precompute_ui_momentum.py after every data update (schema version 1). */
export const MOMENTUM_FILE = "ui_momentum.json";
export const MOMENTUM_VERSION = 1;
const DEFAULT_DATA_DIR = process.env.DATA_DIR ?? "..";

export type MomentumResult =
  | { ok: true; data: UiMomentum }
  | { ok: false; reason: "missing" | "invalid" | "version" };

function hasShape(v: Record<string, unknown>): boolean {
  const { views, tabs, trade_filters: filters } = v;
  return (
    isObj(views) && isObj(views.all) && isObj(views.ath) && isObj(tabs) && isObj(filters) && isObj(v.details) &&
    Array.isArray(v.signals) && Array.isArray(v.recent) && Array.isArray(v.trades)
  );
}

/** Read and check the saved Momentum page data. Never throws: a broken file becomes an empty state. */
export async function loadMomentum(dataDir: string = DEFAULT_DATA_DIR): Promise<MomentumResult> {
  const res = await loadVersionedJson(path.join(dataDir, MOMENTUM_FILE), MOMENTUM_VERSION, hasShape);
  return res.ok ? { ok: true, data: res.value as unknown as UiMomentum } : res;
}
