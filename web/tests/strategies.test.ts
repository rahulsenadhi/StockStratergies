import { describe, it, expect } from "vitest";
import { getStrategies, mapStrategy, getEquitySeries, getStrategy, getEquityCurve, computeDrawdown, getTrades, rebaseToReturn, getLiveSignals, getEquityWithBenchmark, annualizedReturn, getRankings } from "@/lib/data/strategies";
import path from "path";
import os from "os";
import { promises as fsp } from "fs";

const FIX = path.join(import.meta.dirname, "fixtures");

describe("getStrategies", () => {
  it("maps fields and sorts by rank asc", async () => {
    const s = await getStrategies(FIX);
    expect(s.map((x) => x.id)).toEqual(["b", "a", "c"]); // b rank1, a rank2, c unranked last
    expect(s[1].kpis.cagr).toBe(0.21);
    expect(s[1].kpis.maxDd).toBe(-0.11);
  });
  it("preserves null win_rate (not 0)", async () => {
    const s = await getStrategies(FIX);
    const a = s.find((x) => x.id === "a")!;
    expect(a.kpis.winRate).toBeNull();
  });
  it("includes errored strategy with null kpis + kpisError", async () => {
    const s = await getStrategies(FIX);
    const c = s.find((x) => x.id === "c")!;
    expect(c.kpisError).toBe("missing CSV: x");
    expect(c.kpis.cagr).toBeNull();
    expect(c.kpis.sharpe).toBeNull();
    expect(c.kpis.winRate).toBeNull();
    expect(c.rank).toBeNull();
  });
  it("missing index file -> []", async () => {
    expect(await getStrategies("/no/such/dir")).toEqual([]);
  });
});

describe("mapStrategy", () => {
  it("null kpis_inline -> all kpis null", () => {
    const m = mapStrategy({ id: "z", name: "Z" });
    expect(m.kpis.cagr).toBeNull();
    expect(m.kpis.winRate).toBeNull();
    expect(m.kpis.alpha).toBeNull();
  });
});

describe("getStrategy", () => {
  it("returns the matching strategy", async () => {
    const s = await getStrategy("b", FIX);
    expect(s?.id).toBe("b");
  });
  it("maps tradesCsv", async () => {
    const s = await getStrategy("a", FIX);
    expect(s?.tradesCsv).toBe("tr_a.csv");
  });
  it("unknown id -> null", async () => {
    expect(await getStrategy("nope", FIX)).toBeNull();
  });
});

describe("getEquitySeries", () => {
  it("reads Portfolio_Value column", async () => {
    expect(await getEquitySeries("eq_a.csv", FIX)).toEqual([100, 110, 120]);
  });
  it("reads Equity column", async () => {
    expect(await getEquitySeries("eq_b.csv", FIX)).toEqual([100, 90, 130]);
  });
  it("missing file -> []", async () => {
    expect(await getEquitySeries("nope.csv", FIX)).toEqual([]);
  });
  it("null path -> []", async () => {
    expect(await getEquitySeries(null, FIX)).toEqual([]);
  });
  it("downsamples to <= 80 points", async () => {
    const dir = await fsp.mkdtemp(path.join(os.tmpdir(), "eq-"));
    const rows = ["Date,equity", ...Array.from({ length: 200 }, (_, i) => `2024-01-${i},${100 + i}`)];
    await fsp.writeFile(path.join(dir, "big.csv"), rows.join("\n"));
    const series = await getEquitySeries("big.csv", dir);
    expect(series.length).toBeLessThanOrEqual(80);
    expect(series.length).toBeGreaterThan(1);
  });
});

