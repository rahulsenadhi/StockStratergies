/**
 * Pure (client-safe) exit research types, display mapper and copy, shared by the Monthly and
 * Momentum desk pages (master_dashboard.py _exit_playbook_card). No node:fs here.
 */
import { LOW_SAMPLE_TRADES, formatSigned, orDash, pyFixed } from "@/lib/desk/format";

/** Saved numbers that Python wrote as NaN arrive as null; `targets` may be missing (Python reads it with .get). */
export interface ExitTarget {
  pct: number | null;
  book_pct: number | null;
  hit_rate: number | null;
}

export interface ExitRec {
  strategy?: string;
  bucket?: string;
  hold_days: number | null;
  hold_median_return: number | null;
  hold_win_rate: number | null;
  targets?: ExitTarget[] | null;
  stop_pct: number | null;
  sample_size: number | null;
  data_quality: string;
  curve?: Record<string, number | null>[];
}

// ---- exit research (_exit_playbook_card) ----

export function exitTexts(rec: ExitRec) {
  const dq = rec.data_quality === "ohlcv" ? "daily OHLCV" : "close-only (approx.)";
  return {
    hold: orDash(rec.hold_days, (n) => `${n} days`),
    median: orDash(rec.hold_median_return, (n) => `${pyFixed(n, 1)}%`),
    winRate: orDash(rec.hold_win_rate, (n) => `${pyFixed(n * 100, 0)}%`),
    targets: (rec.targets ?? []).map((t, n) => ({
      tier: `T${n + 1}`,
      target: orDash(t.pct, (v) => `+${pyFixed(v, 1)}%`),
      book: orDash(t.book_pct, (v) => `${v}%`),
      hit: orDash(t.hit_rate, (v) => `${pyFixed(v * 100, 0)}%`),
    })),
    caption: `Stop level: ${orDash(rec.stop_pct, (n) => `${pyFixed(n, 1)}%`)}  -  ` +
      `sample: ${orDash(rec.sample_size, String)} trades  -  data: ${dq}`,
  };
}

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

// ---- Hold and exit plan card ----

export const HOLD_EXIT_LABELS = {
  hold: "Researched hold",
  median: "Median return at that hold",
  sellPlan: "Sell plan",
  stop: "Stop level",
  columns: ["Tier", "Sell at", "Sell this much", "Hit before (hist.)"],
} as const;

export const SMALL_SAMPLE_NOTE = `Small sample: fewer than ${LOW_SAMPLE_TRADES} past trades, so treat these numbers as rough.`;

export const HOLD_RESEARCH_NOTE = "Hold research uses all past trades.";

/** Plain statement that the numbers are history, never a promise. */
export const HONESTY_NOTE = (lossPct: number) =>
  `Past results, not a promise. At the suggested hold, ${lossPct}% of past trades still lost money.`;

/** Display text for the Hold and exit plan card, from the saved exit_rec. */
export function holdExitRows(rec: ExitRec) {
  const t = exitTexts(rec);
  const sample = rec.sample_size;
  return {
    hold: t.hold,
    winRate: t.winRate,
    winRateLabel: `Success rate if held exactly ${orDash(rec.hold_days, String)} days ` +
      `(${orDash(sample, String)} trades tested)`,
    median: orDash(rec.hold_median_return, (n) => `${formatSigned(n, 1)}%`),
    stop: orDash(rec.stop_pct, (n) => `${pyFixed(n, 1)}%`),
    basis: `Based on ${orDash(sample, String)} past trades`,
    isSmallSample: sample != null && Number.isFinite(sample) && sample < LOW_SAMPLE_TRADES,
    lossPct: rec.hold_win_rate == null || !Number.isFinite(rec.hold_win_rate)
      ? null : Number(pyFixed((1 - rec.hold_win_rate) * 100, 0)),
    dataQuality: rec.data_quality === "ohlcv" ? "daily OHLCV" : "close-only (approx.)",
    targets: t.targets,
  };
}
