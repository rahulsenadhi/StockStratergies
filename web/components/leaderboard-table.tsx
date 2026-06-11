"use client";

import { useState } from "react";
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  flexRender,
  type ColumnDef,
  type SortingState,
} from "@tanstack/react-table";
import { Term } from "@/components/ui/term";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import Link from "next/link";
import { Sparkline } from "@/components/sparkline";
import { KpiCell } from "@/components/kpi-cell";
import type { Strategy } from "@/lib/data/strategies";

export type Row = Strategy & { series: number[] };

const columns: ColumnDef<Row>[] = [
  {
    accessorKey: "rank",
    header: "#",
    cell: (c) => (
      <span className="font-bold text-green-500">
        {c.getValue<number | null>() ?? "—"}
      </span>
    ),
  },
  {
    accessorKey: "name",
    header: "Strategy",
    cell: (c) => (
      <Link href={`/strategy/${c.row.original.id}`} className="block hover:underline">
        <div className="font-medium">{c.row.original.name}</div>
        <div className="text-xs text-muted-foreground">
          {c.row.original.type} · {c.row.original.status}
        </div>
      </Link>
    ),
  },
  {
    id: "cagr",
    accessorFn: (r) => r.kpis.cagr ?? -Infinity,
    header: () => <Term k="CAGR">CAGR</Term>,
    cell: (c) => <KpiCell value={c.row.original.kpis.cagr} />,
  },
  {
    id: "sharpe",
    accessorFn: (r) => r.kpis.sharpe ?? -Infinity,
    header: () => <Term k="Sharpe">Sharpe</Term>,
    cell: (c) => <KpiCell value={c.row.original.kpis.sharpe} kind="num" />,
  },
  {
    id: "maxDd",
    accessorFn: (r) => r.kpis.maxDd ?? -Infinity,
    header: () => <Term k="Drawdown">Max DD</Term>,
    cell: (c) => <KpiCell value={c.row.original.kpis.maxDd} />,
  },
  {
    id: "winRate",
    accessorFn: (r) => r.kpis.winRate ?? -Infinity,
    header: () => <Term k="Win_Rate">Win</Term>,
    cell: (c) => <KpiCell value={c.row.original.kpis.winRate} />,
  },
  {
    id: "alpha",
    accessorFn: (r) => r.kpis.alpha ?? -Infinity,
    header: "Alpha",
    cell: (c) => <KpiCell value={c.row.original.kpis.alpha} />,
  },
  {
    id: "rankScore",
    accessorFn: (r) => r.rankScore ?? -Infinity,
    header: "Score",
    cell: (c) => <KpiCell value={c.row.original.rankScore} kind="num" />,
  },
  {
    id: "trend",
    header: "Trend",
    enableSorting: false,
    cell: (c) => <Sparkline points={c.row.original.series} />,
  },
];

export function LeaderboardTable({ rows }: { rows: Row[] }) {
  const [sorting, setSorting] = useState<SortingState>([
    { id: "rank", desc: false },
  ]);

  const table = useReactTable({
    data: rows,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  if (!rows.length) {
    return (
      <p className="text-muted-foreground">
        No strategies — run a backtest.
      </p>
    );
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
                className={
                  h.column.getCanSort() ? "cursor-pointer select-none" : ""
                }
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
