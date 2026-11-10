"use client";

import { useMemo, useRef, useState } from "react";
import { DeskTable, NameCell } from "@/components/desk/desk-table";
import { ChangePill, EmptyState, SectionHead, StatusPill } from "@/components/desk/primitives";
import { Tabs } from "@/components/desk/tabs";
import { IndicatorChart } from "@/components/desk/momentum/indicator-chart";
import { signalTone, StockRail, type RailStock } from "@/components/desk/momentum/stock-rail";
import {
  EMPTY_NO_SIGNALS, HIST_NOTE, RAIL_PLACEHOLDER, countsLine, exchangeOf, RECENT_NOTE, SETUPS_META, SETUPS_TITLE, recentCells, signalCells, tabLabels, tabRows,
  type RecentRow, type SetupTab, type SignalRow, type UiMomentum, type ViewKey,
} from "@/lib/desk/momentum-text";
import type { DeskColumn } from "@/lib/desk/table";

/** Below this width the rail stacks under the table, so a row tap scrolls the rail into view. */
const STACKED_MAX_WIDTH = 1200;
const CHART_TITLE = "Price chart and indicators";

const sub = (r: SignalRow) => (r.company === r.symbol ? exchangeOf(r.symbol) : `${r.symbol} · ${exchangeOf(r.symbol)}`);
const cells = signalCells;

const COMPACT: DeskColumn<SignalRow>[] = [
  { key: "company", label: "Company", kind: "name", priority: 1, sortValue: (r) => r.company,
    render: (r) => <NameCell title={r.company} sub={sub(r)} /> },
  { key: "signal", label: "Signal", kind: "pill", priority: 1, sortValue: (r) => r.signal,
    render: (r) => <StatusPill label={r.signal} tone={signalTone(r.signal)} /> },
  { key: "price", label: "Price", kind: "num", priority: 2, sortValue: (r) => r.close, render: (r) => cells(r).close },
  { key: "from", label: "From high", kind: "num", priority: 1, sortValue: (r) => r.dist_ath,
    render: (r) => <ChangePill value={r.dist_ath} decimals={1} /> },
  { key: "stop", label: "Stop", kind: "num", priority: 2, sortValue: (r) => r.stop_pct, render: (r) => cells(r).stopPct },
  { key: "breaks", label: "Breaks", kind: "text", priority: 3, sortValue: (r) => r.entry_type, render: (r) => <span style={{ whiteSpace: "nowrap" }}>{cells(r).entryType}</span> },
  { key: "vol", label: "Volume", kind: "num", priority: 3, sortValue: (r) => r.vol_ratio, render: (r) => cells(r).volRatio },
  { key: "score", label: "Score", kind: "num", priority: 1, sortValue: (r) => r.score, render: (r) => cells(r).score },
];

const EXTRA: DeskColumn<SignalRow>[] = [
  { key: "action", label: "Action", kind: "text", priority: 2, sortValue: (r) => r.action, render: (r) => r.action },
  { key: "ath", label: "ATH (₹)", kind: "num", priority: 2, sortValue: (r) => r.ath, render: (r) => cells(r).ath },
  { key: "qual", label: "Chart quality", kind: "text", priority: 3, sortValue: (r) => r.chart_qual, render: (r) => cells(r).chartQual },
  { key: "chop", label: "Choppiness", kind: "num", priority: 3, sortValue: (r) => r.choppiness, render: (r) => cells(r).choppiness },
  { key: "recovery", label: "Recovery", kind: "text", priority: 3, sortValue: (r) => r.recovery, render: (r) => cells(r).recovery },
  { key: "ema", label: "220 EMA", kind: "num", priority: 3, sortValue: (r) => r.ema220, render: (r) => cells(r).ema220 },
  { key: "h52", label: "52W High", kind: "num", priority: 3, sortValue: (r) => r.high52, render: (r) => cells(r).high52 },
  { key: "vsh", label: "vs High%", kind: "num", priority: 3, sortValue: (r) => r.vs_high, render: (r) => cells(r).vsHigh },
  { key: "stopr", label: "Stop (₹)", kind: "num", priority: 3, sortValue: (r) => r.stop_price, render: (r) => cells(r).stop },
  { key: "hw", label: "Hist Win%", kind: "num", priority: 3, sortValue: (r) => r.hist_win, render: (r) => cells(r).histWin },
  { key: "ha", label: "Hist Avg%", kind: "num", priority: 3, sortValue: (r) => r.hist_avg, render: (r) => cells(r).histAvg },
];

const RECENT_COLUMNS: DeskColumn<RecentRow>[] = [
  { key: "stock", label: "Stock", kind: "name", priority: 1, sortValue: (r) => r.symbol, render: (r) => <NameCell title={r.symbol} sub={exchangeOf(r.symbol)} /> },
  { key: "days", label: "Days ago", kind: "num", priority: 1, sortValue: (r) => r.days_ago, render: (r) => recentCells(r).daysAgo },
  { key: "bkd", label: "Breakout date", kind: "text", priority: 2, sortValue: (r) => r.bk_date, render: (r) => recentCells(r).bkDate },
  { key: "bkp", label: "Breakout price", kind: "num", priority: 2, sortValue: (r) => r.bk_price, render: (r) => recentCells(r).bkPrice },
  { key: "close", label: "Close", kind: "num", priority: 1, sortValue: (r) => r.close, render: (r) => recentCells(r).close },
  { key: "off", label: "% off breakout", kind: "num", priority: 1, sortValue: (r) => r.off_bk, render: (r) => recentCells(r).offBk },
  { key: "ema", label: "220 EMA", kind: "num", priority: 3, sortValue: (r) => r.ema220, render: (r) => recentCells(r).ema220 },
  { key: "vol", label: "Volume", kind: "num", priority: 3, sortValue: (r) => r.vol_ratio, render: (r) => recentCells(r).volRatio },
  { key: "stop", label: "Stop", kind: "num", priority: 2, sortValue: (r) => r.stop, render: (r) => recentCells(r).stop },
];

