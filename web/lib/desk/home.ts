/**
 * Home page text and rows. Every string copies master_dashboard.py's render_home helpers
 * (_render_home_header/_candidates/_growth/_market/_strategies) so both apps read the same.
 */
import { formatNumber, freshnessLabel, LOW_SAMPLE_TRADES, type Tone } from "@/lib/desk/format";
import type { Candidate, Regime, StrategyRow } from "@/lib/desk/snapshot";

export const CANDIDATE_FILTERS = ["All", "Monthly", "IPO", "Momentum"] as const;
export type CandidateFilter = (typeof CANDIDATE_FILTERS)[number];

export const CANDIDATE_NOTE =
  "Move: month return for Monthly, distance from the all-time high for Momentum. " +
  "Labels come from each strategy’s own rules; they are model output, not advice.";
export const PEAD_NOTE = "PEAD has no saved signals; screen companies on the PEAD page.";
export const GROWTH_NOTE =
  "Each line starts at 0% at the start of the window, or at its own first test date if later, " +
  "so lines can cover different periods. PEAD is not shown (4 completed trades).";
export const STRATEGIES_NOTE = "Gross results over different test periods; not a ranking of future performance.";
export const HOW_TO_READ =
  "Per year (CAGR) is annualised growth over each strategy’s whole test. Worst fall is the " +
  "largest drop below an earlier peak. Win rates and full figures are on each strategy page; " +
  "a high win rate does not by itself mean a strategy was profitable. Fewer than " +
  `${LOW_SAMPLE_TRADES} completed trades is too few to rely on. ` +
  "Live and Paper are strategy labels, not a connected brokerage account.";

export function filterCandidates(cands: readonly Candidate[], pick: CandidateFilter): Candidate[] {
  return pick === "All" ? [...cands] : cands.filter((c) => c.short === pick);
}

export function candidateNote(peadHasSignals: boolean): string {
  return peadHasSignals ? CANDIDATE_NOTE : `${CANDIDATE_NOTE} ${PEAD_NOTE}`;
}

export function strategySub(s: Pick<StrategyRow, "status" | "num_trades" | "unit" | "small_sample" | "max_dd_pct">): string {
  const small = s.small_sample ? " · small sample" : "";
  return `${s.status} · ${s.num_trades.toLocaleString("en-US")} ${s.unit}${small} · worst fall ${s.max_dd_pct.toFixed(1)}%`;
}

export function headerTrend(status: string | undefined): { label: string; tone: Tone } {
  if (status === "Bull") return { label: "Trend filter on", tone: "gain" };
  if (status === "Bear") return { label: "Trend filter off", tone: "warn" };
  return { label: "Trend unknown", tone: "muted" };
}

export function headerSub(nCandidates: number): string {
  return `${nCandidates} candidates in saved files · research only, nothing here places orders`;
}

/** Python: freshness_label(int(age_h // 24)) if age_h is not None else 'age unknown'. */
export function priceAge(ageHours: number | null | undefined): string {
  return ageHours == null ? "age unknown" : freshnessLabel(Math.floor(ageHours / 24));
}

export interface MarketRow {
  title: string;
  sub?: string;
  pill?: { label: string; tone: Tone };
  text?: string;
  change?: number | null;
}

/** Rows of the Market rail list, in _render_home_market's order and conditions. */
export function marketRows(r: Regime): MarketRow[] {
  const pill = r.status === "Bull" ? { label: "On", tone: "gain" as Tone }
    : r.status === "Bear" ? { label: "Off", tone: "warn" as Tone } : { label: "Unknown", tone: "muted" as Tone };
  const rows: MarketRow[] = [{ title: "Trend filter", sub: "all Nifty trend conditions must pass", pill }];
  if (r.close) {
    rows.push(
      { title: "Nifty close", sub: r.date ?? "", text: formatNumber(r.close) },
      { title: "50-day average", text: formatNumber(r.sma50 ?? 0) },
      { title: "200-day average", text: formatNumber(r.sma200 ?? 0) },
      { title: "From 52-week high", change: r.pct_from_high ?? null },
    );
  }
  if (r.bars_since_flip) rows.push({ title: "In this state", text: `${r.bars_since_flip} sessions` });
  return rows;
}
