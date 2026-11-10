import { hexRgba } from "@/lib/desk/colour";

/** Streamlit _PERIOD_BARS (without "All"): how many sessions each period shows. */
export const PERIOD_BARS = { "1M": 21, "3M": 63, "6M": 126, "1Y": 252, "3Y": 756 } as const;
export type Period = keyof typeof PERIOD_BARS;
export const PERIODS = Object.keys(PERIOD_BARS) as Period[];
export const DEFAULT_PERIOD: Period = "1Y";

export const CHART_EMPTY = {
  title: "No indicator chart is saved for this stock",
  reason: "Run a data update on the Momentum page to build it.",
};
export const CHART_ERROR = "The indicator chart could not be loaded. Try selecting the stock again.";

/** One saved trace from precompute_ui_momentum_charts.py. Points are [date, ...values]. */
export interface ChartTrace {
  name: string;
  type: "candlestick" | "line" | "bar" | "markers";
  row: number;
  colour: string | null;
  colour_down?: string | null;
  dash: string;
  symbol?: string | null;
  opacity?: number | null;
  points: [string, ...(number | string | null)[]][];
}
export interface ChartShape {
  kind: "hline" | "vline";
  row: number;
  value: number | string;
  colour: string;
  dash: string;
  label: string | null;
}
export interface ChartBadge { label: string; value: string; sub: string; colour: string }
export interface MomentumChartFile {
  version: number;
  symbol: string;
  rows?: string[];
  traces?: ChartTrace[];
  shapes?: ChartShape[];
  badges?: ChartBadge[];
  since_line?: string | null;
  note?: string | null;
  generated_at?: string;
}

export interface ChartToggles { bb: boolean; rsi: boolean; macd: boolean; vol: boolean }
export type ToggleKey = keyof ChartToggles;

export type SeriesKind = "candles" | "line" | "hist";
export interface SeriesSpec {
  name: string;
  kind: SeriesKind;
  pane: number;
  colour: string;
  colourDown: string;
  dash: string;
  data: Record<string, unknown>[];
}
export interface LineSpec { pane: number; row: number; value: number; colour: string; dash: string; title: string }
export interface MarkerSpec {
  time: string;
  position: "aboveBar" | "belowBar";
  shape: "arrowUp" | "arrowDown" | "circle";
  color: string;
  text: string;
}
export interface ChartPlan {
  series: SeriesSpec[];
  lines: LineSpec[];
  markers: MarkerSpec[];
  paneCount: number;
  sinceLine: string | null;
  badges: ChartBadge[];
}

const FALLBACK_COLOUR = "#94A3B8";

/** Date of the first session shown for a period, or null with no candles. */
export function windowStart(chart: MomentumChartFile, period: Period): string | null {
  const price = (chart.traces ?? []).find((t) => t.type === "candlestick");
  if (!price || price.points.length === 0) return null;
  return price.points[Math.max(0, price.points.length - PERIOD_BARS[period])][0];
}

function groupOf(t: ChartTrace): ToggleKey | null {
  if (t.name.startsWith("BB ")) return "bb";
  if (t.row === 2) return "rsi";
  if (t.row === 3) return "macd";
  if (t.row === 4) return "vol";
  return null;
}

const isNum = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);

function seriesData(t: ChartTrace, start: string): Record<string, unknown>[] {
  const pts = t.points.filter((p) => p[0] >= start);
  if (t.type === "candlestick") {
    return pts.map(([time, o, h, l, c]) =>
      (isNum(o) && isNum(h) && isNum(l) && isNum(c) ? { time, open: o, high: h, low: l, close: c } : { time }));
  }
  if (t.type === "bar") {
    const alpha = t.opacity ?? 1;
    return pts.map(([time, value, colour]) => (isNum(value)
      ? { time, value, color: hexRgba(typeof colour === "string" ? colour : FALLBACK_COLOUR, alpha) }
      : { time }));
  }
  return pts.map(([time, value]) => (isNum(value) ? { time, value } : { time }));
}

function markerFor(t: ChartTrace, time: string): MarkerSpec {
  const color = t.colour ?? FALLBACK_COLOUR;
  if (t.symbol === "triangle-up") return { time, position: "belowBar", shape: "arrowUp", color, text: t.name };
  if (t.symbol === "triangle-down") return { time, position: "aboveBar", shape: "arrowDown", color, text: t.name };
  return { time, position: "aboveBar", shape: "circle", color, text: t.name };
}

/** Map saved traces to chart series for one period and toggle set. Pure: no indicator is computed here. */
export function mapChart(chart: MomentumChartFile, period: Period, toggles: ChartToggles): ChartPlan {
  const start = windowStart(chart, period) ?? "";
  const traces = (chart.traces ?? []).filter((t) => {
    const g = groupOf(t);
    return g === null || toggles[g];
  });
  const rows = [...new Set([1, ...traces.filter((t) => t.type !== "markers").map((t) => t.row)])].sort((a, b) => a - b);
  const paneOf = (row: number) => rows.indexOf(row);

  const series: SeriesSpec[] = [];
  const markers: MarkerSpec[] = [];
  for (const t of traces) {
    if (t.type === "markers") {
      for (const p of t.points) if (p[0] >= start) markers.push(markerFor(t, p[0]));
      continue;
    }
    series.push({
      name: t.name, kind: t.type === "candlestick" ? "candles" : t.type === "bar" ? "hist" : "line",
      pane: paneOf(t.row), colour: t.colour ?? FALLBACK_COLOUR, colourDown: t.colour_down ?? FALLBACK_COLOUR,
      dash: t.dash, data: seriesData(t, start),
    });
  }
  markers.sort((a, b) => (a.time < b.time ? -1 : a.time > b.time ? 1 : 0));

  const lines: LineSpec[] = (chart.shapes ?? [])
    .filter((s) => s.kind === "hline" && isNum(s.value) && paneOf(s.row) >= 0)
    .map((s) => ({
      pane: paneOf(s.row), row: s.row, value: s.value as number, colour: s.colour, dash: s.dash,
      title: s.label ?? "",
    }));

  return {
    series, lines, markers, paneCount: rows.length,
    sinceLine: chart.since_line || null,
    badges: chart.badges ?? [],
  };
}
