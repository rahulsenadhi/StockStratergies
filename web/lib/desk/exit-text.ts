/**
 * Pure (client-safe) exit research types, display mapper and copy, shared by the Monthly and
 * Momentum desk pages (master_dashboard.py _exit_playbook_card). No node:fs here.
 */
import { orDash, pyFixed } from "@/lib/desk/format";

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
