"use client";

import { useMemo, useState, type KeyboardEvent } from "react";
import { ArrowUpRight } from "lucide-react";
import { nextSort, previewRows, PREVIEW_ROWS, sortRows, type DeskColumn, type SortSpec } from "@/lib/desk/table";

interface DeskTableProps<R> {
  rows: readonly R[];
  columns: readonly DeskColumn<R>[];
  getRowId: (row: R) => string;
  caption: string;
  selectedId?: string | null;
  onRowClick?: (row: R) => void;
  empty?: string;
  previewLimit?: number;
  /** Start with every row shown (e.g. a deep-linked selection sits beyond the preview). */
  defaultExpanded?: boolean;
}

const cellClass = (kind: DeskColumn<unknown>["kind"], priority: number, sorted: boolean, head: boolean) =>
  [
    head ? "rd-th" : "rd-td",
    kind === "num" ? (head ? "rd-th--num" : "rd-td--num") : "",
    kind === "name" && !head ? "rd-td--name" : "",
    kind === "text" && !head ? "rd-td--text" : "",
    priority > 1 ? `rd-col--p${priority}` : "",
    sorted ? "rd-col--sorted" : "",
  ].filter(Boolean).join(" ");

/** Research table (Streamlit data_table in the v2 look) with sort, preview and column priorities. */
export function DeskTable<R>({
  rows, columns, getRowId, caption, selectedId, onRowClick, empty = "No rows", previewLimit = PREVIEW_ROWS,
  defaultExpanded = false,
}: DeskTableProps<R>) {
  const [sort, setSort] = useState<SortSpec>(null);
  const [expanded, setExpanded] = useState(defaultExpanded);

  const sorted = useMemo(() => {
    if (!sort) return [...rows];
    const col = columns.find((c) => c.key === sort.key);
    return col?.sortValue ? sortRows(rows, col.sortValue, sort.dir) : [...rows];
  }, [rows, columns, sort]);
  const shown = previewRows(sorted, expanded, previewLimit);

  const onKey = (e: KeyboardEvent<HTMLTableRowElement>, row: R) => {
    if (onRowClick && (e.key === "Enter" || e.key === " ")) {
      e.preventDefault();
      onRowClick(row);
    }
  };

  return (
    <div className="rd-table-wrap">
      <table className="rd-table">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr>
            {columns.map((c) => {
              const isSorted = sort?.key === c.key;
              const aria = isSorted ? (sort!.dir === "asc" ? "ascending" : "descending") : "none";
              return (
                <th key={c.key} scope="col" aria-sort={aria} className={cellClass(c.kind, c.priority, isSorted, true)}>
                  {c.sortValue ? (
                    <button type="button" className="rd-th__btn" onClick={() => setSort((s) => nextSort(s, c.key))}>
                      {c.label}
                      {isSorted ? <span aria-hidden="true">{sort!.dir === "asc" ? "▲" : "▼"}</span> : null}
                    </button>
                  ) : (
                    c.label
                  )}
                </th>
              );
            })}
          </tr>
        </thead>
        {shown.length > 0 ? (
          <tbody>
            {shown.map((row) => {
              const id = getRowId(row);
              const cls = onRowClick ? `rd-tr${id === selectedId ? " rd-tr--sel" : ""}` : "rd-tr--static";
              return (
                <tr
                  key={id}
                  className={cls}
                  tabIndex={onRowClick ? 0 : undefined}
                  onClick={onRowClick ? () => onRowClick(row) : undefined}
                  onKeyDown={onRowClick ? (e) => onKey(e, row) : undefined}
                  aria-selected={onRowClick ? id === selectedId : undefined}
                >
                  {columns.map((c) => (
                    <td key={c.key} className={cellClass(c.kind, c.priority, sort?.key === c.key, false)}>
                      {c.render(row)}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        ) : null}
      </table>
      {shown.length === 0 ? <div className="rd-table__empty">{empty}</div> : null}
      {rows.length > previewLimit ? (
        <button type="button" className="rd-table__more" onClick={() => setExpanded((v) => !v)}>
          {expanded ? `Show first ${previewLimit} rows` : `Show all ${rows.length.toLocaleString("en-US")} rows`}
        </button>
      ) : null}
    </div>
  );
}

/** Two-line company/strategy name cell (Python _cell_html kind="name"). */
export function NameCell({ title, sub, external = false }: { title: string; sub?: string; external?: boolean }) {
  return (
    <span className="rd-name" title={external ? "Not moved yet — opens the old Streamlit app" : undefined}>
      <span className="rd-name__title">
        {title}
        {external ? (
          <>
            <ArrowUpRight className="desk-ext" aria-hidden="true" />
            <span className="sr-only"> (opens old app)</span>
          </>
        ) : null}
      </span>
      {sub ? <span className="rd-name__sub">{sub}</span> : null}
    </span>
  );
}