describe("getEquityCurve", () => {
  it("returns dated points sorted, Portfolio_Value column", async () => {
    const c = await getEquityCurve("eq_a.csv", FIX);
    expect(c).toEqual([
      { time: "2024-01-01", value: 100 },
      { time: "2024-01-02", value: 110 },
      { time: "2024-01-03", value: 120 },
    ]);
  });
  it("Equity column variant", async () => {
    const c = await getEquityCurve("eq_b.csv", FIX);
    expect(c.map((p) => p.value)).toEqual([100, 90, 130]);
  });
  it("missing/null -> []", async () => {
    expect(await getEquityCurve("nope.csv", FIX)).toEqual([]);
    expect(await getEquityCurve(null, FIX)).toEqual([]);
  });
  it("getEquityCurve caps at <=2000 and keeps last point", async () => {
    const dir = await fsp.mkdtemp(path.join(os.tmpdir(), "eqc-"));
    const rows = ["Date,equity"];
    for (let i = 0; i < 5000; i++) {
      const d = new Date(Date.UTC(2010, 0, 1));
      d.setUTCDate(d.getUTCDate() + i);
      rows.push(`${d.toISOString().slice(0, 10)},${100 + i}`);
    }
    await fsp.writeFile(path.join(dir, "big.csv"), rows.join("\n"));
    const c = await getEquityCurve("big.csv", dir);
    expect(c.length).toBeLessThanOrEqual(2000);
    expect(c[c.length - 1].value).toBe(100 + 4999);   // final point preserved
  });
  it("getEquityCurve dedups duplicate dates keeping last", async () => {
    const dir = await fsp.mkdtemp(path.join(os.tmpdir(), "eqd-"));
    await fsp.writeFile(path.join(dir, "dup.csv"),
      "Date,equity\n2024-01-01,100\n2024-01-01,150\n2024-01-02,200\n");
    const c = await getEquityCurve("dup.csv", dir);
    expect(c).toEqual([
      { time: "2024-01-01", value: 150 },
      { time: "2024-01-02", value: 200 },
    ]);
  });
});

describe("computeDrawdown", () => {
  it("running-peak drawdown <= 0", () => {
    const dd = computeDrawdown([
      { time: "1", value: 100 }, { time: "2", value: 120 },
      { time: "3", value: 60 }, { time: "4", value: 90 },
    ]);
    expect(dd.map((p) => p.value)).toEqual([0, 0, -0.5, -0.25]);
  });
  it("[] -> []", () => {
    expect(computeDrawdown([])).toEqual([]);
  });
});

describe("getTrades", () => {
  it("generic columns + rows", async () => {
    const t = await getTrades("tr_a.csv", FIX);
    expect(t.columns).toEqual(["Ticker", "Entry_Date", "Exit_Date", "PnL_Pct", "Result"]);
    expect(t.rows[0].Ticker).toBe("AAA.NS");
    expect(t.rows[1].Result).toBe("LOSS");
  });
  it("works on rebalance-log shape (no PnL)", async () => {
    const t = await getTrades("tr_rebal.csv", FIX);
    expect(t.columns).toContain("Top5_Stocks");
    expect(t.rows.length).toBe(2);
  });
  it("missing/null -> empty", async () => {
    expect(await getTrades("nope.csv", FIX)).toEqual({ columns: [], rows: [] });
    expect(await getTrades(null, FIX)).toEqual({ columns: [], rows: [] });
  });
});

describe("rebaseToReturn", () => {
  it("normalizes to 0% at start", () => {
    const r = rebaseToReturn([
      { time: "1", value: 100 }, { time: "2", value: 110 }, { time: "3", value: 90 },
    ]);
    expect(r).toHaveLength(3);
    expect(r[0]).toEqual({ time: "1", value: 0 });
    expect(r[1].time).toBe("2");
    expect(r[1].value).toBeCloseTo(0.1);
    expect(r[2].time).toBe("3");
    expect(r[2].value).toBeCloseTo(-0.1);
  });
  it("[] -> []", () => expect(rebaseToReturn([])).toEqual([]));
  it("v0<=0 -> []", () => {
    expect(rebaseToReturn([{ time: "1", value: 0 }, { time: "2", value: 5 }])).toEqual([]);
  });
});

