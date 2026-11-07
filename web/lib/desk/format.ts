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

const grouped = (decimals: number) =>
  new Intl.NumberFormat("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });

/** Python `f"{value:,.{decimals}f}"`, e.g. 25030.35 -> "25,030.35". */
export function formatNumber(value: number, decimals = 2): string {
  return grouped(decimals).format(value);
}

/** Python `change_pill`: "↗ 15.83%" / "↘ 4.93%" / "0.00%", "—" when missing. */
export function formatChange(
  value: number | null | undefined,
  decimals = 2,
): { text: string; direction: Direction } {
  if (value == null || Number.isNaN(value)) return { text: "—", direction: "flat" };
  const direction: Direction = value > 0 ? "up" : value < 0 ? "down" : "flat";
  const icon = direction === "up" ? "↗ " : direction === "down" ? "↘ " : "";
  return { text: `${icon}${Math.abs(value).toFixed(decimals)}%`, direction };
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
