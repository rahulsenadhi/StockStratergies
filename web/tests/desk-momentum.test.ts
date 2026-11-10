import { describe, expect, test } from "vitest";
import { execFileSync } from "node:child_process";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import {
  conditionTitle, countsLine, exchangeOf, exitBadge, OLD_APP_LINK, FUNNEL_LABELS, healthStats, loadMomentum, recentCells, resolveSelected, signalCells,
  tabLabels, tabRows, tradeCells, tradesCaption, visibleTrades,
  type Health, type MomentumSummary, type RecentRow, type SignalRow, type TradeRow, type UiMomentum,
} from "@/lib/desk/momentum";

const sig = (symbol: string, extra: Partial<SignalRow> = {}): SignalRow => ({
  symbol, company: symbol, signal: "Watch Zone", action: "FORMING", close: 100, ath: 110, dist_ath: -9.1,
  entry_type: "52W High", chart_qual: "Clean ✅", choppiness: 30, recovery: "Fast 🟢", ema220: 90, high52: 110,
  vs_high: -9.1, vol_ratio: 1.5, score: 50, hist_win: 30, hist_avg: 2, hist_n: 10, stop_price: 85, stop_pct: -15, ...extra,
});
const rec = (symbol: string): RecentRow => ({
  symbol, days_ago: 2, bk_date: "2026-11-04", bk_price: 100, close: 98.5, off_bk: -1.5, ema220: 80, vol_ratio: 2.345, stop: 85,
});
const trade = (id: number, extra: Partial<TradeRow> = {}): TradeRow => ({
  id, symbol: "AAA", entry_date: "2026-01-01", entry_price: 100, prior_high: 98, bk_margin: 2.04, exit_date: "2026-06-01",
  exit_price: 120, pnl: 20, hold_days: 151, exit_reason: "220 EMA Break", result: "Win", filters: "All 8 pass",
  entry_type: "52W high", recovery: "Fast · 3d", ...extra,
});

const health: Health = {
  n_trades: 144, win_rate: 31.9, avg_pnl: 4.74, median_pnl: -6.1, median_hold: 111, safe_20d_pct: 22,
  universe: "u", verdict_text: "v", top_lift: "t", best_combo: "b", verdict_tone: "loss",
};
const summary: MomentumSummary = { cagr: 8.18, total_ret: 116.79, max_dd: -31.53, start: "2017-01-04", end: "2026-11-06" };

function data(over: Partial<UiMomentum> = {}): UiMomentum {
  const signals = [sig("TITAN"), sig("HAL", { action: "BUY NOW", signal: "Breakout Today" }), sig("ZED")];
  const trades = [trade(0, { exit_date: "2026-10-01" }), trade(1, { exit_date: "2026-05-01" }), trade(2, { exit_date: "2024-02-01" })];
  return {
    version: 1, generated_at: "x", colour: "#fff", summary, chart: null,
    views: {
      all: { health, counts: { breakout: 1, near: 0, watch: 1, ath: 0, clean: 3, fast: 3 }, signal_ids: ["TITAN", "HAL", "ZED"], trade_ids: [0, 1, 2] },
      ath: { health, counts: { breakout: 1, near: 0, watch: 0, ath: 1, clean: 1, fast: 1 }, signal_ids: ["HAL"], trade_ids: [0, 2] },
    },
    signals,
    tabs: { All: ["TITAN", "HAL", "ZED"], "BUY NOW": ["HAL"], WATCH: [], FORMING: ["TITAN", "ZED"] },
    recent: [rec("NEWCO"), rec("TITAN")],
    funnel: null, details: {}, trades,
    trade_filters: {
      periods: { "Last 1Y": [0, 1], "Last 3Y": [0, 1, 2], All: [0, 1, 2], "2026": [0, 1], "2024": [2] },
      years: [2026, 2024], strict: [0, 2],
    },
    exit_rec: null, ...over,
  };
}

