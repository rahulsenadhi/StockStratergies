import { describe, it, expect } from "vitest";
import { computeConfidence } from "@/lib/confidence";
import type { Kpis } from "@/lib/data/strategies";

const base: Kpis = {
  cagr: 0.21,
  totalReturn: 1.5,
  volatility: 0.18,
  sharpe: 1.2,
  maxDd: -0.11,
  calmar: null,
  winRate: 0.6,
  numTrades: 120,
  alpha: 0.08,
  finalEquity: null,
};

describe("computeConfidence", () => {
  it("scores all five criteria passing as HIGH (100)", () => {
    const r = computeConfidence(base);
    expect(r.score).toBe(100);
    expect(r.level).toBe("HIGH");
    expect(r.criteria).toHaveLength(5);
    expect(r.criteria.every((c) => c.pass === true)).toBe(true);
  });

  it("levels: 80->HIGH, 60->MODERATE, 40->CAUTION, <40->LOW", () => {
    // fail one (drawdown) -> 80
    expect(computeConfidence({ ...base, maxDd: -0.4 }).score).toBe(80);
    expect(computeConfidence({ ...base, maxDd: -0.4 }).level).toBe("HIGH");
    // fail two -> 60 MODERATE
    expect(computeConfidence({ ...base, maxDd: -0.4, sharpe: 0.1 }).level).toBe("MODERATE");
    // fail three -> 40 CAUTION
    expect(
      computeConfidence({ ...base, maxDd: -0.4, sharpe: 0.1, winRate: 0.3 }).level,
    ).toBe("CAUTION");
    // fail four -> 20 LOW
    expect(
      computeConfidence({ ...base, maxDd: -0.4, sharpe: 0.1, winRate: 0.3, alpha: -0.05 })
        .level,
    ).toBe("LOW");
  });

  it("treats null alpha as no-benchmark (pass=null, no points)", () => {
    const r = computeConfidence({ ...base, alpha: null });
    const c = r.criteria.find((x) => x.label.startsWith("Beat"));
    expect(c!.pass).toBeNull();
    expect(c!.value).toBe("No benchmark data");
    expect(r.score).toBe(80); // 4 of 5 contribute
  });

  it("falls back to % positive years when win rate is null", () => {
    const annual = [0.1, 0.2, -0.05, 0.3]; // 3/4 = 75% positive -> passes >50%
    const r = computeConfidence({ ...base, winRate: null }, annual);
    const c = r.criteria.find((x) => x.label === "% Positive Years");
    expect(c).toBeDefined();
    expect(c!.pass).toBe(true);
    expect(c!.value).toBe("75%");
    expect(r.score).toBe(100);
  });

  it("% positive years fails when half or fewer years are positive", () => {
    const r = computeConfidence({ ...base, winRate: null }, [0.1, -0.2]);
    const c = r.criteria.find((x) => x.label === "% Positive Years");
    expect(c!.pass).toBe(false);
    expect(r.score).toBe(80);
  });

  it("returns NO DATA when all core KPIs are null", () => {
    const r = computeConfidence({
      ...base,
      cagr: null,
      totalReturn: null,
      sharpe: null,
      maxDd: null,
    });
    expect(r.level).toBe("NO DATA");
    expect(r.criteria).toHaveLength(0);
  });
});
