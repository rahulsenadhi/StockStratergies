"use client";

import { useMemo, useState } from "react";
import { DeskTable, NameCell } from "@/components/desk/desk-table";
import { StatusPill } from "@/components/desk/primitives";
import { Segmented } from "@/components/desk/segmented";
import {
  TRADE_PERIODS, TRADES_LEGEND, tradeCells, tradesCaption, visibleTrades,
  type TradePeriod, type TradeRow, type UiMomentum, type ViewKey,
} from "@/lib/desk/momentum-text";
import type { DeskColumn } from "@/lib/desk/table";

const cells = tradeCells;

const COLUMNS: DeskColumn<TradeRow>[] = [
  { key: "stock", label: "Stock", kind: "name", priority: 1, sortValue: (r) => r.symbol,
    render: (r) => <NameCell title={r.symbol} sub={cells(r).entryType} /> },
  { key: "bought", label: "Bought", kind: "text", priority: 1, sortValue: (r) => r.entry_date, render: (r) => cells(r).entryDate },
  { key: "at", label: "At", kind: "num", priority: 2, sortValue: (r) => r.entry_price, render: (r) => cells(r).entryPrice },
  { key: "prior", label: "Prior 52W high", kind: "num", priority: 3, sortValue: (r) => r.prior_high, render: (r) => cells(r).priorHigh },
  { key: "margin", label: "BK margin", kind: "num", priority: 3, sortValue: (r) => r.bk_margin, render: (r) => cells(r).bkMargin },
  { key: "sold", label: "Sold", kind: "text", priority: 1, sortValue: (r) => r.exit_date, render: (r) => cells(r).exitDate },
  { key: "sat", label: "At", kind: "num", priority: 2, sortValue: (r) => r.exit_price, render: (r) => cells(r).exitPrice },
  { key: "result", label: "Result", kind: "pill", priority: 1, sortValue: (r) => r.pnl,
    render: (r) => <StatusPill label={cells(r).pnl} tone={r.pnl == null ? "muted" : r.pnl >= 0 ? "gain" : "loss"} /> },
  { key: "held", label: "Held", kind: "num", priority: 2, sortValue: (r) => r.hold_days, render: (r) => `${cells(r).held}${r.hold_days == null ? "" : "d"}` },
  { key: "why", label: "Why sold", kind: "text", priority: 1, sortValue: (r) => r.exit_reason, render: (r) => cells(r).exitReason },
  { key: "filters", label: "Filters", kind: "text", priority: 3, sortValue: (r) => r.filters, render: (r) => cells(r).filters },
  { key: "recovery", label: "Recovery", kind: "text", priority: 3, sortValue: (r) => r.recovery, render: (r) => cells(r).recovery },
];

/** Past trades for the chosen switch view: period, year and clean-signals filters, then the table. */
export function PastTrades({ data, view }: { data: UiMomentum; view: ViewKey }) {
  const [period, setPeriod] = useState<TradePeriod>("All");
  const years = data.trade_filters.years;
  const [year, setYear] = useState<number | null>(years[0] ?? null);
  const [strict, setStrict] = useState(false);
  const [allCols, setAllCols] = useState(false);

  const { rows, hidden } = useMemo(() => visibleTrades(data, view, period, year, strict), [data, view, period, year, strict]);
  const total = data.views[view].trade_ids.length;
  const exits = rows.map((r) => r.exit_date).filter((d): d is string => d != null).sort();
  const caption = tradesCaption(rows.length, total, exits[0] ?? null, exits[exits.length - 1] ?? null, strict, hidden);

  return (
    <div className="desk-stack" style={{ gap: 8 }}>
      <div className="desk-row">
        <div className="desk-row" style={{ justifyContent: "flex-start" }}>
          <Segmented options={TRADE_PERIODS} value={period} onChange={setPeriod} ariaLabel="Past trades period" />
          {period === "Pick year" ? (
            <select className="desk-select" aria-label="Year" value={year ?? ""} onChange={(e) => setYear(Number(e.target.value))}>
              {years.map((y) => <option key={y} value={y}>{y}</option>)}
            </select>
          ) : null}
          <label className="desk-toggle">
            <input type="checkbox" checked={strict} onChange={(e) => setStrict(e.target.checked)} /> Clean signals only
          </label>
          <label className="desk-toggle">
            <input type="checkbox" checked={allCols} onChange={(e) => setAllCols(e.target.checked)} /> All columns
          </label>
        </div>
        <span className="rd-note">Newest exit first</span>
      </div>
      <p className="rd-note" style={{ margin: 0 }}>{caption}</p>
      <div className={allCols ? undefined : "desk-compact"}>
        <DeskTable rows={rows} columns={COLUMNS} getRowId={(r) => String(r.id)} caption="Closed model trades, newest exit first"
          empty="No trades in this window" />
      </div>
      <p className="rd-note" style={{ margin: 0 }}>{TRADES_LEGEND}</p>
    </div>
  );
}
