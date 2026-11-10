import path from "node:path";
import { loadVersionedJson } from "@/lib/desk/versioned-json";
import type { MomentumChartFile } from "@/lib/desk/momentum-chart-map";

/** Folder written by precompute_ui_momentum_charts.py: one <SYMBOL>.json per stock (schema version 1). */
export const CHART_DIR = "ui_momentum_charts";
export const CHART_VERSION = 1;
/** Symbols as the desk names them: bare NSE codes ("M&M") or BSE codes ("519477.BO"). */
export const SYMBOL_PATTERN = /^[A-Z0-9&.-]{1,20}$/;

export type ChartResult =
  | { ok: true; chart: MomentumChartFile }
  | { ok: false; reason: "missing" | "invalid" | "version" };

const optionalArray = (v: unknown) => v === undefined || Array.isArray(v);

/** Read one saved chart. A file holding only `note` is valid (the page shows it as an empty state). Never throws. */
export async function loadMomentumChart(
  symbol: string,
  dataDir: string = process.env.DATA_DIR ?? "..",
): Promise<ChartResult> {
  if (!SYMBOL_PATTERN.test(symbol)) return { ok: false, reason: "missing" };
  const file = path.join(dataDir, CHART_DIR, `${symbol}.json`);
  const res = await loadVersionedJson(file, CHART_VERSION, (v) =>
    optionalArray(v.traces) && optionalArray(v.shapes) && optionalArray(v.badges));
  return res.ok ? { ok: true, chart: res.value as unknown as MomentumChartFile } : res;
}
