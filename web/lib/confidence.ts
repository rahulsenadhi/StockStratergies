/** Strategy confidence score. Faithful port of master_dashboard.py's
 *  _compute_confidence (~L4803): 5 pass/fail criteria, 20 points each.
 *
 *    1. Positive total return
 *    2. Beat benchmark CAGR (alpha > 0)   — "no data" if no benchmark
 *    3. Win rate > 45%   (falls back to % positive years when win rate is absent)
 *    4. Sharpe ratio > 0.3
 *    5. Max drawdown better than -25%
 *
 *  All KPI inputs are fractions (e.g. 0.21 = 21%), matching the loader's Kpis.
 */
import type { Kpis } from "@/lib/data/strategies";

export type ConfidenceLevel = "HIGH" | "MODERATE" | "CAUTION" | "LOW" | "NO DATA";

export interface ConfidenceCriterion {
  label: string;
  value: string;
  /** true = passed, false = failed, null = not applicable / no data. */
  pass: boolean | null;
  detail: string;
}

export interface ConfidenceResult {
  score: number; // 0..100
  level: ConfidenceLevel;
  criteria: ConfidenceCriterion[];
}

const pctStr = (frac: number): string => `${frac >= 0 ? "+" : ""}${(frac * 100).toFixed(1)}%`;

function level(score: number): ConfidenceLevel {
  if (score >= 80) return "HIGH";
  if (score >= 60) return "MODERATE";
  if (score >= 40) return "CAUTION";
  return "LOW";
}

export function computeConfidence(
  kpis: Kpis,
  annualReturns: (number | null)[] = [],
): ConfidenceResult {
  // No KPI at all -> no data (mirrors Streamlit's empty-equity guard).
  const allNull =
    kpis.totalReturn == null &&
    kpis.cagr == null &&
    kpis.sharpe == null &&
    kpis.maxDd == null;
  if (allNull) {
    return { score: 0, level: "NO DATA", criteria: [] };
  }

  const criteria: ConfidenceCriterion[] = [];
  let score = 0;
  const add = (passed: boolean): void => {
    if (passed) score += 20;
  };

  // 1. Positive total return
  {
    const tr = kpis.totalReturn;
    const passed = tr != null && tr > 0;
    add(passed);
    criteria.push({
      label: "Positive Total Return",
      value: tr != null ? pctStr(tr) : "—",
      pass: passed,
      detail: "Strategy made money over the backtest period",
    });
  }

  // 2. Beat benchmark (alpha > 0) — null alpha => no benchmark data
  {
    const alpha = kpis.alpha;
    if (alpha != null) {
      const passed = alpha > 0;
      add(passed);
      criteria.push({
        label: "Beat NiftyBees (CAGR)",
        value: `Alpha ${pctStr(alpha)}/yr`,
        pass: passed,
        detail: "Strategy CAGR vs NiftyBees benchmark",
      });
    } else {
      criteria.push({
        label: "Beat NiftyBees (CAGR)",
        value: "No benchmark data",
        pass: null,
        detail: "Benchmark not available",
      });
    }
  }

  // 3. Win rate > 45% — fall back to % positive years when win rate is absent
  {
    const wr = kpis.winRate;
    if (wr != null) {
      const passed = wr > 0.45;
      add(passed);
      criteria.push({
        label: "Win Rate > 45%",
        value: pctStr(wr),
        pass: passed,
        detail: "Share of closed trades that were profitable",
      });
    } else {
      const yrs = annualReturns.filter((r): r is number => r != null);
      const pctPos = yrs.length ? yrs.filter((r) => r > 0).length / yrs.length : 0;
      const passed = pctPos > 0.5;
      add(passed);
      criteria.push({
        label: "% Positive Years",
        value: `${(pctPos * 100).toFixed(0)}%`,
        pass: passed,
        detail: "Share of years with positive returns",
      });
    }
  }

  // 4. Sharpe ratio > 0.3
  {
    const s = kpis.sharpe;
    const passed = s != null && s > 0.3;
    add(passed);
    criteria.push({
      label: "Sharpe Ratio > 0.3",
      value: s != null ? s.toFixed(2) : "—",
      pass: passed,
      detail: "Risk-adjusted return (higher = better, >1 is excellent)",
    });
  }

  // 5. Max drawdown better than -25%
  {
    const dd = kpis.maxDd;
    const passed = dd != null && dd > -0.25;
    add(passed);
    criteria.push({
      label: "Max Drawdown < 25%",
      value: dd != null ? pctStr(dd) : "—",
      pass: passed,
      detail: "Worst peak-to-trough loss (smaller = more controlled)",
    });
  }

  return { score, level: level(score), criteria };
}
