/**
 * Pure (client-safe) types, display mappers and copy for the Monthly stock rotation page.
 * Every string copies master_dashboard.py render_monthly and its helpers; every number
 * was computed in Python and saved in ui_monthly.json. No node:fs here.
 */
import {
  formatChange, formatRupees, formatSigned, pyFixed, freshnessLabel, freshnessTone, type Direction, type Tone,
} from "@/lib/desk/format";

export type ChartWindow = "1Y" | "3Y" | "All";
export const CHART_WINDOWS: ChartWindow[] = ["1Y", "3Y", "All"];
export type MonthlyFilter = "All 50" | "Top 5" | "Beating Nifty" | "Lagging Nifty";
export const MONTHLY_FILTERS: MonthlyFilter[] = ["All 50", "Top 5", "Beating Nifty", "Lagging Nifty"];

export interface MonthlySummary {
  cagr: number | null;
  total_ret: number | null;
  max_dd: number | null;
  start: string;
  end: string;
  bench_ret: number;
  bench_cagr: number;
  alpha: number;
  n_months: number | null;
}

export interface ChartTrace {
  name: string;
  colour: string;
  dash: boolean;
  points: [string, number][];
}

export interface RankRow {
  rank: number;
  ticker: string;
  symbol: string;
  company: string;
  price: number;
  month_ret: number | null;
  bench_ret: number | null;
  rs: number;
  label: string;
}

export interface CloseSeries {
  saved_to: string;
  points: [string, number][];
}

export interface RebalanceRow {
  date: string;
  top5: string;
  bought: string;
  sold: string;
  value: number;
}

export interface CheckRow {
  title: string;
  label: string;
  tone: Tone;
  note: string;
}

export interface ExitTarget {
  pct: number;
  book_pct: number;
  hit_rate: number;
}

export interface ExitRec {
  strategy?: string;
  bucket?: string;
  hold_days: number;
  hold_median_return: number;
  hold_win_rate: number;
  targets: ExitTarget[];
  stop_pct: number;
  sample_size: number;
  data_quality: string;
  curve?: Record<string, number | null>[];
}

export interface UiMonthly {
  version: number;
  generated_at: string;
  colour: string;
  summary: MonthlySummary | null;
  chart: Record<ChartWindow, ChartTrace[]> | null;
  ranking: RankRow[];
  filters: Record<MonthlyFilter, string[]>;
  default_symbol: string | null;
  top5: string[];
  closes: Record<string, CloseSeries>;
  rebalances: { total: number; rows: RebalanceRow[] };
  checks: CheckRow[];
  exit_rec: ExitRec | null;
}

/** Which row is open: the requested symbol (".NS" optional) if it is in the full ranking, else the default. */
export function resolveSelected(
  ranking: RankRow[],
  defaultSymbol: string | null,
  requested?: string | null,
): string | null {
  const wanted = requested?.replace(/\.NS$/, "");
  if (wanted && ranking.some((r) => r.symbol === wanted)) return wanted;
  return defaultSymbol ?? ranking[0]?.symbol ?? null;
}

// ---- summary (_render_monthly_summary) ---------------------------------------------------

const DASH = "—";
const pct1 = (v: number | null) => (v == null ? DASH : `${formatSigned(v, 1)}%`);

export function cagrText(s: MonthlySummary): string {
  return pct1(s.cagr);
}

export function cagrTone(s: MonthlySummary): Tone {
  return s.cagr != null && s.cagr >= 0 ? "gain" : "loss";
}

export function benchSub(s: MonthlySummary): string {
  return `vs Nifty ${formatSigned(s.bench_cagr, 1)}% per year, same period`;
}

