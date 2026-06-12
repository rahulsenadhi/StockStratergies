"use client";

import { useMemo, useState } from "react";
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  flexRender,
  type ColumnDef,
  type SortingState,
} from "@tanstack/react-table";
import { ChevronUp, ChevronDown, ChevronsUpDown } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import type { TradesData } from "@/lib/data/strategies";

type TradeRow = Record<string, string>;

export function compareCells(a: string, b: string): number {
  const na = Number(a);
  const nb = Number(b);
  if (Number.isFinite(na) && Number.isFinite(nb)) return na - nb;
  return a.localeCompare(b);
}

function isEmptyCell(v: string | undefined): boolean {
  const t = (v ?? "").trim();
  return t === "" || t === "—";
}

/** A cell is numeric when its non-empty value parses as a finite number. */
function isNumericCell(v: string | undefined): boolean {
  return !isEmptyCell(v) && Number.isFinite(Number((v ?? "").trim()));
}

/** Sort caret icon for header cells */
function SortIcon({ sorted }: { sorted: false | "asc" | "desc" }) {
  if (sorted === "asc")
    return <ChevronUp size={14} className="inline-block ml-0.5 shrink-0" />;
  if (sorted === "desc")
    return <ChevronDown size={14} className="inline-block ml-0.5 shrink-0" />;
  return (
    <ChevronsUpDown
      size={14}
      className="inline-block ml-0.5 shrink-0 text-muted-foreground/50"
    />
  );
}

export function TradesTable({ columns, rows }: TradesData) {
  // A column is numeric when the first non-empty value in it parses as a number.
  const numericColumns = useMemo<Set<string>>(() => {
    const set = new Set<string>();
    for (const col of columns) {
      const sample = rows.find((row) => !isEmptyCell(row[col]));
      if (sample && isNumericCell(sample[col])) set.add(col);
    }
    return set;
  }, [columns, rows]);

  const columnDefs = useMemo<ColumnDef<TradeRow>[]>(
    () =>
      columns.map((col) => ({
        id: col,
        header: col,
        accessorFn: (row) => (isEmptyCell(row[col]) ? undefined : row[col]),
        sortUndefined: "last",
        sortingFn: (rowA, rowB, columnId) =>
          compareCells(
            rowA.getValue<string>(columnId),
            rowB.getValue<string>(columnId),
          ),
        cell: (c) => {
          const v = c.row.original[col];
          return isEmptyCell(v) ? "—" : v;
        },
      })),
    [columns],
  );

  const [sorting, setSorting] = useState<SortingState>([]);

  const table = useReactTable({
    data: rows,
    columns: columnDefs,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  if (!columns.length || !rows.length) {
    return <p className="text-sm text-muted-foreground">No trades for this strategy.</p>;
  }

  return (
    <Table>
      <TableHeader>
        {table.getHeaderGroups().map((hg) => (
          <TableRow key={hg.id} className="sticky top-0 z-10 bg-background">
            {hg.headers.map((h) => {
              const numeric = numericColumns.has(h.column.id);
              return (
                <TableHead
                  key={h.id}
                  onClick={h.column.getToggleSortingHandler()}
                  className={cn(
                    "px-3 py-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground",
                    numeric && "text-right",
                    h.column.getCanSort() && "cursor-pointer select-none",
                  )}
                >
                  <span
                    className={cn(
                      "inline-flex items-center gap-0.5",
                      numeric && "justify-end",
                    )}
                  >
                    {flexRender(h.column.columnDef.header, h.getContext())}
                    {h.column.getCanSort() && (
                      <SortIcon
                        sorted={h.column.getIsSorted() as false | "asc" | "desc"}
                      />
                    )}
                  </span>
                </TableHead>
              );
            })}
          </TableRow>
        ))}
      </TableHeader>
      <TableBody>
        {table.getRowModel().rows.map((r, i) => (
          <TableRow
            key={r.id}
            className={cn(
              "border-b border-border hover:bg-muted/40 transition-colors",
              i % 2 !== 0 && "bg-muted/10",
            )}
          >
            {r.getVisibleCells().map((cell) => (
              <TableCell
                key={cell.id}
                className={cn(
                  "px-3 py-1.5",
                  numericColumns.has(cell.column.id) &&
                    "font-mono tabular-nums text-right",
                )}
              >
                {flexRender(cell.column.columnDef.cell, cell.getContext())}
              </TableCell>
            ))}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
