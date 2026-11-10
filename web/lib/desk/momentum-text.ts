/**
 * Pure (client-safe) types, display mappers and copy for the Momentum page. Every string copies
 * master_dashboard.py render_momentum (emoji and markdown dropped); every number was computed in
 * Python and saved in ui_momentum.json. No node:fs here.
 */
import { formatNumber, formatRupees, formatSigned, orDash, pyFixed, type Tone } from "@/lib/desk/format";
import type { ExitRec } from "@/lib/desk/exit-text";
import type { ChartTrace } from "@/lib/desk/monthly-text";

export { CONTEXT_BASIS } from "@/lib/desk/monthly-text";

export type ViewKey = "all" | "ath";
export type SetupTab = "All" | "BUY NOW" | "WATCH" | "FORMING" | "Recent";
export type TradePeriod = "Last 1Y" | "Last 3Y" | "All" | "Pick year";
export const TRADE_PERIODS: TradePeriod[] = ["Last 1Y", "Last 3Y", "All", "Pick year"];

type Num = number | null;

export interface MomentumSummary {
  cagr: Num;
  total_ret: Num;
  max_dd: Num;
  start: string;
  end: string;
}

export interface Health {
  n_trades: Num;
  win_rate: Num;
  avg_pnl: Num;
  median_pnl: Num;
  median_hold: Num;
  safe_20d_pct: Num;
  universe: string;
  verdict_text: string;
  top_lift: string;
  best_combo: string;
  verdict_tone: Tone;
}

export interface MomentumView {
  health: Health;
  counts: { breakout: number; near: number; watch: number; ath: number; clean: number; fast: number };
  signal_ids: string[];
  trade_ids: number[];
}

export interface SignalRow {
  symbol: string;
  company: string;
  signal: string;
  action: string;
  close: Num;
  ath: Num;
  dist_ath: Num;
  entry_type: string | null;
  chart_qual: string | null;
  choppiness: Num;
  recovery: string | null;
  ema220: Num;
  high52: Num;
  vs_high: Num;
  vol_ratio: Num;
  score: Num;
  hist_win: Num;
  hist_avg: Num;
  hist_n: Num;
  stop_price: Num;
  stop_pct: Num;
}

export interface RecentRow {
  symbol: string;
  days_ago: Num;
  bk_date: string | null;
  bk_price: Num;
  close: Num;
  off_bk: Num;
  ema220: Num;
  vol_ratio: Num;
  stop: Num;
}

export interface FunnelData {
  is_bull: boolean;
  total: number;
  steps: { key: string; count: number }[];
}

export interface Condition {
  ok: boolean;
  label: string;
  sub: string;
  detail: string;
}

export interface StockDetail {
  conditions: Condition[] | null;
  note: string | null;
  chart: {
    saved_to: string;
    close: [string, number | null][];
    ema220: [string, number | null][];
    level: { label: string; value: number } | null;
  } | null;
  past_trades: number;
}

export interface TradeRow {
  id: number;
  symbol: string;
  entry_date: string | null;
  entry_price: Num;
  prior_high: Num;
  bk_margin: Num;
  exit_date: string | null;
  exit_price: Num;
  pnl: Num;
  hold_days: Num;
  exit_reason: string | null;
  result: string | null;
  filters: string | null;
  entry_type: string | null;
  recovery: string | null;
}

export interface TradeFilters {
  periods: Record<string, number[]>;
  years: number[];
  strict: number[];
}

type Bucket = "All" | "BUY NOW" | "WATCH" | "FORMING";

export interface UiMomentum {
  version: number;
  generated_at: string;
  colour: string;
  summary: MomentumSummary | null;
  chart: ChartTrace[] | null;
  views: Record<ViewKey, MomentumView>;
  signals: SignalRow[];
  tabs: Record<Bucket, string[]>;
  recent: RecentRow[];
  funnel: FunnelData | null;
  details: Record<string, StockDetail>;
  trades: TradeRow[];
  trade_filters: TradeFilters;
  exit_rec: ExitRec | null;
}

