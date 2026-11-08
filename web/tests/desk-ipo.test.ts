import { describe, expect, test } from "vitest";
import { execFileSync } from "node:child_process";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import {
  chartLabel, HOW_IT_WORKS, loadIpo, resultTone, signalCells, signalTone, summaryStats, tradeCells,
  type IpoCounts, type IpoSignal, type IpoSummary, type IpoTrade, type UiIpo,
} from "@/lib/desk/ipo";

const sig = (extra: Partial<IpoSignal> = {}): IpoSignal => ({
  symbol: "AAA", company: "Alpha Ltd", signal: "Live Breakout", stage: "Stage 3", setup: "U-TURN", close: 1087.75,
  bk_level: 1050, vs_bk: 3.6, vol_ratio: 2.345, ipo_day_val: 539.2, liquidity: "Liquid ✅", promoter: "YES ✅",
  listing_pe: "25.0 🟢", age_days: 88, score: 7, hist_win: 35.4, hist_avg: 1.26, ...extra,
});
const trade = (extra: Partial<IpoTrade> = {}): IpoTrade => ({
  id: 0, symbol: "AAA", entry_date: "2026-01-01", entry_price: 100, exit_date: "2026-06-01", exit_price: 120.5,
  pnl: 20.5, hold_days: 151, exit_reason: "10-day average break", result: "Win",
  extras: { "Entry Stage": "Breakout", "Partial Booked": "No" }, ...extra,
});
const summary: IpoSummary = { cagr: 0.73, total_ret: 7.87, max_dd: -14.9, start: "2016-06-17", end: "2026-11-06" };
const counts: IpoCounts = {
  live_breakout: 2, watch_zone: 1, stage3: 3, stage2: 4, stage1: 5, in_trade: 6, trades: 127, win_rate: 35.43,
};

describe("summaryStats", () => {
  test("exact rows", () => {
    expect(summaryStats(summary, counts)).toEqual([
      { label: "Total return", value: "+7.9%", tone: "gain" },
      { label: "Worst fall from a peak", value: "-14.9%", tone: "loss" },
      { label: "Trades that made money", value: "35%", sub: "127 trades", tone: "warn" },
      { label: "Ready to break out", value: "3", sub: "Recovering: 4 · Building: 5", tone: "gain" },
      { label: "Currently in trade", value: "6", sub: "Live breakout signals: 2", tone: "info" },
    ]);
  });
  test("missing summary and win rate show dashes", () => {
    const rows = summaryStats(null, { ...counts, win_rate: null, stage3: 0, in_trade: 0 });
    expect(rows.map((r) => r.value)).toEqual(["—", "—", "—", "0", "0"]);
    expect(rows.map((r) => r.tone)).toEqual(["muted", "muted", "muted", "muted", "muted"]);
  });
});

describe("signalCells", () => {
  test("Streamlit formats", () => {
    const c = signalCells(sig());
    expect(c).toMatchObject({
      close: "₹1,087.75", bkLevel: "₹1,050.00", vsBk: "+3.6%", volRatio: "2.35×", ipoDayVal: "₹539.2 Cr",
      liquidity: "Liquid ✅", promoter: "YES ✅", listingPe: "25.0 🟢", age: "88", score: "7.0",
      histWin: "35%", histAvg: "+1.3%",
    });
  });
  test("nulls, nan and empty strings show a dash", () => {
    const c = signalCells(sig({
      close: null, hist_win: null, hist_avg: null, vol_ratio: null, ipo_day_val: null,
      listing_pe: "nan", liquidity: "", promoter: "—", company: null,
    }));
    expect(c).toMatchObject({
      close: "—", histWin: "—", histAvg: "—", volRatio: "—", ipoDayVal: "—", listingPe: "—", liquidity: "—",
      promoter: "—", company: "—",
    });
  });
  test("a numeric listing PE prints as is", () => {
    expect(signalCells(sig({ listing_pe: 25.5 })).listingPe).toBe("25.5");
  });
});

