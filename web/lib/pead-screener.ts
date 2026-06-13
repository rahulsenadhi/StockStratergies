/** PEAD screener filtering + CSV export. Faithful port of
 *  pead_dashboard.py:_tab_screener (~L177): SUE >= min, Piotroski >= min,
 *  P/B <= max, optional sector multiselect. Null SUE/Piotroski/P-B rows are
 *  excluded (pandas NaN comparisons are False — same effect). */
import type { PeadScreenerRow } from "@/lib/data/strategies";

export interface ScreenerFilters {
  sueMin: number;
  pioMin: number;
  pbMax: number;
  sectors: string[];
}

export function filterScreener(
  rows: PeadScreenerRow[],
  { sueMin, pioMin, pbMax, sectors }: ScreenerFilters,
): PeadScreenerRow[] {
  const sectorSet = sectors.length ? new Set(sectors) : null;
  return rows.filter((r) => {
    if (r.sue == null || r.sue < sueMin) return false;
    if (r.piotroski == null || r.piotroski < pioMin) return false;
    if (r.pb == null || r.pb > pbMax) return false;
    if (sectorSet && (r.sector == null || !sectorSet.has(r.sector))) return false;
    return true;
  });
}

/** Distinct, sorted sector list for the multiselect. */
export function sectorsOf(rows: PeadScreenerRow[]): string[] {
  return [...new Set(rows.map((r) => r.sector).filter((s): s is string => !!s))].sort();
}

const CSV_COLS: (keyof PeadScreenerRow)[] = [
  "ticker",
  "sector",
  "resultDate",
  "periodType",
  "sue",
  "sueDecile",
  "epsActual",
  "epsExpected",
  "piotroski",
  "pb",
  "pbSectorMedian",
  "qualifiesLong",
];

const csvCell = (v: unknown): string => {
  if (v == null) return "";
  const s = String(v);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
};

export function toCsv(rows: PeadScreenerRow[]): string {
  const header = CSV_COLS.join(",");
  const body = rows.map((r) => CSV_COLS.map((c) => csvCell(r[c])).join(",")).join("\n");
  return `${header}\n${body}`;
}
