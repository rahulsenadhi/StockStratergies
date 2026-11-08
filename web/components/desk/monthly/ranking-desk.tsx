"use client";

import { useMemo, useRef, useState, type ReactNode } from "react";
import { DeskTable, NameCell } from "@/components/desk/desk-table";
import { ChangePill, EmptyState, RailList, SectionHead, StatusPill } from "@/components/desk/primitives";
import { Segmented } from "@/components/desk/segmented";
import { useMonthlySelection } from "@/components/desk/monthly/selection";
import { PriceChart } from "@/components/desk/monthly/price-chart";
import {
  DETAIL_ROWS, EMPTY_NO_RANKING, MONTHLY_FILTERS, RANKING_META, RANKING_NOTE, RANKING_TITLE, TOP5_META, TOP5_TITLE,
  emptyNoPrices, exchangeLine, noMatchText, priceChartLabel, rankCells, rankLabelTone, rankStatus,
  type CloseSeries, type MonthlyFilter, type RankRow,
} from "@/lib/desk/monthly-text";
import { PREVIEW_ROWS, type DeskColumn } from "@/lib/desk/table";

/** Below this width the rail stacks under the table, so a row tap scrolls the rail into view. */
const STACKED_MAX_WIDTH = 1200;

const COLUMNS: DeskColumn<RankRow>[] = [
  { key: "rank", label: "#", kind: "num", priority: 1, sortValue: (r) => r.rank, render: (r) => rankCells(r).rank },
  { key: "company", label: "Company", kind: "name", priority: 1,
    render: (r) => { const c = rankCells(r); return <NameCell title={c.company} sub={c.sub} />; } },
  { key: "price", label: "Price", kind: "num", priority: 2, render: (r) => rankCells(r).price },
  { key: "move", label: "Month move", kind: "num", priority: 1, sortValue: (r) => r.month_ret,
    render: (r) => <ChangePill value={r.month_ret} /> },
  { key: "rs", label: "RS score", kind: "num", priority: 1, sortValue: (r) => r.rs, render: (r) => rankCells(r).rs },
  { key: "label", label: "Model label", kind: "pill", priority: 2,
    render: (r) => <StatusPill label={r.label} tone={rankLabelTone(r)} /> },
];

interface RankingDeskProps {
  ranking: RankRow[];
  filters: Record<MonthlyFilter, string[]>;
  initialSelected: string | null;
  closes: Record<string, CloseSeries>;
  top5: string[];
  colour: string;
}

/** Python _render_monthly_ranking + _render_monthly_detail: filter, ranking table and the detail rail. */
export function RankingDesk({ ranking, filters, initialSelected, closes, top5, colour }: RankingDeskProps) {
  const [pick, setPick] = useState<MonthlyFilter>("All 50");
  const [localSelected, setLocalSelected] = useState<string | null>(initialSelected);
  const shared = useMonthlySelection();
  const selected = shared ? shared.selected : localSelected;
  const railRef = useRef<HTMLDivElement>(null);
  // A deep-linked row (e.g. ?ticker=HAL, rank 42) beyond the 15-row preview opens the full list so it is visible.
  const [startExpanded] = useState(() => ranking.findIndex((r) => r.symbol === initialSelected) >= PREVIEW_ROWS);

  // Rows come from Python's saved filter lists; only the saved rank order is kept.
  const shown = useMemo(() => {
    const allowed = new Set(filters[pick] ?? []);
    return ranking.filter((r) => allowed.has(r.symbol));
  }, [ranking, filters, pick]);
  // The rail follows the selection in the full ranking, so a filter that hides the row keeps the rail on it.
  const row = ranking.find((r) => r.symbol === selected) ?? null;

  const select = (r: RankRow) => {
    if (shared) shared.select(r.symbol);
    else {
      setLocalSelected(r.symbol);
      window.history.replaceState(null, "", `?ticker=${encodeURIComponent(r.symbol)}`);
    }
    if (window.innerWidth < STACKED_MAX_WIDTH) railRef.current?.scrollIntoView({ block: "start" });
  };

  const head = (
    <SectionHead title={RANKING_TITLE} meta={RANKING_META}
      right={<Segmented options={MONTHLY_FILTERS} value={pick} onChange={setPick} ariaLabel="Show" />} />
  );
  if (ranking.length === 0) {
    return (
      <section className="desk-stack" style={{ gap: 8 }} aria-label={RANKING_TITLE}>
        {head}
        <EmptyState title={EMPTY_NO_RANKING.title} reason={EMPTY_NO_RANKING.reason} />
      </section>
    );
  }

  return (
    <div className="desk-split">
      <section className="desk-stack" style={{ gap: 8 }} aria-label={RANKING_TITLE}>
        {head}
        <DeskTable rows={shown} columns={COLUMNS} caption="Saved ranking of the Nifty 50 by RS score"
          getRowId={(r) => r.symbol} selectedId={selected} onRowClick={select} empty={noMatchText(pick)}
          defaultExpanded={startExpanded} />
        <p className="rd-note" style={{ margin: 0 }}>{RANKING_NOTE}</p>
      </section>
      <div className="desk-rail desk-stack" ref={railRef}>
        {row ? <DetailRail row={row} total={ranking.length} close={closes[row.symbol]} colour={colour} /> : null}
        <RailList title={TOP5_TITLE} meta={TOP5_META} items={top5Rows(ranking, top5)} />
      </div>
    </div>
  );
}