describe("tradeCells", () => {
  test("formats and nan extras", () => {
    const c = tradeCells(trade({ extras: { "Entry Stage": "nan", "Partial Booked": "Yes" } }));
    expect(c).toMatchObject({
      entryPrice: "₹100.00", exitPrice: "₹120.50", pnl: "+20.50%", held: "151", result: "Win",
      extras: { "Entry Stage": "—", "Partial Booked": "Yes" },
    });
  });
  test("negative pnl and null exits", () => {
    const c = tradeCells(trade({ pnl: -3.456, exit_price: null, exit_date: null, result: "Open" }));
    expect(c).toMatchObject({ pnl: "-3.46%", exitPrice: "—", exitDate: "—", result: "Open" });
  });
});

describe("tones and labels", () => {
  test("signalTone", () => {
    expect(["Live Breakout", "Watch Zone", "Forming Base", "Avoid", "Other", null].map(signalTone))
      .toEqual(["gain", "warn", "info", "loss", "muted", "muted"]);
  });
  test("resultTone keys off result, not exits", () => {
    expect(["Win", "Loss", "Open", null].map(resultTone)).toEqual(["gain", "loss", "muted", "muted"]);
  });
  test("chartLabel", () => {
    expect(chartLabel(2)).toBe("Simulated account vs Nifty");
    expect(chartLabel(1)).toBe("Simulated account");
    expect(chartLabel(0)).toBe("Simulated account");
  });
  test("HOW_IT_WORKS bolds the lead and the key terms", () => {
    expect(HOW_IT_WORKS.filter((s) => s.bold).map((s) => s.text)).toEqual(["How it works:", "base", "with strong volume"]);
  });
});

describe("loadIpo", () => {
  const withDir = async (content: string | null) => {
    const dir = await fs.mkdtemp(path.join(os.tmpdir(), "ipo-"));
    if (content !== null) await fs.writeFile(path.join(dir, "ui_ipo.json"), content);
    return dir;
  };
  test("missing, invalid, version and ok", async () => {
    expect(await loadIpo(await withDir(null))).toEqual({ ok: false, reason: "missing" });
    expect(await loadIpo(await withDir("{"))).toEqual({ ok: false, reason: "invalid" });
    expect(await loadIpo(await withDir('{"version":2}'))).toEqual({ ok: false, reason: "version" });
    expect(await loadIpo(await withDir('{"version":1,"counts":{}}'))).toEqual({ ok: false, reason: "invalid" });
    const ok: Partial<UiIpo> = { version: 1, counts, signals: [], trades: [], extra_columns: [] };
    expect((await loadIpo(await withDir(JSON.stringify(ok)))).ok).toBe(true);
  });
});

// Integration: the Next.js text for the saved IPO file equals what Streamlit renders.
const PY = process.env.PYTHON_BIN;
describe.skipIf(!PY)("IPO parity with Streamlit", () => {
  test("trade rows and pill values match", async () => {
    const cwd = path.resolve(process.cwd(), process.env.DATA_DIR ?? "..");
    const py = path.resolve(process.cwd(), PY!);
    const env = { ...process.env, PYTHONIOENCODING: "utf-8" };
    execFileSync(py, ["precompute_ui_ipo.py"], { cwd, env, stdio: "ignore" });
    const script = path.resolve(process.cwd(), "tests/parity/ipo_streamlit_text.py");
    const out = execFileSync(py, [script], { cwd, env, encoding: "utf-8", stdio: ["ignore", "pipe", "ignore"], maxBuffer: 64 << 20 });
    const expected = JSON.parse(out.trim().split(/\r?\n/).pop() ?? "{}");

    const res = await loadIpo(cwd);
    expect(res.ok).toBe(true);
    if (!res.ok) return;
    const d = res.data;

    const trades = d.trades.slice(0, 15).map((r) => {
      const c = tradeCells(r);
      return [r.symbol, c.entryDate, c.entryPrice, c.exitDate, c.exitPrice, c.pnl, c.held, c.exitReason, c.result,
        ...d.extra_columns.map((k) => c.extras[k])];
    });
    expect(trades).toHaveLength(15);
    expect(trades).toEqual(expected.trades);

    const rows = summaryStats(d.summary, d.counts);
    expect(rows.map((r) => r.value)).toEqual(expected.pills.values);
    expect(rows.map((r) => r.sub ?? null)).toEqual(expected.pills.subs);
  }, 180_000);
});