describe("lastRun mapping", () => {
  it("maps raw.last_run", async () => {
    // fixture strategy "a" needs a last_run value (added in Step 3)
    const s = await getStrategy("a", FIX);
    expect(s?.lastRun).toBe("2026-06-01T12:00:00");
  });
});

describe("getLiveSignals", () => {
  it("reads live_rankings shape -> ticker/company/signal", async () => {
    const r = await getLiveSignals("live_rank.csv", FIX);
    expect(r[0]).toEqual({ ticker: "ZEEL.NS", company: "Zee Entertainment", signal: "Strong BUY" });
    expect(r.length).toBe(2);
  });
  it("reads momentum shape", async () => {
    const r = await getLiveSignals("live_mom.csv", FIX);
    expect(r[1]).toEqual({ ticker: "TATASTEEL", company: "Tata Steel", signal: "Breakout" });
  });
  it("limit caps rows", async () => {
    expect((await getLiveSignals("live_rank.csv", FIX, 1)).length).toBe(1);
  });
  it("missing/null -> []", async () => {
    expect(await getLiveSignals("nope.csv", FIX)).toEqual([]);
    expect(await getLiveSignals(null, FIX)).toEqual([]);
  });
  it("liveSignalsCsv mapped on Strategy", async () => {
    const s = await getStrategy("a", FIX);
    expect(s?.liveSignalsCsv).toBe("live_rank.csv");
  });
});

describe("getEquityWithBenchmark", () => {
  it("returns rebased strategy + benchmark series and benchmark CAGR", async () => {
    const r = await getEquityWithBenchmark("bench_a.csv", FIX);
    expect(r.strategy.length).toBe(3);
    expect(r.benchmark.length).toBe(3);
    expect(r.strategy[0].value).toBeCloseTo(0, 6);
    expect(r.benchmark[0].value).toBeCloseTo(0, 6);
    expect(r.strategy[2].value).toBeCloseTo(0.2, 6);
    const expected = Math.pow(235 / 210, 1 / 2) - 1;
    expect(r.benchmarkCagr).toBeCloseTo(expected, 4);
  });
  it("missing Benchmark_Value column -> empty benchmark, null cagr", async () => {
    const r = await getEquityWithBenchmark("eq_b.csv", FIX);
    expect(r.strategy.length).toBeGreaterThan(0);
    expect(r.benchmark).toEqual([]);
    expect(r.benchmarkCagr).toBeNull();
  });
  it("missing file -> empty everything", async () => {
    const r = await getEquityWithBenchmark("nope.csv", FIX);
    expect(r).toEqual({ strategy: [], benchmark: [], benchmarkCagr: null });
  });
  it("null path -> empty everything", async () => {
    const r = await getEquityWithBenchmark(null, FIX);
    expect(r).toEqual({ strategy: [], benchmark: [], benchmarkCagr: null });
  });
});

describe("annualizedReturn", () => {
  it("computes CAGR from first/last point", () => {
    const r = annualizedReturn([
      { time: "2024-01-01", value: 100 },
      { time: "2026-01-01", value: 121 },
    ]);
    // Implementation uses days/365.25; 2024-01-01->2026-01-01 = 731 days (2024 is a leap year)
    const days = (new Date("2026-01-01").getTime() - new Date("2024-01-01").getTime()) / 86_400_000;
    const years = days / 365.25;
    const expected = Math.pow(1.21, 1 / years) - 1;
    expect(r).toBeCloseTo(expected, 4);
  });
  it("< 2 points -> null", () => {
    expect(annualizedReturn([])).toBeNull();
    expect(annualizedReturn([{ time: "2024-01-01", value: 100 }])).toBeNull();
  });
  it("non-positive first value -> null", () => {
    expect(annualizedReturn([
      { time: "2024-01-01", value: 0 },
      { time: "2025-01-01", value: 100 },
    ])).toBeNull();
  });
});
