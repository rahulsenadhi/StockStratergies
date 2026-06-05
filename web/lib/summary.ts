import type { Strategy } from "@/lib/data/strategies";

export type Summary = {
  total: number; live: number; paper: number;
  avgCagr: number; bestCagr: number; avgWinRate: number; totalTrades: number;
};

const avg = (xs: number[]): number => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : 0);
const present = (xs: (number | null)[]): number[] => xs.filter((v): v is number => v != null);

export function summarizeStrategies(strategies: Strategy[]): Summary {
  const cagrs = present(strategies.map((s) => s.kpis.cagr));
  const wins = present(strategies.map((s) => s.kpis.winRate));
  const trades = present(strategies.map((s) => s.kpis.numTrades));
  return {
    total: strategies.length,
    live: strategies.filter((s) => s.status === "Live").length,
    paper: strategies.filter((s) => s.status === "Paper").length,
    avgCagr: avg(cagrs),
    bestCagr: cagrs.length ? Math.max(...cagrs) : 0,
    avgWinRate: avg(wins),
    totalTrades: trades.reduce((a, b) => a + b, 0),
  };
}
