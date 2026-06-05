import { describe, it, expect } from "vitest";
import { getStrategies, mapStrategy, getEquitySeries } from "@/lib/data/strategies";
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