const DASH = "—";

// ---- selection and filtering -------------------------------------------------------------------

/** Which stock is open: the requested one (".NS" optional) if listed, else the first signal, then the first recent. */
export function resolveSelected(
  data: Pick<UiMomentum, "signals" | "recent">,
  requested?: string | null,
): { symbol: string | null; tab: SetupTab } {
  const wanted = requested?.replace(/\.NS$/, "");
  if (wanted && data.signals.some((r) => r.symbol === wanted)) return { symbol: wanted, tab: "All" };
  if (wanted && data.recent.some((r) => r.symbol === wanted)) return { symbol: wanted, tab: "Recent" };
  if (data.signals[0]) return { symbol: data.signals[0].symbol, tab: "All" };
  if (data.recent[0]) return { symbol: data.recent[0].symbol, tab: "Recent" };
  return { symbol: null, tab: "All" };
}

/** Signals in both the chosen view and the chosen tab, in saved order. */
export function tabRows(data: UiMomentum, view: ViewKey, tab: Exclude<SetupTab, "Recent">): SignalRow[] {
  const inView = new Set(data.views[view].signal_ids);
  const inTab = new Set(data.tabs[tab]);
  return data.signals.filter((r) => inView.has(r.symbol) && inTab.has(r.symbol));
}

export function tabLabels(data: UiMomentum, view: ViewKey): { id: SetupTab; label: string }[] {
  const n = (tab: Exclude<SetupTab, "Recent">) => tabRows(data, view, tab).length;
  return [
    { id: "All", label: `All ${n("All")}` },
    { id: "BUY NOW", label: `Buy now ${n("BUY NOW")}` },
    { id: "WATCH", label: `Watch ${n("WATCH")}` },
    { id: "FORMING", label: `Forming ${n("FORMING")}` },
    { id: "Recent", label: `Broke out last 7 days ${data.recent.length}` },
  ];
}