describe("resolveSelected", () => {
  const d = data();
  test("signal, recent-only, .NS, unknown, empty", () => {
    expect(resolveSelected(d, "HAL")).toEqual({ symbol: "HAL", tab: "All" });
    expect(resolveSelected(d, "NEWCO")).toEqual({ symbol: "NEWCO", tab: "Recent" });
    expect(resolveSelected(d, "TITAN.NS")).toEqual({ symbol: "TITAN", tab: "All" });
    for (const bad of ["ZZZ", "", null, undefined]) expect(resolveSelected(d, bad)).toEqual({ symbol: "TITAN", tab: "All" });
    expect(resolveSelected({ signals: [], recent: [rec("NEWCO")] }, "ZZZ")).toEqual({ symbol: "NEWCO", tab: "Recent" });
    expect(resolveSelected({ signals: [], recent: [] }, "ZZZ")).toEqual({ symbol: null, tab: "All" });
  });
});

describe("tabs", () => {
  const d = data();
  test("tabRows keeps saved order and hides stocks outside the view", () => {
    expect(tabRows(d, "all", "All").map((r) => r.symbol)).toEqual(["TITAN", "HAL", "ZED"]);
    expect(tabRows(d, "all", "FORMING").map((r) => r.symbol)).toEqual(["TITAN", "ZED"]);
    expect(tabRows(d, "ath", "All").map((r) => r.symbol)).toEqual(["HAL"]);
    expect(tabRows(d, "ath", "FORMING")).toEqual([]);
  });
  test("tabLabels", () => {
    expect(tabLabels(d, "all")).toEqual([
      { id: "All", label: "All 3" }, { id: "BUY NOW", label: "Buy now 1" }, { id: "WATCH", label: "Watch 0" },
      { id: "FORMING", label: "Forming 2" }, { id: "Recent", label: "Broke out last 7 days 2" },
    ]);
    expect(tabLabels(d, "ath")[0].label).toBe("All 1");
  });
});

describe("visibleTrades", () => {
  const d = data();
  const ids = (r: { rows: TradeRow[] }) => r.rows.map((t) => t.id);
  test("intersection of view, period and strict", () => {
    expect(ids(visibleTrades(d, "all", "Last 1Y", null, false))).toEqual([0, 1]);
    expect(visibleTrades(d, "all", "Last 1Y", null, false).hidden).toBe(0);
    const strict = visibleTrades(d, "all", "Last 1Y", null, true);
    expect(ids(strict)).toEqual([0]);
    expect(strict.hidden).toBe(1);
    expect(ids(visibleTrades(d, "ath", "All", null, false))).toEqual([0, 2]);
    expect(ids(visibleTrades(d, "ath", "All", null, true))).toEqual([0, 2]);
    expect(visibleTrades(d, "ath", "Last 1Y", null, true)).toMatchObject({ hidden: 0 });
  });
  test("Pick year", () => {
    expect(ids(visibleTrades(d, "all", "Pick year", 2024, false))).toEqual([2]);
    expect(ids(visibleTrades(d, "all", "Pick year", 1999, false))).toEqual([]);
    expect(ids(visibleTrades(d, "all", "Pick year", null, false))).toEqual([0, 1, 2]);
  });
  test("tradesCaption", () => {
    expect(tradesCaption(2, 3, "2026-05-01", "2026-10-01", false, 0)).toBe(
      "Showing 2 trades of 3 total. Range: May 2026 → Oct 2026. Turn on Clean signals only to hide marginal-breakout entries.");
    expect(tradesCaption(1, 3, "2026-10-01", "2026-10-26", true, 1)).toBe(
      "Showing 1 trades of 3 total. Range: Oct 2026 → Oct 2026. Clean signals only hid 1 marginal trade(s) in this window.");
    expect(tradesCaption(0, 3, null, null, false, 0)).toContain("Range: — → —.");
  });
});

describe("healthStats", () => {
  test("rows, tones and dashes", () => {
    expect(healthStats(health, summary)).toEqual([
      { label: "Total return", value: "+116.8%", tone: "gain" },
      { label: "Worst fall from a peak", value: "-31.5%", tone: "loss" },
      { label: "Trades that made money", value: "32% of 144", tone: "warn" },
      { label: "Average per trade", value: "+4.74%", sub: "median -6.10%", tone: "gain" },
      { label: "Typical hold", value: "111 days", tone: "muted" },
      { label: "Loss-free 20+ days", value: "22%", tone: "warn" },
    ]);
    const none = healthStats({ ...health, win_rate: 55, safe_20d_pct: 40, avg_pnl: -1 }, null);
    expect(none[0]).toMatchObject({ value: "—" });
    expect(none[1]).toMatchObject({ value: "—" });
    expect(none[2]).toMatchObject({ tone: "gain" });
    expect(none[3]).toMatchObject({ tone: "loss" });
    expect(none[5]).toMatchObject({ tone: "gain" });
  });
  test("null health numbers show a dash", () => {
    expect(healthStats({ ...health, win_rate: null, median_pnl: null }, summary)[2].value).toBe("—");
  });
});

