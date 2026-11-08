/**
 * Pure (client-safe) types, display mappers and copy for the IPO page. Every string copies
 * master_dashboard.py render_ipo (emoji and markdown dropped); every number was computed in
 * Python and saved in ui_ipo.json. No node:fs here.
 */
import { formatRupees, formatSigned, orDash, pyFixed, type Tone } from "@/lib/desk/format";
import type { ExitRec } from "@/lib/desk/exit-text";
import type { ChartTrace } from "@/lib/desk/monthly-text";

export { CONTEXT_BASIS } from "@/lib/desk/monthly-text";

type Num = number | null;
/** Display strings from Python (e.g. "25.0 🟢", "Liquid ✅") may also arrive as numbers. */
type Loose = string | number | null;

export interface IpoSummary {
  cagr: Num;
  total_ret: Num;
  max_dd: Num;
  start: string;
  end: string;
}

export interface IpoCounts {
  live_breakout: number;
  watch_zone: number;
  stage3: number;
  stage2: number;
  stage1: number;
  in_trade: number;
  trades: number;
  win_rate: Num;
}

export interface IpoSignal {
  symbol: string;
  company: string | null;
  signal: string | null;
  stage: string | null;
  setup: string | null;
  close: Num;
  bk_level: Num;
  vs_bk: Num;
  vol_ratio: Num;
  ipo_day_val: Num;
  liquidity: Loose;
  promoter: Loose;
  listing_pe: Loose;
  age_days: Num;
  score: Num;
  hist_win: Num;
  hist_avg: Num;
}

export interface IpoTrade {
  id: number;
  symbol: string;
  entry_date: string | null;
  entry_price: Num;
  exit_date: string | null;
  exit_price: Num;
  pnl: Num;
  hold_days: Num;
  exit_reason: string | null;
  result: string | null;
  extras: Record<string, string | null>;
}

export interface UiIpo {
  version: number;
  generated_at: string;
  colour: string;
  summary: IpoSummary | null;
  chart: ChartTrace[] | null;
  counts: IpoCounts;
  signals: IpoSignal[];
  trades: IpoTrade[];
  extra_columns: string[];
  exit_rec: ExitRec | null;
}

const DASH = "—";

/** A missing display string: null, empty, Python's "nan" or an existing dash all show "—". */
function text(v: string | number | null | undefined): string {
  if (v == null) return DASH;
  const s = String(v).trim();
  return s === "" || s.toLowerCase() === "nan" || s === DASH ? DASH : s;
}

const rupees = (v: Num) => orDash(v, (n) => formatRupees(n, 2));
const plain = (v: Num) => orDash(v, String);
/** Python `str(float)` for the unformatted score column: 7.0 stays "7.0". */
const floatText = (v: Num) => orDash(v, (n) => (Number.isInteger(n) ? n.toFixed(1) : String(n)));

// ---- summary pills -------------------------------------------------------------------------------

export function summaryStats(
  s: IpoSummary | null,
  c: IpoCounts,
): { label: string; value: string; sub?: string; tone: Tone }[] {
  const win = c.win_rate;
  return [
    {
      label: "Total return",
      value: orDash(s?.total_ret, (n) => `${formatSigned(n, 1)}%`),
      tone: s?.total_ret == null ? "muted" : s.total_ret >= 0 ? "gain" : "loss",
    },
    {
      label: "Worst fall from a peak",
      value: orDash(s?.max_dd, (n) => `${pyFixed(n, 1)}%`),
      tone: s?.max_dd == null ? "muted" : "loss",
    },
    {
      label: "Trades that made money",
      value: orDash(win, (n) => `${pyFixed(n, 0)}%`),
      sub: `${c.trades} trades`,
      tone: win == null ? "muted" : win >= 50 ? "gain" : "warn",
    },
    {
      label: "Ready to break out",
      value: String(c.stage3),
      sub: `Recovering: ${c.stage2} · Building: ${c.stage1}`,
      tone: c.stage3 > 0 ? "gain" : "muted",
    },
    {
      label: "Currently in trade",
      value: String(c.in_trade),
      sub: `Live breakout signals: ${c.live_breakout}`,
      tone: c.in_trade > 0 ? "info" : "muted",
    },
  ];
}

/** Growth chart label: the Nifty line is only named when the benchmark trace exists. */
export function chartLabel(traceCount: number): string {
  return traceCount >= 2 ? "Simulated account vs Nifty" : "Simulated account";
}