export function summaryStats(s: MonthlySummary): { label: string; value: string; tone: Tone }[] {
  return [
    { label: "Extra vs Nifty", value: `${formatSigned(s.alpha, 1)}% / yr`, tone: s.alpha >= 0 ? "gain" : "loss" },
    { label: "Total return", value: pct1(s.total_ret), tone: "info" },
    { label: "Nifty total", value: `${formatSigned(s.bench_ret, 1)}%`, tone: "muted" },
    { label: "Worst fall from a peak", value: s.max_dd == null ? DASH : `${pyFixed(s.max_dd, 1)}%`, tone: "loss" },
    { label: "Sample", value: s.n_months ? `${s.n_months} monthly rebalances` : DASH, tone: "muted" },
  ];
}

// ---- ranking (_render_monthly_ranking / _render_monthly_detail) -----------------------------

export function rankSub(r: Pick<RankRow, "symbol" | "rank">): string {
  return r.rank <= 5 ? `${r.symbol} · top 5 candidate` : r.symbol;
}

export function rankStatus(r: Pick<RankRow, "rank">, total: number): { label: string; tone: Tone } {
  return r.rank <= 5
    ? { label: "Top-5 candidate", tone: "info" }
    : { label: `Rank ${r.rank} of ${total}`, tone: "muted" };
}

/** Tone of the model-label pill in the table: info for the top 5, muted otherwise. */
export function rankLabelTone(r: Pick<RankRow, "rank">): Tone {
  return r.rank <= 5 ? "info" : "muted";
}

export interface RankCells {
  rank: string;
  company: string;
  sub: string;
  price: string;
  move: { text: string; direction: Direction };
  rs: string;
  label: string;
}

/** The table cells exactly as `_render_monthly_ranking` builds them. */
export function rankCells(r: RankRow): RankCells {
  return {
    rank: `${r.rank}`,
    company: r.company,
    sub: rankSub(r),
    price: formatRupees(r.price, 2),
    move: formatChange(r.month_ret),
    rs: `${formatSigned(r.rs, 2)}%`,
    label: r.label,
  };
}

export function rankingAge(ageDays: number | null): { label: string; tone: Tone } {
  return { label: `Ranking ${freshnessLabel(ageDays)}`, tone: freshnessTone(ageDays) };
}

// ---- rebalances (_render_monthly_rebalances) ---------------------------------------------------

export function rebalanceCells(r: RebalanceRow): [string, string, string, string, string] {
  return [r.date, r.top5, r.bought, r.sold, formatRupees(r.value, 0)];
}

export const REBALANCE_NOTE = (total: number): string =>
  `Latest 12 of ${total} monthly rebalances, newest first. ` +
  "Bought = new entrant into the top 5. Sold = fell out of the top 5.";

// ---- exit research (_exit_playbook_card) ----------------------------------------------------------

export function exitTexts(rec: ExitRec) {
  const dq = rec.data_quality === "ohlcv" ? "daily OHLCV" : "close-only (approx.)";
  return {
    hold: `${rec.hold_days} days`,
    median: `${pyFixed(rec.hold_median_return, 1)}%`,
    winRate: `${pyFixed(rec.hold_win_rate * 100, 0)}%`,
    targets: rec.targets.map((t, n) => ({
      tier: `T${n + 1}`,
      target: `+${pyFixed(t.pct, 1)}%`,
      book: `${t.book_pct}%`,
      hit: `${pyFixed(t.hit_rate * 100, 0)}%`,
    })),
    caption: `Stop level: ${pyFixed(rec.stop_pct, 1)}%  -  sample: ${rec.sample_size} trades  -  data: ${dq}`,
  };
}

// ---- copy -------------------------------------------------------------------------------------------

export const MONTHLY_TITLE = "Monthly stock rotation";
export const MONTHLY_SUB =
  "Ranks the Nifty 50 by recent strength; the model holds the top 5 and rebalances monthly.";
export const LIVE_PILL = "Live";

export const SUMMARY_LABEL = "Avg yearly return (CAGR)";
export const CHART_LABEL = "Simulated account vs Nifty";
export const CHART_NOTE =
  "Both lines start at 0% at the beginning of the selected window. " +
  "The figures on the left always cover the full test period.";

