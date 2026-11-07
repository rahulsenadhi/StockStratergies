import type { ReactNode } from "react";

export type SortDir = "asc" | "desc";
export type SortSpec = { key: string; dir: SortDir } | null;
export type SortValue = number | string | null | undefined;

/** Long tables show this many rows plus a "Show all N rows" toggle (never an inner scroll box). */
export const PREVIEW_ROWS = 15;

export interface DeskColumn<R> {
  key: string;
  label: string;
  /** name = two-line company cell; num = right-aligned figure or change pill. */
  kind: "name" | "num" | "text" | "pill";
  /** 1 always shows; 2 hides below 640px; 3 hides below 1024px. */
  priority: 1 | 2 | 3;
  sortValue?: (row: R) => SortValue;
  render: (row: R) => ReactNode;
}

const isBlank = (v: SortValue): v is null | undefined =>
  v === null || v === undefined || (typeof v === "number" && Number.isNaN(v));

/** Stable sort; blanks always last; numbers numeric, strings by localeCompare. Returns a new array. */
export function sortRows<R>(rows: readonly R[], value: (row: R) => SortValue, dir: SortDir): R[] {
  const sign = dir === "asc" ? 1 : -1;
  return rows
    .map((row, i) => ({ row, i, v: value(row) }))
    .sort((a, b) => {
      const ab = isBlank(a.v), bb = isBlank(b.v);
      if (ab || bb) return ab === bb ? a.i - b.i : ab ? 1 : -1;
      const cmp = typeof a.v === "number" && typeof b.v === "number"
        ? a.v - b.v
        : String(a.v).localeCompare(String(b.v));
      return cmp === 0 ? a.i - b.i : sign * cmp;
    })
    .map((x) => x.row);
}

export function previewRows<R>(rows: readonly R[], expanded: boolean, limit: number = PREVIEW_ROWS): R[] {
  return expanded ? [...rows] : rows.slice(0, limit);
}

/** Header click: a new column starts descending (biggest first), the same column flips. */
export function nextSort(current: SortSpec, key: string): Exclude<SortSpec, null> {
  if (current && current.key === key) return { key, dir: current.dir === "desc" ? "asc" : "desc" };
  return { key, dir: "desc" };
}
