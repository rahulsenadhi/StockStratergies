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

export function TradesTable({ columns, rows }: TradesData) {
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
          <TableRow key={hg.id}>
            {hg.headers.map((h) => (
              <TableHead
                key={h.id}
                onClick={h.column.getToggleSortingHandler()}
                className={h.column.getCanSort() ? "cursor-pointer select-none" : ""}
              >
                {flexRender(h.column.columnDef.header, h.getContext())}
                {({ asc: " ↑", desc: " ↓" } as Record<string, string>)[
                  h.column.getIsSorted() as string
                ] ?? ""}
              </TableHead>
            ))}
          </TableRow>
        ))}
      </TableHeader>
      <TableBody>
        {table.getRowModel().rows.map((r) => (
          <TableRow key={r.id}>
            {r.getVisibleCells().map((cell) => (
              <TableCell key={cell.id}>
                {flexRender(cell.column.columnDef.cell, cell.getContext())}
              </TableCell>
            ))}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
