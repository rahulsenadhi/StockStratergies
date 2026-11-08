import path from "node:path";
import { isObj, loadVersionedJson } from "@/lib/desk/versioned-json";
import type { UiIpo } from "@/lib/desk/ipo-text";

export * from "@/lib/desk/ipo-text";

/** Written by precompute_ui_ipo.py after every data update (schema version 1). */
export const IPO_FILE = "ui_ipo.json";
export const IPO_VERSION = 1;
const DEFAULT_DATA_DIR = process.env.DATA_DIR ?? "..";

export type IpoResult =
  | { ok: true; data: UiIpo }
  | { ok: false; reason: "missing" | "invalid" | "version" };

function hasShape(v: Record<string, unknown>): boolean {
  return isObj(v.counts) && Array.isArray(v.signals) && Array.isArray(v.trades) && Array.isArray(v.extra_columns);
}

/** Read and check the saved IPO page data. Never throws: a broken file becomes an empty state. */
export async function loadIpo(dataDir: string = DEFAULT_DATA_DIR): Promise<IpoResult> {
  const res = await loadVersionedJson(path.join(dataDir, IPO_FILE), IPO_VERSION, hasShape);
  return res.ok ? { ok: true, data: res.value as unknown as UiIpo } : res;
}
