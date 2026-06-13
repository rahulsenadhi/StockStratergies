import { describe, it, expect } from "vitest";
import { annualReturns, buildHistoryProof } from "@/lib/history-proof";

describe("annualReturns", () => {
  it("computes last/first - 1 per calendar year", () => {
    const curve = [
      { time: "2022-01-03", value: 100 },
      { time: "2022-12-30", value: 120 }, // +20%
      { time: "2023-01-02", value: 120 },
      { time: "2023-12-29", value: 108 }, // -10%
    ];
    const a = annualReturns(curve);
    expect(a.get(2022)).toBeCloseTo(0.2);
    expect(a.get(2023)).toBeCloseTo(-0.1);
  });

  it("skips years with fewer than 2 points", () => {
    const a = annualReturns([{ time: "2024-06-01", value: 100 }]);
    expect(a.has(2024)).toBe(false);
  });
});

describe("buildHistoryProof", () => {
  const strat = new Map([
    [2022, 0.2],
    [2023, -0.1],
    [2024, 0.3],
  ]);
  const bench = new Map([
    [2022, 0.1], // strat beats
    [2023, -0.05], // strat loses (-0.1 < -0.05)
    // 2024 missing -> no comparison
  ]);

  it("builds rows with per-year beat flags", () => {
    const h = buildHistoryProof(strat, bench, 0.45);
    expect(h.rows).toHaveLength(3);
    expect(h.rows[0]).toEqual({ year: 2022, strategyRet: 0.2, benchmarkRet: 0.1, beat: true });
    expect(h.rows[1].beat).toBe(false);
    expect(h.rows[2].beat).toBeNull(); // no benchmark for 2024
  });

  it("counts beats only over comparable years", () => {
    const h = buildHistoryProof(strat, bench, 0.45);
    expect(h.beatCount).toBe(1);
    expect(h.beatTotal).toBe(2);
  });

  it("computes growth of ₹1L, avg yearly, worst year, range", () => {
    const h = buildHistoryProof(strat, bench, 0.45);
    expect(h.growth1L).toBeCloseTo(145_000);
    expect(h.avgYearly).toBeCloseTo((0.2 - 0.1 + 0.3) / 3);
    expect(h.worstYear).toBeCloseTo(-0.1);
    expect(h.nYears).toBe(3);
    expect(h.yearRange).toBe("2022–2024");
  });

  it("handles no-benchmark and null total return", () => {
    const h = buildHistoryProof(strat, new Map(), null);
    expect(h.growth1L).toBeNull();
    expect(h.beatTotal).toBe(0);
    expect(h.rows.every((r) => r.beat === null)).toBe(true);
  });

  it("empty strategy -> empty proof", () => {
    const h = buildHistoryProof(new Map(), new Map(), 0.1);
    expect(h.nYears).toBe(0);
    expect(h.yearRange).toBe("—");
    expect(h.avgYearly).toBeNull();
    expect(h.worstYear).toBeNull();
  });
});
