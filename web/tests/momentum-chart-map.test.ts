import { describe, expect, it } from "vitest";
import {
  PERIOD_BARS, mapChart, repairText, windowStart, type ChartToggles, type MomentumChartFile,
} from "@/lib/desk/momentum-chart-map";

// Text a cp1252 mix-up produced from UTF-8 (what the saved files hold today).
const RUPEE_BAD = "â‚¹";
const TRI_BAD = "â–²";

const dates = Array.from({ length: 800 }, (_, i) => `d${String(i).padStart(4, "0")}`);
const lastN = (n: number) => dates.slice(-n);
const line = (name: string, row: number) => ({
  name, type: "line" as const, row, colour: "#111111", dash: "solid", opacity: null,
  points: dates.map((d, i) => [d, i] as [string, number | null]),
});
const CHART = {
  version: 1, symbol: "X", rows: ["price", "rsi", "macd", "volume"], note: null, generated_at: "t",
  since_line: `Since ${TRI_BAD} +1%`,
  badges: [{ label: "RSI(14)", value: "60", sub: "Bullish", colour: "#22C55E" }],
  traces: [
    { name: "Price", type: "candlestick", row: 1, colour: "#22C55E", colour_down: "#EF4444", dash: "solid",
      points: dates.map((d, i) => [d, i, i + 2, i - 1, i + 1]) },
    line("SMA 50", 1), line("BB Upper", 1), line("BB Lower", 1), line("RSI(14)", 2),
    { name: "MACD Hist", type: "bar", row: 3, colour: null, dash: "solid", opacity: 0.5,
      points: dates.map((d, i) => [d, i, i % 2 ? "#22C55E" : "#EF4444"]) },
    line("MACD", 3),
    { name: "Volume", type: "bar", row: 4, colour: null, dash: "solid", opacity: 0.45,
      points: dates.map((d) => [d, 5, "#22C55E"]) },
    line("OBV (scaled)", 4),
    { name: "BUY", type: "markers", row: 1, colour: "#22C55E", dash: "solid", symbol: "triangle-up",
      points: [[dates[10], 1], [dates[790], 2]] },
  ],
  shapes: [
    { kind: "hline", row: 1, value: 50, colour: "red", dash: "dash", label: `52W High ${RUPEE_BAD}50` },
    { kind: "hline", row: 2, value: 70, colour: "red", dash: "dot", label: null },
    { kind: "vline", row: 1, value: dates[790], colour: "blue", dash: "dash", label: null },
  ],
} as unknown as MomentumChartFile;
const ALL: ChartToggles = { bb: true, rsi: true, macd: true, vol: true };

describe("windowStart", () => {
  it("keeps the last N sessions for every period", () => {
    for (const [p, n] of Object.entries(PERIOD_BARS)) {
      expect(windowStart(CHART, p as keyof typeof PERIOD_BARS)).toBe(lastN(n)[0]);
    }
  });
  it("uses the whole history when it is shorter than the period", () => {
    const short = { ...CHART, traces: (CHART.traces ?? []).map((t) => ({ ...t, points: t.points.slice(-5) })) } as MomentumChartFile;
    expect(windowStart(short, "3Y")).toBe(dates[795]);
  });
});

describe("mapChart", () => {
  const plan = mapChart(CHART, "1M", ALL);
  const find = (name: string) => plan.series.find((s) => s.name === name);
  it("slices every series and the markers to the period", () => {
    for (const s of plan.series) expect(s.data.length).toBe(21);
    expect(plan.markers.map((m) => m.time)).toEqual([dates[790]]);
  });
  it("puts each row in its own pane in order", () => {
    expect(find("Price")?.pane).toBe(0);
    expect(find("RSI(14)")?.pane).toBe(1);
    expect(find("MACD")?.pane).toBe(2);
    expect(find("OBV (scaled)")?.pane).toBe(3);
    expect(plan.paneCount).toBe(4);
  });
  it("uses the saved per-bar colour for bars and the saved down colour for candles", () => {
    const hist = find("MACD Hist");
    expect(hist?.kind).toBe("hist");
    expect(hist?.data[0]).toMatchObject({ color: expect.stringMatching(/^rgba\(/) });
    expect(find("Price")).toMatchObject({ kind: "candles", colour: "#22C55E", colourDown: "#EF4444" });
  });
  it("turns off a group and closes the gap between panes", () => {
    const p = mapChart(CHART, "1Y", { ...ALL, rsi: false, bb: false });
    expect(p.series.some((s) => s.name === "RSI(14)" || s.name.startsWith("BB "))).toBe(false);
    expect(p.series.find((s) => s.name === "MACD")?.pane).toBe(1);
    expect(p.lines.map((l) => l.pane)).toEqual([0]);
  });
  it("leaves the price pane only when every optional group is off", () => {
    const p = mapChart(CHART, "1Y", { bb: false, rsi: false, macd: false, vol: false });
    expect(new Set(p.series.map((s) => s.pane))).toEqual(new Set([0]));
    expect(p.paneCount).toBe(1);
  });
  it("maps horizontal lines with their label and drops vertical lines", () => {
    expect(plan.lines).toEqual([
      expect.objectContaining({ pane: 0, value: 50, title: "52W High ₹50" }),
      expect.objectContaining({ pane: 1, value: 70, title: "" }),
    ]);
  });
  it("repairs the since line text", () => {
    expect(plan.sinceLine).toBe("Since ▲ +1%");
  });
  it("maps a gap value to a whitespace point", () => {
    const withGap = { ...CHART, traces: (CHART.traces ?? []).map((t) => (t.name === "SMA 50"
      ? { ...t, points: t.points.map((p, i) => (i === 799 ? [p[0], null] : p)) } : t)) } as MomentumChartFile;
    const s = mapChart(withGap, "1M", ALL).series.find((x) => x.name === "SMA 50");
    expect(s?.data[20]).toEqual({ time: dates[799] });
  });
});

describe("repairText", () => {
  it("fixes UTF-8 text that was decoded as cp1252", () => {
    expect(repairText(`52W High ${RUPEE_BAD}12,329`)).toBe("52W High ₹12,329");
    expect(repairText("a Â· b")).toBe("a · b");
  });
  it("leaves clean text alone", () => {
    expect(repairText("52W High ₹12,329 · Âbc")).toBe("52W High ₹12,329 · Âbc");
    expect(repairText("plain")).toBe("plain");
  });
});
