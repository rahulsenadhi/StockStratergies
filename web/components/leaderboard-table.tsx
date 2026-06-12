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
import { ChevronUp, ChevronDown, ChevronsUpDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { upDown } from "@/lib/dir";
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
import { pct, signed } from "@/lib/format";
import type { Strategy } from "@/lib/data/strategies";

export type Row = Strategy & { series: number[] };

/** Inline KPI cell — mono tabular-nums, right-aligned, up/down color where applicable */
function NumCell({
  value,
  kind = "pct",
  colored = false,
}: {
  value: number | null;
  kind?: "pct" | "num";
  colored?: boolean;
}) {
  if (value == null) return <span className="text-muted-foreground">—</span>;
  const formatted = kind === "pct" ? pct(value) : signed(value);
  return (
    <span className={cn("font-mono tabular-nums", colored && upDown(value))}>
      {formatted}
    </span>
  );
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

const columns: ColumnDef<Row>[] = [
  {
    accessorKey: "rank",
    header: "#",
    cell: (c) => {
      const rank = c.getValue<number | null>() ?? null;
      const isFirst = rank === 1;
      return (
        <span
          className={cn(
            "inline-flex h-5 min-w-5 items-center justify-center rounded px-1 text-xs font-medium tabular-nums",
            isFirst
              ? "bg-accent-blue/15 text-accent-blue"
              : "bg-muted text-foreground",
          )}
        >
          {rank ?? "—"}
        </span>
      );
    },
  },
  {
    accessorKey: "name",
    header: "Strategy",
    cell: (c) => (
      <Link
        href={`/strategy/${c.row.original.id}`}
        className="block text-accent-blue hover:underline font-medium"
      >
        {c.row.original.name}
        <span className="block text-xs font-normal text-muted-foreground">
          {c.row.original.type} · {c.row.original.status}
        </span>
      </Link>
    ),
  },
  {
    id: "cagr",
    accessorFn: (r) => r.kpis.cagr ?? -Infinity,
    header: () => <Term k="CAGR">CAGR</Term>,
    cell: (c) => (
      <NumCell value={c.row.original.kpis.cagr} kind="pct" colored />
    ),
  },
  {
    id: "sharpe",
    accessorFn: (r) => r.kpis.sharpe ?? -Infinity,
    header: () => <Term k="Sharpe">Sharpe</Term>,
    cell: (c) => <NumCell value={c.row.original.kpis.sharpe} kind="num" />,
  },
  {
    id: "maxDd",
    accessorFn: (r) => r.kpis.maxDd ?? -Infinity,
    header: () => <Term k="Drawdown">Max DD</Term>,
    cell: (c) => <NumCell value={c.row.original.kpis.maxDd} kind="pct" />,
  },
  {
    id: "winRate",
    accessorFn: (r) => r.kpis.winRate ?? -Infinity,
    header: () => <Term k="Win_Rate">Win</Term>,
    cell: (c) => <NumCell value={c.row.original.kpis.winRate} kind="pct" />,
  },
  {
    id: "alpha",
    accessorFn: (r) => r.kpis.alpha ?? -Infinity,
    header: "Alpha",
    cell: (c) => (
      <NumCell value={c.row.original.kpis.alpha} kind="pct" colored />
    ),
  },
  {
    id: "rankScore",
    accessorFn: (r) => r.rankScore ?? -Infinity,
    header: "Score",
    cell: (c) => <NumCell value={c.row.original.rankScore} kind="num" />,
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
          <TableRow
            key={hg.id}
            className="sticky top-0 z-10 bg-background"
          >
            {hg.headers.map((h) => (
              <TableHead
                key={h.id}
                onClick={h.column.getToggleSortingHandler()}
                className={cn(
                  "px-3 py-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground",
                  h.column.getCanSort() && "cursor-pointer select-none",
                )}
              >
                <span className="inline-flex items-center gap-0.5">
                  {flexRender(h.column.columnDef.header, h.getContext())}
                  {h.column.getCanSort() && (
                    <SortIcon
                      sorted={h.column.getIsSorted() as false | "asc" | "desc"}
                    />
                  )}
                </span>
              </TableHead>
            ))}
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
                  // right-align numeric columns
                  ["cagr", "sharpe", "maxDd", "winRate", "alpha", "rankScore"].includes(
                    cell.column.id,
                  ) && "text-right",
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