/** Past trades after the view, period and strict filters (render_momentum ~7436-7466). */
export function visibleTrades(
  data: UiMomentum,
  view: ViewKey,
  period: TradePeriod,
  year: number | null,
  strict: boolean,
): { rows: TradeRow[]; hidden: number } {
  const { periods, strict: strictIds } = data.trade_filters;
  // Pick year without a year shows everything, as Streamlit does.
  const key = period === "Pick year" ? (year == null ? "All" : String(year)) : period;
  const inView = new Set(data.views[view].trade_ids);
  const inPeriod = new Set(periods[key] ?? []);
  const base = data.trades.filter((t) => inView.has(t.id) && inPeriod.has(t.id));
  if (!strict) return { rows: base, hidden: 0 };
  const clean = new Set(strictIds);
  const rows = base.filter((t) => clean.has(t.id));
  return { rows, hidden: base.length - rows.length };
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
function monthYear(iso: string | null): string {
  const m = iso ? /^(\d{4})-(\d{2})/.exec(iso) : null;
  return m ? `${MONTHS[Number(m[2]) - 1]} ${m[1]}` : DASH;
}

export function tradesCaption(
  shown: number,
  total: number,
  firstExit: string | null,
  lastExit: string | null,
  strict: boolean,
  hidden: number,
): string {
  return `Showing ${shown} trades of ${total} total. Range: ${monthYear(firstExit)} → ${monthYear(lastExit)}. ` +
    (strict
      ? `Clean signals only hid ${hidden} marginal trade(s) in this window.`
      : "Turn on Clean signals only to hide marginal-breakout entries.");
}

// ---- strategy health (_render_health_hero and the render_momentum metric row) -----------------

export function healthStats(
  h: Health,
  s: MomentumSummary | null,
): { label: string; value: string; sub?: string; tone: Tone }[] {
  const pct = (v: Num | undefined, d: number) => orDash(v, (n) => `${pyFixed(n, d)}%`);
  const win = h.win_rate;
  const safe = h.safe_20d_pct;
  return [
    {
      label: "Total return",
      value: orDash(s?.total_ret, (n) => `${formatSigned(n, 1)}%`),
      tone: s?.total_ret == null ? "muted" : s.total_ret >= 0 ? "gain" : "loss",
    },
    { label: "Worst fall from a peak", value: pct(s?.max_dd, 1), tone: s?.max_dd == null ? "muted" : "loss" },
    {
      label: "Trades that made money",
      value: win == null ? DASH : `${pyFixed(win, 0)}% of ${orDash(h.n_trades, String)}`,
      tone: win == null ? "muted" : win >= 50 ? "gain" : "warn",
    },
    {
      label: "Average per trade",
      value: orDash(h.avg_pnl, (n) => `${formatSigned(n, 2)}%`),
      sub: `median ${orDash(h.median_pnl, (n) => `${formatSigned(n, 2)}%`)}`,
      tone: h.avg_pnl == null ? "muted" : h.avg_pnl > 0 ? "gain" : "loss",
    },
    { label: "Typical hold", value: orDash(h.median_hold, (n) => `${n} days`), tone: "muted" },
    {
      label: "Loss-free 20+ days",
      value: pct(safe, 0),
      tone: safe == null ? "muted" : safe >= 40 ? "gain" : "warn",
    },
  ];
}

// ---- table cells (_render_subset and the past-trades table) -------------------------------------

const rupees = (v: Num) => orDash(v, (n) => formatRupees(n, 2));
const signedPct1 = (v: Num) => orDash(v, (n) => `${formatSigned(n, 1)}%`);
const plain = (v: Num) => orDash(v, String);
const text = (v: string | null) => v ?? DASH;
/** Python `str(float)` for the unformatted score columns: 53.0 stays "53.0", 68.3 stays "68.3". */
const floatText = (v: Num) => orDash(v, (n) => (Number.isInteger(n) ? n.toFixed(1) : String(n)));

export function signalCells(r: SignalRow) {
  return {
    close: rupees(r.close),
    stop: rupees(r.stop_price),
    stopPct: signedPct1(r.stop_pct),
    ath: rupees(r.ath),
    distAth: signedPct1(r.dist_ath),
    entryType: text(r.entry_type),
    chartQual: text(r.chart_qual),
    choppiness: floatText(r.choppiness),
    recovery: text(r.recovery),
    ema220: rupees(r.ema220),
    high52: rupees(r.high52),
    vsHigh: signedPct1(r.vs_high),
    volRatio: orDash(r.vol_ratio, (n) => `${pyFixed(n, 2)}×`),
    score: floatText(r.score),
    histWin: orDash(r.hist_win, (n) => `${pyFixed(n, 0)}%`),
    histAvg: signedPct1(r.hist_avg),
  };
}

/** Python `_exit_badge`: "Hold ~65d - T1/T2/T3 +22/+70/+133% - Stop -10%". */
export function exitBadge(rec: ExitRec | null): string {
  if (!rec) return "-";
  const tg = rec.targets ?? [];
  const tline = tg.length >= 3
    ? `T1/T2/T3 ${tg.slice(0, 3).map((t) => `+${orDash(t.pct, (n) => pyFixed(n, 0))}`).join("/")}%`
    : "targets n/a";
  return `Hold ~${plain(rec.hold_days)}d - ${tline} - Stop ${orDash(rec.stop_pct, (n) => pyFixed(n, 0))}%`;
}

/** The Recent tab shows the same rupee, percent and times formats as the setups table. */
export function recentCells(r: RecentRow) {
  return {
    daysAgo: plain(r.days_ago),
    bkDate: text(r.bk_date),
    bkPrice: rupees(r.bk_price),
    close: rupees(r.close),
    offBk: signedPct1(r.off_bk),
    ema220: rupees(r.ema220),
    volRatio: orDash(r.vol_ratio, (n) => `${pyFixed(n, 2)}×`),
    stop: rupees(r.stop),
  };
}

export function tradeCells(r: TradeRow) {
  return {
    entryDate: text(r.entry_date),
    entryPrice: rupees(r.entry_price),
    priorHigh: rupees(r.prior_high),
    // Python: '+{x:.2f}%' for x >= 0, '{x:.2f}%' otherwise.
    bkMargin: orDash(r.bk_margin, (n) => `${n >= 0 ? "+" : ""}${pyFixed(n, 2)}%`),
    exitDate: text(r.exit_date),
    exitPrice: rupees(r.exit_price),
    pnl: orDash(r.pnl, (n) => `${formatSigned(n, 2)}%`),
    held: plain(r.hold_days),
    exitReason: text(r.exit_reason),
    result: text(r.result),
    filters: text(r.filters),
    entryType: text(r.entry_type),
    recovery: text(r.recovery),
  };
}

// ---- conditions and funnel ---------------------------------------------------------------------------

const CONDITION_TITLES: Record<string, string> = {
  F1: "Long-term trend up",
  F2: "Price above 50-day average",
  F3: "Averages stacked in order",
  F4: "Well above yearly low",
  F5: "Recent dip below 220-day line",
  F6: "Clean chart",
};

export function conditionTitle(label: string): string {
  if (label.includes("Breakout Trigger")) return "Breakout with volume";
  const prefix = /^(F[1-6])(?!\d)/.exec(label.trim());
  return prefix ? CONDITION_TITLES[prefix[1]] : label;
}

export const FUNNEL_LABELS: Record<string, string> = {
  total: "Universe",
  sufficient_data: "Has 1 year of prices",
  f1: "Long-term trend up",
  f2: "Above 50-day average",
  f3: "Averages stacked",
  f4: "Above yearly low",
  f5: "Dip recovered",
  f6: "Clean chart",
  vol_bk: "Breakout + volume",
};

// ---- copy --------------------------------------------------------------------------------------------

export const MOMENTUM_TITLE = "Price strength (Momentum)";
export const MOMENTUM_SUB = "Study stocks making new highs and the trend checks behind each saved setup.";
export const HOW_TO_READ_TITLE = "How to read this page";
export const HOW_TO_READ =
  "A breakout is a move above a previous price high. Trend checks compare price with longer-term averages. " +
  "Use the company details to inspect each check; the historical test shows what happened to earlier model trades.";
export const BUY_NOW_NOTE = "BUY NOW is the model’s signal label, not an instruction or an executed order.";
export const EXIT_RULES =
  "A closing price more than 15% below entry triggers an exit at that close. Otherwise, a close below the " +
  "220-day weighted average queues an exit at the next opening price. The 15% rule takes precedence; " +
  "losses can exceed that level. Proposed targets and stops elsewhere are separate research.";

export const ATH_SWITCH_LABEL = "Which breakouts count";
export const ATH_OPTIONS = ["52-week or all-time high", "All-time high only"] as const;
export const ATH_NOTE =
  "Yearly return, total return, worst fall and the growth chart always include every saved trade. " +
  "The switch changes the setups, past trades and trade stats.";

export const CHART_LABEL = "Simulated account (₹10 lakh start)";
export const CHART_NOTE =
  "This shows how ₹10 lakh invested at the start of the backtest would have grown over time following every " +
  "signal from this strategy. Each peak = new all-time high for the portfolio. Dips = times the market corrected.";

export const SETUPS_TITLE = "Today's setups";
export const SETUPS_META = "Sorted by score · evaluated on yesterday's close";
export const RECENT_NOTE =
  "Stocks that crossed their prior 52-week close high in the past week. They may have pulled back today (so they " +
  "do not appear as BUY NOW) but are still trading above their EMA220 and above 92% of the breakout price, i.e. " +
  "still buyable on a pullback. % off breakout is how far today's close is from the breakout-day close " +
  "(negative = pulled back).";
export const HIST_NOTE =
  "Hist Win% / Hist Avg% — historical performance of past trades with the same Entry Type + Recovery Speed " +
  "combo. Based on closed backtest trades only.";

export const FUNNEL_TITLE = (total: number): string => `How ${formatNumber(total, 0)} stocks narrow to today's list`;
export const FUNNEL_NOTE =
  "Each step is a filter the stock must pass. The drop from one bar to the next is how many failed that gate.";

export const TRADES_LEGEND =
  "BK Margin = how much the signal-day close exceeded the prior 52-week close high. Margins under +1% " +
  "(like AXISBANK +0.25% on 14 Jan 2026) are knife-edge breakouts that often fail. Clean signals only hides them. " +
  "The Filters column shows how many conditions passed on signal day and names any that failed: F1 trend · " +
  "F2 close>SMA50 · F3 MA align · F4 vs 52W low · F5 dip · F6 choppiness · BK breakout · V volume.";

export const COLUMN_GUIDE: [string, string][] = [
  ["Signal", "Breakout Today = best, Near Breakout = almost there, Watch Zone = monitor"],
  ["Close", "Today's last traded price"],
  ["ATH (₹)", "All-Time High price — the highest this stock has ever traded"],
  ["Dist ATH%", "How far today's price is from the all-time high. 0% = AT the all-time high"],
  ["Entry Type", "ATH = breaking all-time high · 52W = breaking 52-week high (second best)"],
  ["Chart Qual", "Clean = chart looks tidy, no messy sideways action (Choppiness < 55)"],
  ["Choppiness", "0–100 score. Below 55 = trending. Above 62 = choppy/sideways — avoid"],
  ["Recovery", "Fast = bounced back from dip in <30 days · Slow = took longer"],
  ["220 EMA", "The long-term average price (220 days). Stock must be above this to qualify"],
  ["Vol Ratio", "Today's volume ÷ 20-day average. Above 1.5× = strong buying interest"],
  ["Score", "Overall quality score (0–10). Higher = better setup. Sort by this to prioritise"],
];

export const RAIL_PLACEHOLDER = {
  title: "Pick a stock",
  reason: "Select a row in the table to see its checks and chart.",
};

/** BSE-only symbols carry the .BO suffix in the saved data; everything else is NSE. */
export function exchangeOf(symbol: string): "NSE" | "BSE" {
  return symbol.toUpperCase().endsWith(".BO") ? "BSE" : "NSE";
}

/** One line under the setups head: the saved counts for the current view. */
export function countsLine(counts: { ath: number; clean: number; fast: number }): string {
  return `All-time-high entries ${counts.ath} · Clean charts ${counts.clean} · Fast recovery ${counts.fast}`;
}

export const OLD_APP_LINK = "Single-stock backtest: open in the old app";
export const EMPTY_NO_SIGNALS = {
  title: "No signals found today",
  reason:
    "Use “Update one strategy → Momentum” in the sidebar to pull fresh market data. Signals appear when a " +
    "stock passes all 8 filters simultaneously — this is intentionally selective.",
};
export const CONTEXT_UNIVERSE = (total: number): string => `NSE + BSE, ${formatNumber(total, 0)} stocks`;
export const CONTEXT_RULE = "New high above 220-day line · exit −15% or close below it";

export const HOLD_EXIT_TITLE = "Hold and exit plan: Price strength (Momentum)";

/** Extra Hold and exit rows from the current ATH view's health numbers. */
export function holdExitExtras(h: Health): { label: string; value: string }[] {
  return [
    { label: "Trades in profit at exit",
      value: h.win_rate == null ? DASH : `${pyFixed(h.win_rate, 0)}% of ${orDash(h.n_trades, String)}` },
    { label: "Stayed above entry 20+ days", value: orDash(h.safe_20d_pct, (n) => `${pyFixed(n, 0)}%`) },
  ];
}
