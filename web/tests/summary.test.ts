import { describe, it, expect } from "vitest";
import { summarizeStrategies } from "@/lib/summary";
import type { Strategy } from "@/lib/data/strategies";

function mk(over: Partial<Strategy> & { id: string }): Strategy {
  return {
    id: over.id, name: over.id, type: "Quant", status: over.status ?? "Live",
    kpis: {
      cagr: 0.2, totalReturn: 0, volatility: 0, sharpe: 1, maxDd: -0.1,
      calmar: null, winRate: 0.5, numTrades: 10, alpha: null, finalEquity: 0,
      ...(over.kpis ?? {}),
    },
    rank: null, rankScore: null, equityCsv: null, tradesCsv: null, lastRun: null,
    ...over,
  } as Strategy;
}

describe("summarizeStrategies", () => {
  it("counts, averages, ignores nulls", () => {
    const s = summarizeStrategies([
      mk({ id: "a", status: "Live", kpis: { cagr: 0.20, winRate: 0.6, numTrades: 10 } as Strategy["kpis"] }),
      mk({ id: "b", status: "Paper", kpis: { cagr: 0.10, winRate: null, numTrades: 5 } as Strategy["kpis"] }),
    ]);
    expect(s.total).toBe(2);
    expect(s.live).toBe(1);
    expect(s.paper).toBe(1);
    expect(s.avgCagr).toBeCloseTo(0.15);
    expect(s.bestCagr).toBeCloseTo(0.20);
    expect(s.avgWinRate).toBeCloseTo(0.6);   // null win-rate excluded, not counted as 0
    expect(s.totalTrades).toBe(15);
  });
  it("empty -> zeros", () => {
    expect(summarizeStrategies([])).toEqual({
      total: 0, live: 0, paper: 0, avgCagr: 0, bestCagr: 0, avgWinRate: 0, totalTrades: 0,
    });
  });
});
