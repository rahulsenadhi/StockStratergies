import { describe, expect, test } from "vitest";
import { execFileSync } from "node:child_process";
import path from "node:path";
import {
  CANDIDATE_NOTE, PEAD_NOTE, candidateNote, filterCandidates, headerSub, headerTrend, marketRows, priceAge, strategySub,
} from "@/lib/desk/home";
import { formatChange } from "@/lib/desk/format";
import { loadSnapshot, type Candidate } from "@/lib/desk/snapshot";

const cand = (short: string, ticker: string): Candidate => ({
  strategy: short, short, ticker, company: ticker, status: "Watch Zone", status_tone: "warn",
  key_measure: "", change: null, data: "",
});

describe("home mappers", () => {
  const all = [cand("Monthly", "A"), cand("Monthly", "B"), cand("IPO", "C"),
    cand("Momentum", "D"), cand("Momentum", "E"), cand("Momentum", "F")];

  test("filterCandidates", () => {
    expect(filterCandidates(all, "All")).toHaveLength(6);
    expect(filterCandidates(all, "Monthly")).toHaveLength(2);
    expect(filterCandidates(all, "IPO")).toHaveLength(1);
    expect(filterCandidates(all, "Momentum")).toHaveLength(3);
  });

  test("candidate note adds the PEAD sentence only without PEAD signals", () => {
    expect(candidateNote(true)).toBe(CANDIDATE_NOTE);
    expect(candidateNote(false)).toBe(`${CANDIDATE_NOTE} ${PEAD_NOTE}`);
    expect(CANDIDATE_NOTE).toBe("Move: month return for Monthly, distance from the all-time high for Momentum. " +
      "Labels come from each strategy’s own rules; they are model output, not advice.");
  });

  test("strategySub copies _render_home_strategies", () => {
    expect(strategySub({ status: "Paper", num_trades: 4, unit: "trades", small_sample: true, max_dd_pct: -3.1 }))
      .toBe("Paper · 4 trades · small sample · worst fall -3.1%");
    expect(strategySub({ status: "Live", num_trades: 1260, unit: "trades", small_sample: false, max_dd_pct: -30.46 }))
      .toBe("Live · 1,260 trades · worst fall -30.5%");
  });

  test("header trend, sub and price age", () => {
    expect(headerTrend("Bear")).toEqual({ label: "Trend filter off", tone: "warn" });
    expect(headerTrend("Bull")).toEqual({ label: "Trend filter on", tone: "gain" });
    expect(headerTrend(undefined)).toEqual({ label: "Trend unknown", tone: "muted" });
    expect(headerSub(14)).toBe("14 candidates in saved files · research only, nothing here places orders");
    expect(priceAge(1.5)).toBe("updated today");
    expect(priceAge(50)).toBe("2 days old");
    expect(priceAge(null)).toBe("age unknown");
  });

  test("marketRows follows _render_home_market", () => {
    const rows = marketRows({ status: "Bear", bars_since_flip: 169, close: 25030.35, sma50: 23264.12,
      sma200: 24009.89, pct_from_high: -4.93, date: "2026-11-06" });
    expect(rows.map((r) => r.title)).toEqual(
      ["Trend filter", "Nifty close", "50-day average", "200-day average", "From 52-week high", "In this state"]);
    expect(rows[0]).toMatchObject({ sub: "all Nifty trend conditions must pass", pill: { label: "Off", tone: "warn" } });
    expect(rows[1]).toMatchObject({ sub: "2026-11-06", text: "25,030.35" });
    expect(rows[4]).toMatchObject({ change: -4.93 });
    expect(rows[5]).toMatchObject({ text: "169 sessions" });
    expect(marketRows({ status: "Unknown" }).map((r) => r.title)).toEqual(["Trend filter"]);
  });
});

// Integration: the Next.js text for each candidate equals what Streamlit's Home renders.
const PY = process.env.PYTHON_BIN;
describe.skipIf(!PY)("Home candidates parity with Streamlit", () => {
  test("ticker, status, key measure and move text match row by row", async () => {
    const cwd = path.resolve(process.cwd(), process.env.DATA_DIR ?? "..");
    const py = path.resolve(process.cwd(), PY!);
    const env = { ...process.env, PYTHONIOENCODING: "utf-8" };
    execFileSync(py, ["precompute_ui_home.py"], { cwd, env, stdio: "ignore" });
    const code =
      "import json,re,logging; logging.disable(logging.WARNING); import master_dashboard as md; " +
      "import pandas as pd; from core import ui_components as ui; " +
      "c = md._home_candidates(md.load_monthly(), md.load_ipo(), md.load_momentum()); " +
      "strip = lambda h: re.sub(r'<[^>]+>', '', h); " +
      "print(json.dumps([[r.Ticker, r.Status, r['Key measure'], " +
      "strip(ui.change_pill(None if r.Change is None or pd.isna(r.Change) else float(r.Change)))] " +
      "for _, r in c.iterrows()], ensure_ascii=False))";
    const out = execFileSync(py, ["-c", code], { cwd, env, encoding: "utf-8", stdio: ["ignore", "pipe", "ignore"] });
    const expected = JSON.parse(out.trim().split(/\r?\n/).pop() ?? "[]");
    const snap = await loadSnapshot(cwd);
    expect(snap.ok).toBe(true);
    if (!snap.ok) return;
    const actual = snap.snapshot.home.candidates.map((c) => [c.ticker, c.status, c.key_measure, formatChange(c.change).text]);
    expect(actual).toEqual(expected);
  }, 180_000);
});
