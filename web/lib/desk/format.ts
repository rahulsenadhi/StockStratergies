/**
 * Display formatting for the Research Desk. Each function copies a Python helper
 * in core/ui_components.py exactly, so Next.js and Streamlit show the same text.
 */

export type Tone = "gain" | "loss" | "warn" | "info" | "muted";
export type Direction = "up" | "down" | "flat";

/** Python FRESH_MAX_DAYS / AGING_MAX_DAYS. */
const FRESH_MAX_DAYS = 7;
const AGING_MAX_DAYS = 21;

/** Python LOW_SAMPLE_TRADES: below this, a KPI is labelled "small sample". */
export const LOW_SAMPLE_TRADES = 30;

/**
 * Python `f"{value:.{decimals}f}"`. JS toFixed rounds an exact tie (3.125 at 2 decimals) up
 * where Python rounds it to even, so ties are detected from the exact expansion and corrected.
 */
export function pyFixed(value: number, decimals: number): string {
  const rounded = Object.is(value, -0) ? `-${value.toFixed(decimals)}` : value.toFixed(decimals);
  const exact = Math.abs(value).toFixed(Math.min(100, decimals + 30));
  const tail = exact.slice(exact.length - 30);
  if (!/^50*$/.test(tail)) return rounded;
  const kept = exact.slice(0, exact.length - 30).replace(/\.$/, "");
  const even = Number(kept[kept.length - 1]) % 2 === 0;
  return even ? `${value < 0 ? "-" : ""}${kept}` : rounded;
}

/**
 * The one null-tolerant path for saved numbers: a value Python saved as NaN arrives as null,
 * so null, undefined and non-finite values show "—" instead of reaching `toFixed`.
 */
export function orDash(value: number | null | undefined, format: (value: number) => string): string {
  return value == null || !Number.isFinite(value) ? "—" : format(value);
}

/** Python `f"{value:,.{decimals}f}"`, e.g. 25030.35 -> "25,030.35". */
export function formatNumber(value: number, decimals = 2): string {
  const [int, frac] = pyFixed(value, decimals).split(".");
  const grouped = int.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return frac === undefined ? grouped : `${grouped}.${frac}`;
}

/** Python `f"{value:,}"` for floats already rounded to 2 decimals, e.g. 23264.1 -> "23,264.1". */
export function formatPlain(value: number): string {
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(value);
}

/** Python `change_pill`: "↗ 15.83%" / "↘ 4.93%" / "0.00%", "—" when missing. */
export function formatChange(
  value: number | null | undefined,
  decimals = 2,
): { text: string; direction: Direction } {
  if (value == null || Number.isNaN(value)) return { text: "—", direction: "flat" };
  const direction: Direction = value > 0 ? "up" : value < 0 ? "down" : "flat";
  const icon = direction === "up" ? "↗ " : direction === "down" ? "↘ " : "";
  return { text: `${icon}${pyFixed(Math.abs(value), decimals)}%`, direction };
}

const HEADLINE_MAX = 120;

/** One short line for a failed update step: the error's last non-empty line (where Python puts the message). */
export function errorHeadline(errorTail: string | undefined): string {
  const last = (errorTail ?? "").split(/\r?\n/).map((l) => l.trim()).filter(Boolean).pop();
  if (!last) return "no error message";
  return last.length > HEADLINE_MAX ? `${last.slice(0, HEADLINE_MAX - 1)}…` : last;
}

/** Python `freshness_label`. */
export function freshnessLabel(ageDays: number | null): string {
  if (ageDays == null) return "no saved file";
  if (ageDays === 0) return "updated today";
  return ageDays === 1 ? "1 day old" : `${ageDays} days old`;
}

/** Python `freshness_tone`. */
export function freshnessTone(ageDays: number | null): Tone {
  if (ageDays == null) return "muted";
  if (ageDays <= FRESH_MAX_DAYS) return "gain";
  if (ageDays <= AGING_MAX_DAYS) return "warn";
  return "loss";
}

/** Python `f"{value:+.{decimals}f}"`, e.g. 20.94 -> "+20.9", -4.93 -> "-4.93" (no `%`). */
export function formatSigned(value: number, decimals: number): string {
  const text = pyFixed(value, decimals);
  return text.startsWith("-") ? text : `+${text}`;
}

/** Python `f"₹{value:,.{decimals}f}"`, e.g. 1087.75 -> "₹1,087.75". */
export function formatRupees(value: number, decimals: number): string {
  return `₹${formatNumber(value, decimals)}`;
}

/** Python `big_value` split: text before the first "." is large, the rest ("." included) is small. */
export function bigValueParts(text: string): { head: string; dec: string | null } {
  const at = text.indexOf(".");
  return at < 0 ? { head: text, dec: null } : { head: text.slice(0, at), dec: text.slice(at) };
}