describe("conditionTitle", () => {
  test("each prefix", () => {
    expect(conditionTitle("F1 — SMA 150 > EMA 220")).toBe("Long-term trend up");
    expect(conditionTitle("F2 — Close > SMA 50")).toBe("Price above 50-day average");
    expect(conditionTitle("F3 — SMA 50 > SMA 150")).toBe("Averages stacked in order");
    expect(conditionTitle("F4 — Close ≥ 1.25 × 52W Low")).toBe("Well above yearly low");
    expect(conditionTitle("F5 — Dipped below EMA 220 (last 90d)")).toBe("Recent dip below 220-day line");
    expect(conditionTitle("F6 — Choppiness < 61.8")).toBe("Clean chart");
    expect(conditionTitle("🚀 Breakout Trigger — Close > 52W High")).toBe("Breakout with volume");
    expect(conditionTitle("Something else")).toBe("Something else");
  });
  test("funnel labels", () => {
    expect(FUNNEL_LABELS.vol_bk).toBe("Breakout + volume");
    expect(Object.keys(FUNNEL_LABELS)).toHaveLength(9);
  });
});

describe("cells", () => {
  test("signalCells for the TITAN row", () => {
    const c = signalCells(sig("TITAN", { close: 5000, stop_pct: -15, stop_price: 4250, dist_ath: -3.07, vol_ratio: 6.28, score: 68.3 }));
    expect(c).toMatchObject({ close: "₹5,000.00", stopPct: "-15.0%", stop: "₹4,250.00", distAth: "-3.1%", volRatio: "6.28×", score: "68.3" });
  });
  test("signalCells dashes nulls", () => {
    const c = signalCells(sig("X", { close: null, stop_pct: null, dist_ath: null, vol_ratio: null, score: null, hist_win: null, hist_avg: null }));
    expect([c.close, c.stopPct, c.distAth, c.volRatio, c.score, c.histWin, c.histAvg]).toEqual(Array(7).fill("—"));
  });
  test("histWin / histAvg", () => {
    expect(signalCells(sig("X", { hist_win: 32.4, hist_avg: 5.22 }))).toMatchObject({ histWin: "32%", histAvg: "+5.2%" });
  });
  test("recentCells", () => {
    expect(recentCells(rec("N"))).toMatchObject({
      daysAgo: "2", bkDate: "2026-11-04", bkPrice: "₹100.00", close: "₹98.50", offBk: "-1.5%", ema220: "₹80.00", volRatio: "2.35×", stop: "₹85.00",
    });
  });
  test("tradeCells", () => {
    expect(tradeCells(trade(0))).toMatchObject({
      entryPrice: "₹100.00", priorHigh: "₹98.00", bkMargin: "+2.04%", exitPrice: "₹120.00", pnl: "+20.00%", held: "151",
    });
    expect(tradeCells(trade(0, { bk_margin: -0.5, prior_high: null, pnl: -8.256 }))).toMatchObject({
      bkMargin: "-0.50%", priorHigh: "—", pnl: "-8.26%",
    });
    expect(tradeCells(trade(0, { bk_margin: null })).bkMargin).toBe("—");
  });
  test("exitBadge", () => {
    expect(exitBadge(null)).toBe("-");
    const base = { hold_days: 65, hold_median_return: 1, hold_win_rate: 1, stop_pct: -10.1, sample_size: 1, data_quality: "ohlcv" };
    expect(exitBadge({ ...base, targets: [{ pct: 22, book_pct: 40, hit_rate: 1 }, { pct: 69.9, book_pct: 1, hit_rate: 1 }, { pct: 132.8, book_pct: 1, hit_rate: 1 }] }))
      .toBe("Hold ~65d - T1/T2/T3 +22/+70/+133% - Stop -10%");
    expect(exitBadge({ ...base, targets: [] })).toBe("Hold ~65d - targets n/a - Stop -10%");
  });
});

