/** History & Proof helpers. Faithful port of master_dashboard.py's
 *  _annual_returns + render_history summary math (~L4774, ~L5147-5247):
 *  year-by-year returns, growth of ₹1 lakh, "beat Nifty" count, avg yearly.
 *
 *  All returns are fractions (0.21 = +21%). */

export interface EquityPoint {
  time: string; // YYYY-MM-DD
  value: number;
}

/** Year-by-year return: last/first - 1 within each calendar year (needs >=2 pts). */
export function annualReturns(curve: EquityPoint[]): Map<number, number> {
  const byYear = new Map<number, EquityPoint[]>();
  for (const p of curve) {
    const year = Number(p.time.slice(0, 4));
    if (!Number.isFinite(year) || year === 0) continue;
    const arr = byYear.get(year);
    if (arr) arr.push(p);
    else byYear.set(year, [p]);
  }
  const out = new Map<number, number>();
  for (const [year, pts] of byYear) {
    if (pts.length >= 2 && pts[0].value !== 0) {
      out.set(year, pts[pts.length - 1].value / pts[0].value - 1);
    }
  }
  return out;
}

export interface HistoryRow {
  year: number;
  strategyRet: number | null;
  benchmarkRet: number | null;
  /** strategy beat benchmark this year? null if no benchmark for the year. */
  beat: boolean | null;
}

export interface HistoryProof {
  rows: HistoryRow[];
  nYears: number;
  yearRange: string;
  /** ₹1 lakh compounded by the total backtest return. null if unknown. */
  growth1L: number | null;
  avgYearly: number | null;
  beatCount: number;
  beatTotal: number; // years that had a benchmark to compare against
  worstYear: number | null;
}

export function buildHistoryProof(
  strategyAnnual: Map<number, number>,
  benchmarkAnnual: Map<number, number>,
  totalReturn: number | null,
): HistoryProof {
  const years = [...strategyAnnual.keys()].sort((a, b) => a - b);
  const rows: HistoryRow[] = years.map((year) => {
    const s = strategyAnnual.get(year) ?? null;
    const b = benchmarkAnnual.has(year) ? benchmarkAnnual.get(year)! : null;
    const beat = s != null && b != null ? s > b : null;
    return { year, strategyRet: s, benchmarkRet: b, beat };
  });

  const vals = years.map((y) => strategyAnnual.get(y)!).filter((v) => v != null);
  const avgYearly = vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : null;
  const worstYear = vals.length ? Math.min(...vals) : null;
  const beatTotal = rows.filter((r) => r.beat != null).length;
  const beatCount = rows.filter((r) => r.beat === true).length;

  return {
    rows,
    nYears: years.length,
    yearRange: years.length ? `${years[0]}–${years[years.length - 1]}` : "—",
    growth1L: totalReturn != null ? 100_000 * (1 + totalReturn) : null,
    avgYearly,
    beatCount,
    beatTotal,
    worstYear,
  };
}