// ---- table cells (render_ipo's screener and trade-history formats) ----------------------------------

export function signalCells(r: IpoSignal) {
  return {
    company: text(r.company),
    signal: text(r.signal),
    stage: text(r.stage),
    setup: text(r.setup),
    close: rupees(r.close),
    bkLevel: rupees(r.bk_level),
    vsBk: orDash(r.vs_bk, (n) => `${formatSigned(n, 1)}%`),
    volRatio: orDash(r.vol_ratio, (n) => `${pyFixed(n, 2)}×`),
    ipoDayVal: orDash(r.ipo_day_val, (n) => `₹${pyFixed(n, 1)} Cr`),
    liquidity: text(r.liquidity),
    promoter: text(r.promoter),
    listingPe: text(r.listing_pe),
    age: plain(r.age_days),
    score: floatText(r.score),
    histWin: orDash(r.hist_win, (n) => `${pyFixed(n, 0)}%`),
    histAvg: orDash(r.hist_avg, (n) => `${formatSigned(n, 1)}%`),
  };
}

export function tradeCells(r: IpoTrade) {
  return {
    entryDate: text(r.entry_date),
    entryPrice: rupees(r.entry_price),
    exitDate: text(r.exit_date),
    exitPrice: rupees(r.exit_price),
    pnl: orDash(r.pnl, (n) => `${formatSigned(n, 2)}%`),
    held: plain(r.hold_days),
    exitReason: text(r.exit_reason),
    result: text(r.result),
    extras: Object.fromEntries(Object.entries(r.extras ?? {}).map(([k, v]) => [k, text(v)])) as Record<string, string>,
  };
}

// ---- tones --------------------------------------------------------------------------------------------

export function signalTone(signal: string | null): Tone {
  switch (signal) {
    case "Live Breakout": return "gain";
    case "Watch Zone": return "warn";
    case "Forming Base": return "info";
    case "Avoid": return "loss";
    default: return "muted";
  }
}

/** "Open" is keyed off the saved result, never off missing exits (open trades carry a mark-to-market exit). */
export function resultTone(result: string | null): Tone {
  return result === "Win" ? "gain" : result === "Loss" ? "loss" : "muted";
}

// ---- copy -----------------------------------------------------------------------------------------------

export const IPO_TITLE = "Newly listed stocks (IPO)";
export const IPO_SUB = "Review newly listed companies moving above an early trading range.";
export const HOW_IT_WORKS: { text: string; bold: boolean }[] = [
  { text: "How it works:", bold: true },
  { text: " When a stock lists on NSE, it often trades sideways for ~40 days (the “", bold: false },
  { text: "base", bold: true },
  { text: "”). Once it breaks above that base ", bold: false },
  { text: "with strong volume", bold: true },
  {
    text: ", we enter. We exit when it drops below its 10-day average or hits a hard stop. " +
      "A partial profit is booked at +15% gain.",
    bold: false,
  },
];
export const HOW_TO_READ_TITLE = "How to read this page";
export const HOW_TO_READ =
  "A breakout means price moved above the model’s reference range. A watch-zone company is near that level. " +
  "Trading volume counts shares traded. Signals identify setups to research; the historical charts show simulated outcomes.";

export const SCREENER_TITLE = "Live screener: IPOs listed in the last 12 months";
export const SIGNAL_GUIDE: [string, string][] = [
  ["Live Breakout", "buy signal now"],
  ["Watch Zone", "almost ready, monitor closely"],
  ["Forming Base", "wait, not ready yet"],
  ["Avoid", "broken, skip"],
];
export const STAGE_GUIDE: [string, string][] = [
  ["Stage", "3=Breakout 2=Recovering 1=Base In Trade=Held now"],
  ["Vol Ratio", ">1.5× = strong volume (confirms breakout)"],
  ["Score", "0–10, higher = better quality setup"],
];
export const HIST_NOTE =
  "Hist Win% / Hist Avg% — overall historical IPO Edge win rate from closed trades.";
export const EMPTY_NO_SIGNALS = {
  title: "No IPO setups to show",
  reason: "Use “Update one strategy → IPO” in the sidebar to refresh the newly listed stocks.",
};
export const CHART_LABEL = "Simulated account";
export const CONTEXT_UNIVERSE = "Newly listed NSE stocks (last 12 months)";
export const CONTEXT_RULE = "Breakout above the post-listing base with volume";