export const CONTEXT_BASIS = "Gross · before costs and slippage";
export const CONTEXT_UNIVERSE = "Nifty 50 (current list)";
export const CONTEXT_RULE = "Top 5 by RS score, monthly";
export const testPeriod = (s: MonthlySummary | null): string => (s ? `${s.start} → ${s.end}` : DASH);

export const RANKING_TITLE = "Saved ranking";
export const RANKING_META = "Nifty 50 by RS score · click a row";
export const RANKING_NOTE =
  "RS score = the stock’s return since last month end minus the Nifty benchmark return. " +
  "The top 5 are the model’s current candidates, not your holdings. The model label is written by " +
  "the ranking script and does not consider market conditions.";
export const noMatchText = (choice: string): string => `No stocks match “${choice}” in the saved ranking.`;

export const DETAIL_ROWS = {
  price: { title: "Price", sub: "" },
  month: { title: "Month move", sub: "since last month end" },
  bench: { title: "Nifty benchmark", sub: "same period" },
  rs: { title: "RS score", sub: "move minus benchmark" },
  label: { title: "Model label", sub: "" },
} as const;
export const priceChartLabel = (sessions: number, savedTo: string): string =>
  `Closing price · last ${sessions} sessions (saved to ${savedTo})`;
export const TOP5_TITLE = "Model top 5";
export const TOP5_META = "RS score";
export const exchangeLine = (symbol: string): string => `${symbol} · NSE`;

export const TAB_TITLES = ["Rebalance log", "Rules and checks", "Exit research"] as const;

export const HOW_IT_WORKS: { text: string; bold: boolean }[] = [
  { text: "How it works:", bold: true },
  { text: " Every month, we rank all 50 Nifty stocks by their recent price strength (", bold: false },
  { text: "RS Score", bold: true },
  {
    text: "). We buy the top 5 and hold them for the month. If a stock falls out of the top 5, " +
      "the model replaces it with a new entrant. These are model rules, not purchases in your account.",
    bold: false,
  },
];
export const HOW_TO_READ_TITLE = "How to read this page";
export const HOW_TO_READ =
  "Rankings compare each stock with the market. Positive relative strength means it performed better " +
  "over the measured period. The account chart and trade history describe the saved monthly simulation. " +
  "Review dates before using a ranking.";
export const VALIDATION_TITLE = "Validation status";
export const VALIDATION_META = "what has and has not been checked";

export const EXIT_TITLE = "Exit research: Monthly stock rotation";
export const EXIT_CAPTION =
  "Exploratory historical analysis. Suggested targets and stops are not necessarily the active strategy exits; " +
  "no out-of-sample winner established.";
export const EXIT_LABELS = {
  hold: "Exploratory hold",
  holdHelp: "Trading days that historically maximised median return per unit of drawdown.",
  median: "Median return at hold",
  winRate: "Win rate at hold",
  columns: ["Tier", "Profit target", "Book", "Hit rate (hist.)"],
} as const;
export const EXIT_EMPTY = "Exit Playbook: insufficient trade history to recommend a hold/exit plan yet.";

export const FOOTER_CAPTION =
  "Daily rankings are research candidates. The backtest rotates monthly; actual holdings are not tracked here.";

export const EMPTY_NO_SIMULATION = {
  title: "No monthly simulation is saved",
  reason: "Use “Update one strategy → Monthly” in the sidebar to request data and rebuild the saved results.",
};
export const EMPTY_NO_RANKING = {
  title: "No saved ranking",
  reason: "Use “Update one strategy → Monthly” in the sidebar to download prices and rebuild the ranking.",
};
export const EMPTY_NO_REBALANCE = { title: "No rebalance log saved", reason: "rebalance_log.csv is missing or empty." };
export const emptyNoPrices = (ticker: string) => ({
  title: "No saved price history",
  reason: `data/${ticker}.csv is missing or unreadable.`,
});