describe("loadMomentum", () => {
  const withDir = async (content: string | null) => {
    const dir = await fs.mkdtemp(path.join(os.tmpdir(), "momentum-"));
    if (content !== null) await fs.writeFile(path.join(dir, "ui_momentum.json"), content);
    return dir;
  };
  test("missing, invalid, version and ok", async () => {
    expect(await loadMomentum(await withDir(null))).toEqual({ ok: false, reason: "missing" });
    expect(await loadMomentum(await withDir("{"))).toEqual({ ok: false, reason: "invalid" });
    expect(await loadMomentum(await withDir('{"version":2}'))).toEqual({ ok: false, reason: "version" });
    expect(await loadMomentum(await withDir('{"version":1,"views":{}}'))).toEqual({ ok: false, reason: "invalid" });
    const res = await loadMomentum(await withDir(JSON.stringify(data())));
    expect(res.ok).toBe(true);
  });
});

// Integration: the Next.js text for the saved Momentum file equals what Streamlit renders.
const PY = process.env.PYTHON_BIN;
describe.skipIf(!PY)("Momentum parity with Streamlit", () => {
  test("setups, trades and health strings match", async () => {
    const cwd = path.resolve(process.cwd(), process.env.DATA_DIR ?? "..");
    const py = path.resolve(process.cwd(), PY!);
    const env = { ...process.env, PYTHONIOENCODING: "utf-8" };
    execFileSync(py, ["precompute_ui_momentum.py"], { cwd, env, stdio: "ignore" });
    const script = path.resolve(process.cwd(), "tests/parity/momentum_streamlit_text.py");
    const out = execFileSync(py, [script], { cwd, env, encoding: "utf-8", stdio: ["ignore", "pipe", "ignore"], maxBuffer: 64 << 20 });
    const expected = JSON.parse(out.trim().split(/\r?\n/).pop() ?? "{}");

    const res = await loadMomentum(cwd);
    expect(res.ok).toBe(true);
    if (!res.ok) return;
    const d = res.data;

    const setups = tabRows(d, "all", "All").map((r) => {
      const c = signalCells(r);
      return [r.symbol, r.signal, r.action, c.close, c.stop, c.stopPct, c.ath, c.distAth, c.entryType, c.chartQual,
        c.choppiness, c.recovery, c.ema220, c.high52, c.vsHigh, c.volRatio, c.score, c.histWin, c.histAvg, exitBadge(d.exit_rec)];
    });
    expect(setups.length).toBeGreaterThan(0);
    expect(setups).toEqual(expected.setups);

    const trades = visibleTrades(d, "all", "All", null, false).rows.slice(0, 15).map((r) => {
      const c = tradeCells(r);
      return [r.symbol, c.entryDate, c.entryPrice, c.priorHigh, c.bkMargin, c.exitDate, c.exitPrice, c.pnl, c.held,
        c.exitReason, c.filters, c.entryType, c.recovery];
    });
    expect(trades).toHaveLength(15);
    expect(trades).toEqual(expected.trades);

    const rows = healthStats(d.views.all.health, d.summary);
    expect(rows.map((r) => r.value)).toEqual(expected.health.values);
    expect(rows[3].sub).toBe(expected.health.medianSub);
    expect(d.views.all.counts).toEqual(expected.counts);
  }, 180_000);
});

describe("exchangeOf / countsLine / old-app link", () => {
  test("exchangeOf labels .BO symbols BSE and everything else NSE", () => {
    expect(exchangeOf("519477.BO")).toBe("BSE");
    expect(exchangeOf("TITAN")).toBe("NSE");
    expect(exchangeOf("TITAN.NS")).toBe("NSE");
  });
  test("countsLine shows the saved ATH, clean and fast counts", () => {
    expect(countsLine({ ath: 4, clean: 21, fast: 9 })).toBe("All-time-high entries 4 · Clean charts 21 · Fast recovery 9");
  });
  test("old-app link text is the approved wording", () => {
    expect(OLD_APP_LINK).toBe("Single-stock backtest: open in the old app");
  });
});