function top5Rows(ranking: RankRow[], top5: string[]) {
  return top5
    .map((sym) => ranking.find((r) => r.symbol === sym))
    .filter((r): r is RankRow => r !== undefined)
    .map((r) => ({ key: r.symbol, title: r.company, sub: `#${r.rank} · ${r.symbol}`, value: <ChangePill value={r.rs} /> }));
}

function DetailItem({ title, sub, children }: { title: string; sub: string; children: ReactNode }) {
  return (
    <div className="rd-li">
      <span className="rd-li__main">
        <span className="rd-li__title">{title}</span>
        {sub ? <span className="rd-li__sub">{sub}</span> : null}
      </span>
      {children}
    </div>
  );
}

interface DetailRailProps {
  row: RankRow;
  total: number;
  close: CloseSeries | undefined;
  colour: string;
}

function DetailRail({ row, total, close, colour }: DetailRailProps) {
  const status = rankStatus(row, total);
  const cells = rankCells(row);
  const noPrices = emptyNoPrices(row.ticker);
  return (
    <>
      <section className="rd-list" aria-label={`${row.company} detail`}>
        <div className="rd-list__head">
          <span className="desk-rail__title">{row.company}</span>
          <StatusPill label={status.label} tone={status.tone} />
        </div>
        <div className="rd-li"><span className="rd-li__sub">{exchangeLine(row.symbol)}</span></div>
        <DetailItem {...DETAIL_ROWS.price}><span className="rd-li__val">{cells.price}</span></DetailItem>
        <DetailItem {...DETAIL_ROWS.month}><ChangePill value={row.month_ret} /></DetailItem>
        <DetailItem {...DETAIL_ROWS.bench}><ChangePill value={row.bench_ret} /></DetailItem>
        <DetailItem {...DETAIL_ROWS.rs}><ChangePill value={row.rs} /></DetailItem>
        <DetailItem {...DETAIL_ROWS.label}><StatusPill label={row.label} tone="muted" /></DetailItem>
      </section>
      <div className="desk-card" style={{ padding: "10px 12px" }}>
        {close && close.points.length > 0 ? (
          <>
            <div className="rd-stat-label">{priceChartLabel(close.points.length, close.saved_to)}</div>
            <PriceChart key={row.symbol} points={close.points} colour={colour}
              label={priceChartLabel(close.points.length, close.saved_to)} />
          </>
        ) : (
          <EmptyState title={noPrices.title} reason={noPrices.reason} />
        )}
      </div>
    </>
  );
}
