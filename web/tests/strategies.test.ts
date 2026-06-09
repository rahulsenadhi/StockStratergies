import { describe, it, expect } from "vitest";
import { getStrategies, mapStrategy, getEquitySeries, getStrategy, getEquityCurve, readEquityCurveRaw, computeDrawdown, getTrades, rebaseToReturn, getLiveSignals, getEquityWithBenchmark, annualizedReturn, getRankings, parseCsvLines, getFunnel, getRecentBreakouts, getDecileSpread, getMonthlyReturns } from "@/lib/data/strategies";
import { barWidthPct } from "@/components/horizontal-bars";
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

describe("getRankings", () => {
  it("parses rows, strips .NS and emoji, keeps nulls not zero", async () => {
    const r = await getRankings("ranks_a.csv", FIX);
    expect(r.length).toBe(2); // third row skipped (no ticker)
    expect(r[0]).toEqual({
      rank: 1,
      ticker: "ZEEL",
      company: "Zee Entertainment",
      price: 104.42,
      returnPct: 12.14,
      rsScore: 12.96,
      signal: "Strong BUY",
    });
    expect(r[1].ticker).toBe("COALINDIA");
    expect(r[1].signal).toBe("Strong BUY");
  });
  it("company falls back to ticker when column absent", async () => {
    const r = await getRankings("ranks_noco.csv", FIX);
    expect(r[0].company).toBe(r[0].ticker);
  });
  it("missing numeric cells -> null (not 0)", async () => {
    const r = await getRankings("ranks_partial.csv", FIX);
    expect(r[0].rsScore).toBeNull();
    expect(r[0].price).toBeNull();
  });
  it("missing file -> []", async () => {
    expect(await getRankings("nope.csv", FIX)).toEqual([]);
  });
  it("null path -> []", async () => {
    expect(await getRankings(null, FIX)).toEqual([]);
  });
});

describe("parseCsvLines", () => {
  it("splits header + rows, trims header", async () => {
    const r = await parseCsvLines("ranks_a.csv", FIX);
    expect(r.header[0]).toBe("Rank");
    expect(r.rows.length).toBeGreaterThan(0);
    expect(Array.isArray(r.rows[0])).toBe(true);
  });
  it("lowercaseHeader flag lowercases the header", async () => {
    const r = await parseCsvLines("ranks_a.csv", FIX, true);
    expect(r.header).toContain("ticker");
  });
  it("missing file -> empty", async () => {
    expect(await parseCsvLines("nope.csv", FIX)).toEqual({ header: [], rows: [] });
  });
  it("null path -> empty", async () => {
    expect(await parseCsvLines(null, FIX)).toEqual({ header: [], rows: [] });
  });
  it("header-only file -> empty", async () => {
    const dir = await fsp.mkdtemp(path.join(os.tmpdir(), "pcl-"));
    await fsp.writeFile(path.join(dir, "h.csv"), "a,b,c");
    expect(await parseCsvLines("h.csv", dir)).toEqual({ header: [], rows: [] });
  });
  it("handles CRLF line endings", async () => {
    const dir = await fsp.mkdtemp(path.join(os.tmpdir(), "crlf-"));
    await fsp.writeFile(path.join(dir, "c.csv"), "a,b\r\nv1,v2\r\nv3,v4\r\n");
    const r = await parseCsvLines("c.csv", dir);
    expect(r.header).toEqual(["a", "b"]);
    expect(r.rows).toEqual([["v1", "v2"], ["v3", "v4"]]);
  });
});