/** The stock the rail describes: its setup row if it has one, else its recent-breakout row. */
function railStock(data: UiMomentum, symbol: string): RailStock | null {
  const s = data.signals.find((r) => r.symbol === symbol);
  if (s) {
    const c = signalCells(s);
    return { symbol, company: s.company, price: c.close, pillLabel: s.signal, pillTone: signalTone(s.signal),
      stop: `${c.stop} (${c.stopPct})`, signal: s };
  }
  const r = data.recent.find((x) => x.symbol === symbol);
  if (!r) return null;
  const c = recentCells(r);
  return { symbol, company: symbol, price: c.close, pillLabel: "Broke out last 7 days", pillTone: "muted", stop: c.stop, signal: null };
}

interface SetupsDeskProps {
  data: UiMomentum;
  view: ViewKey;
  initial: { symbol: string | null; tab: SetupTab };
}

/** Today's setups: tabs, table and the stock rail; selection is kept in the address bar. */
export function SetupsDesk({ data, view, initial }: SetupsDeskProps) {
  const [tab, setTab] = useState<SetupTab>(initial.tab);
  const [selected, setSelected] = useState<string | null>(initial.symbol);
  const [allCols, setAllCols] = useState(false);
  const railRef = useRef<HTMLDivElement>(null);

  const select = (symbol: string) => {
    setSelected(symbol);
    window.history.replaceState(null, "", `?ticker=${encodeURIComponent(symbol)}`);
    if (window.innerWidth < STACKED_MAX_WIDTH) railRef.current?.scrollIntoView({ block: "start" });
  };

  const labels = tabLabels(data, view);
  // Highest score first; the sort is stable, so ties keep the saved order.
  const rows = useMemo(
    () => (tab === "Recent" ? [] : [...tabRows(data, view, tab)].sort((a, b) => (b.score ?? -Infinity) - (a.score ?? -Infinity))),
    [data, view, tab],
  );
  const columns = useMemo(() => (allCols ? [...COMPACT, ...EXTRA] : COMPACT), [allCols]);
  const stock = selected ? railStock(data, selected) : null;

  const onRow = (symbol: string) => select(symbol);
  let panel;
  if (tab === "Recent") {
    panel = (
      <div className="desk-stack" style={{ gap: 8 }}>
        <p className="rd-note" style={{ margin: 0 }}>{RECENT_NOTE}</p>
        <div className="desk-compact">
        <DeskTable rows={data.recent} columns={RECENT_COLUMNS} getRowId={(r) => r.symbol} selectedId={selected}
          onRowClick={(r) => onRow(r.symbol)} caption="Stocks that broke out in the last 7 days" empty="No recent breakouts" />
        </div>
      </div>
    );
  } else if (data.signals.length === 0) {
    panel = <EmptyState title={EMPTY_NO_SIGNALS.title} reason={EMPTY_NO_SIGNALS.reason} />;
  } else {
    panel = (
      <div className="desk-stack" style={{ gap: 8 }}>
        <div className={allCols ? undefined : "desk-compact"}>
        <DeskTable rows={rows} columns={columns} getRowId={(r) => r.symbol} selectedId={selected}
          onRowClick={(r) => onRow(r.symbol)} caption="Today's saved setups, highest score first"
          empty="No setups match this view and tab" />
        </div>
        <p className="rd-note" style={{ margin: 0 }}>{HIST_NOTE}</p>
      </div>
    );
  }

  return (
    <div className="desk-stack" style={{ gap: 24 }}>
    <div className="desk-split">
      <section className="desk-stack" style={{ gap: 8 }} aria-label={SETUPS_TITLE}>
        <SectionHead title={SETUPS_TITLE} meta={SETUPS_META}
          right={(
            <label className="desk-toggle">
              <input type="checkbox" checked={allCols} onChange={(e) => setAllCols(e.target.checked)} /> All columns
            </label>
          )} />
        <p className="rd-note" style={{ margin: 0 }}>{countsLine(data.views[view].counts)}</p>
        <Tabs value={tab} onChange={(id) => setTab(id as SetupTab)}
          tabs={labels.map((l) => ({ id: l.id, label: l.label, content: panel }))} />
      </section>
      <div className="desk-rail desk-stack" ref={railRef}>
        {stock ? (data.details[stock.symbol]
          ? <StockRail stock={stock} detail={data.details[stock.symbol]} colour={data.colour} />
          : <EmptyState title={`No saved details for ${stock.symbol}.`} />)
          : <EmptyState title={RAIL_PLACEHOLDER.title} reason={RAIL_PLACEHOLDER.reason} />}
      </div>
    </div>
    {selected && (
      <section className="desk-stack" style={{ gap: 8 }} aria-label={CHART_TITLE}>
        <SectionHead title={CHART_TITLE} meta={`${selected} · candles, averages, volume, RSI, MACD`} />
        <IndicatorChart symbol={selected} />
      </section>
    )}
    </div>
  );
}
