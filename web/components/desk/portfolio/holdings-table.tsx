"use client";
import { DeskTable } from "@/components/desk/desk-table";
import { StatusPill } from "@/components/desk/primitives";
import { actionTone, count, drawdown, held, money, percent, ruleText, type PortfolioPosition } from "@/lib/desk/portfolio-text";
import type { DeskColumn } from "@/lib/desk/table";

const columns: DeskColumn<PortfolioPosition>[] = [
  { key: "name", label: "Company / symbol", kind: "name", priority: 1, sortValue: (p) => p.name,
    render: (p) => <span className="rd-name"><span className="rd-name__title">{p.name}</span><span className="rd-name__sub">{p.symbol} · {p.exchange}</span></span> },
  { key: "qty", label: "Qty", kind: "num", priority: 2, sortValue: (p) => p.open_qty, render: (p) => count(p.open_qty) },
  { key: "avg", label: "Avg price", kind: "num", priority: 3, sortValue: (p) => p.avg_price, render: (p) => money(p.avg_price) },
  { key: "close", label: "Last close", kind: "num", priority: 2, sortValue: (p) => p.evaluation.last_close,
    render: (p) => <>{money(p.evaluation.last_close)}<span className="rd-name__sub">{p.evaluation.last_bar_date ?? "Unavailable"}</span></> },
  { key: "pnl", label: "Unrealised P&L", kind: "num", priority: 2, sortValue: (p) => p.unrealised_pnl,
    render: (p) => <>{money(p.unrealised_pnl)}<span className="rd-name__sub">{percent(p.unrealised_pnl_pct)}</span></> },
  { key: "realised", label: "Realised P&L", kind: "num", priority: 3, sortValue: (p) => p.realised_pnl, render: (p) => money(p.realised_pnl) },
  { key: "held", label: "Held", kind: "text", priority: 3, sortValue: (p) => p.evaluation.held_days, render: held },
  { key: "drawdown", label: "Drawdown", kind: "num", priority: 3, sortValue: (p) => p.evaluation.drawdown_from_peak, render: drawdown },
  { key: "action", label: "Action", kind: "pill", priority: 1, sortValue: (p) => p.evaluation.action, render: (p) => <StatusPill label={p.evaluation.action} tone={actionTone(p.evaluation.action)} /> },
  { key: "rule", label: "Rule", kind: "text", priority: 3, render: (p) => ruleText(p.evaluation) },
];
export function HoldingsTable({ positions, selected, onSelect }: { positions: PortfolioPosition[]; selected: string | null; onSelect: (p: PortfolioPosition) => void }) {
  return <div className="portfolio-holdings"><DeskTable rows={positions} columns={columns} getRowId={(p) => p.symbol} caption="Open holdings" selectedId={selected} onRowClick={onSelect} empty="No open holdings recorded." /></div>;
}
export function ClosedPositions({ positions, selected, onSelect }: { positions: PortfolioPosition[]; selected: string | null; onSelect: (p: PortfolioPosition) => void }) {
  const closedColumns: DeskColumn<PortfolioPosition>[] = [columns[0], columns[5], { key: "charges", label: "Charge basis", kind: "text", priority: 2,
    render: (p) => p.charges_known ? "Net of recorded charges" : "Excludes unrecorded buy charges" }];
  return <DeskTable rows={positions} columns={closedColumns} getRowId={(p) => p.symbol} caption="Closed positions" selectedId={selected} onRowClick={onSelect} empty="No closed positions yet." />;
}