describe("getFunnel", () => {
  it("maps fixed keys to ordered labelled stages (ignores extra 'final' key)", async () => {
    const f = await getFunnel("funnel.json", FIX);
    expect(f).toEqual([
      { label: "Universe", value: 100 },
      { label: "Has Data", value: 100 },
      { label: "F1 Trend", value: 50 },
      { label: "F2 Price > SMA50", value: 40 },
      { label: "F3 MA Align", value: 30 },
      { label: "F4 vs 52W Low", value: 20 },
      { label: "F5 Dip Recovered", value: 15 },
      { label: "F6 Clean Chart", value: 12 },
      { label: "Vol + Breakout", value: 8 },
    ]);
  });
  it("missing key -> 0", async () => {
    const dir = await fsp.mkdtemp(path.join(os.tmpdir(), "fun-"));
    await fsp.writeFile(path.join(dir, "p.json"), JSON.stringify({ total: 5 }));
    const f = await getFunnel("p.json", dir);
    expect(f[0].value).toBe(5);
    expect(f[1].value).toBe(0);
    expect(f[8].value).toBe(0);
  });
  it("missing/null/bad file -> []", async () => {
    expect(await getFunnel("nope.json", FIX)).toEqual([]);
    expect(await getFunnel(null, FIX)).toEqual([]);
    const dir = await fsp.mkdtemp(path.join(os.tmpdir(), "fun2-"));
    await fsp.writeFile(path.join(dir, "bad.json"), "{not json");
    expect(await getFunnel("bad.json", dir)).toEqual([]);
  });
  it("non-object JSON root (array) -> []", async () => {
    const dir = await fsp.mkdtemp(path.join(os.tmpdir(), "fun3-"));
    await fsp.writeFile(path.join(dir, "arr.json"), "[1,2,3]");
    expect(await getFunnel("arr.json", dir)).toEqual([]);
  });
});

describe("getRecentBreakouts", () => {
  it("returns all 9 columns + rows (no 8-col cap)", async () => {
    const r = await getRecentBreakouts("breakouts.csv", FIX);
    expect(r.columns.length).toBe(9);
    expect(r.columns[8]).toBe("Stop (₹)");
    expect(r.rows.length).toBe(3);
    expect(r.rows[0]["Ticker"]).toBe("APOLLOHOSP");
    expect(r.rows[0]["Stop (₹)"]).toBe("7230.1");
  });
  it("limit caps rows", async () => {
    const r = await getRecentBreakouts("breakouts.csv", FIX, 2);
    expect(r.rows.length).toBe(2);
  });
  it("missing/null -> empty", async () => {
    expect(await getRecentBreakouts("nope.csv", FIX)).toEqual({ columns: [], rows: [] });
    expect(await getRecentBreakouts(null, FIX)).toEqual({ columns: [], rows: [] });
  });
});

describe("getDecileSpread", () => {
  it("parses, drops bad/empty rows, sorts by decile asc", async () => {
    const r = await getDecileSpread("decile.csv", FIX);
    expect(r.map((p) => p.decile)).toEqual([1, 2, 10]); // 'bad' and empty fwd dropped
    expect(r[0]).toEqual({ decile: 1, fwdReturn: 4.12 });
    expect(r[2]).toEqual({ decile: 10, fwdReturn: 2.83 });
  });
  it("missing required column -> []", async () => {
    const dir = await fsp.mkdtemp(path.join(os.tmpdir(), "dec-"));
    await fsp.writeFile(path.join(dir, "x.csv"), "foo,bar\n1,2");
    expect(await getDecileSpread("x.csv", dir)).toEqual([]);
  });
  it("missing/null -> []", async () => {
    expect(await getDecileSpread("nope.csv", FIX)).toEqual([]);
    expect(await getDecileSpread(null, FIX)).toEqual([]);
  });
});

describe("parity field mapping", () => {
  it("maps funnelJson / recentBreakoutsCsv / decileSpreadCsv", async () => {
    const s = await getStrategy("a", FIX);
    expect(s?.funnelJson).toBe("funnel.json");
    expect(s?.recentBreakoutsCsv).toBe("breakouts.csv");
    expect(s?.decileSpreadCsv).toBe("decile.csv");
  });
  it("defaults missing parity keys to null", () => {
    const m = mapStrategy({ id: "z", name: "Z" });
    expect(m.funnelJson).toBeNull();
    expect(m.recentBreakoutsCsv).toBeNull();
    expect(m.decileSpreadCsv).toBeNull();
  });
});

describe("barWidthPct", () => {
  it("scales value against max", () => {
    expect(barWidthPct(50, 100)).toBe(50);
    expect(barWidthPct(100, 100)).toBe(100);
  });
  it("maxValue <= 0 -> 0 (no div-by-zero)", () => {
    expect(barWidthPct(5, 0)).toBe(0);
    expect(barWidthPct(5, -3)).toBe(0);
  });
  it("clamps to [0, 100]", () => {
    expect(barWidthPct(-2, 100)).toBe(0);
    expect(barWidthPct(150, 100)).toBe(100);
  });
});

describe("readEquityCurveRaw", () => {
  it("returns full-resolution sorted/deduped curve (no downsample)", async () => {
    const dir = await fsp.mkdtemp(path.join(os.tmpdir(), "raw-"));
    const rows = ["Date,equity"];
    for (let i = 0; i < 5000; i++) {
      const d = new Date(Date.UTC(2010, 0, 1));
      d.setUTCDate(d.getUTCDate() + i);
      rows.push(`${d.toISOString().slice(0, 10)},${100 + i}`);
    }
    await fsp.writeFile(path.join(dir, "big.csv"), rows.join("\n"));
    const c = await readEquityCurveRaw("big.csv", dir);
    expect(c.length).toBe(5000); // NOT capped
    expect(c[0].value).toBe(100);
    expect(c[c.length - 1].value).toBe(100 + 4999);
  });
  it("missing/null -> []", async () => {
    expect(await readEquityCurveRaw("nope.csv", FIX)).toEqual([]);
    expect(await readEquityCurveRaw(null, FIX)).toEqual([]);
  });
});

describe("getMonthlyReturns", () => {
  async function write(rows: string[]): Promise<[string, string]> {
    const dir = await fsp.mkdtemp(path.join(os.tmpdir(), "mr-"));
    await fsp.writeFile(path.join(dir, "eq.csv"), ["Date,equity", ...rows].join("\n"));
    return ["eq.csv", dir];
  }

  it("month-end value wins; first month anchors on opening value", async () => {
    const [csv, dir] = await write([
      "2024-01-05,100",
      "2024-01-20,105",
      "2024-01-31,110",
      "2024-02-28,121",
    ]);
    const r = await getMonthlyReturns(csv, dir);
    expect(r.length).toBe(1);
    expect(r[0].year).toBe(2024);
    expect(r[0].months[0]).toBeCloseTo(0.10, 6); // Jan: 110/100 - 1
    expect(r[0].months[1]).toBeCloseTo(0.10, 6); // Feb: 121/110 - 1
    expect(r[0].months[2]).toBeNull();           // Mar absent
    expect(r[0].annual).toBeCloseTo(0.21, 6);    // (1.1*1.1)-1
  });

  it("gap month is null; next present month compounds from last month-end", async () => {
    const [csv, dir] = await write([
      "2024-01-15,100",
      "2024-01-31,110",
      "2024-03-31,132",
    ]);
    const r = await getMonthlyReturns(csv, dir);
    expect(r[0].months[0]).toBeCloseTo(0.10, 6); // Jan vs opening 100
    expect(r[0].months[1]).toBeNull();           // Feb gap
    expect(r[0].months[2]).toBeCloseTo(0.20, 6); // Mar vs Jan-end 110
  });

  it("annual compounds only displayed months across multiple years", async () => {
    const [csv, dir] = await write([
      "2023-12-29,100",
      "2024-06-28,110",
      "2024-12-31,121",
    ]);
    const r = await getMonthlyReturns(csv, dir);
    expect(r.map((x) => x.year)).toEqual([2023, 2024]);
    expect(r[0].months[11]).toBeCloseTo(0, 6);
    expect(r[0].annual).toBeCloseTo(0, 6);
    expect(r[1].months[5]).toBeCloseTo(0.10, 6);
    expect(r[1].months[11]).toBeCloseTo(0.10, 6);
    expect(r[1].annual).toBeCloseTo(0.21, 6);
  });

  it("empty/missing csv -> []", async () => {
    expect(await getMonthlyReturns("nope.csv", FIX)).toEqual([]);
    expect(await getMonthlyReturns(null, FIX)).toEqual([]);
  });

  it("single data point (<2) -> []", async () => {
    const [csv, dir] = await write(["2024-01-31,100"]);
    expect(await getMonthlyReturns(csv, dir)).toEqual([]);
  });

  it("non-positive prior anchor -> null return guard", async () => {
    const [csv, dir] = await write([
      "2024-01-31,0",
      "2024-02-28,50",
    ]);
    const r = await getMonthlyReturns(csv, dir);
    expect(r[0].months[0]).toBeNull();
    expect(r[0].months[1]).toBeNull();
    expect(r[0].annual).toBeNull();
  });
});
