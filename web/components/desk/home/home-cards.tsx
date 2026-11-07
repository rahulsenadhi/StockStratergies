"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { ColorType, createChart, LineSeries, LineStyle } from "lightweight-charts";
import { DeskTable, NameCell } from "@/components/desk/desk-table";
import { ChangePill, SectionHead, StatusPill } from "@/components/desk/primitives";
import { Segmented } from "@/components/desk/segmented";
import { strategyPageHref, type ResolvedHref } from "@/lib/desk/nav";
import {
  CANDIDATE_FILTERS, GROWTH_NOTE, STRATEGIES_NOTE, candidateNote, filterCandidates, strategySub, type CandidateFilter,
} from "@/lib/desk/home";
import type { DeskColumn } from "@/lib/desk/table";
import type { Candidate, GrowthSeries, GrowthWindow, StrategyRow } from "@/lib/desk/snapshot";

function useOpen() {
  const router = useRouter();
  return (to: ResolvedHref) => {
    if (to.external) window.open(to.href, "_blank", "noopener");
    else router.push(to.href);
  };
}

const CANDIDATE_COLUMNS: DeskColumn<Candidate>[] = [
  { key: "company", label: "Company", kind: "name", priority: 1, sortValue: (c) => c.company || c.ticker,
    render: (c) => <NameCell title={c.company || c.ticker} sub={`${c.ticker} · ${c.short}`} /> },
  { key: "status", label: "Status", kind: "pill", priority: 1, sortValue: (c) => c.status,
    render: (c) => <StatusPill label={c.status} tone={c.status_tone} /> },
  { key: "measure", label: "Key measure", kind: "text", priority: 3, render: (c) => c.key_measure },
  { key: "move", label: "Move", kind: "num", priority: 1, sortValue: (c) => c.change,
    render: (c) => <ChangePill value={c.change} /> },
];

export function CandidatesCard({ candidates, peadHasSignals }: { candidates: Candidate[]; peadHasSignals: boolean }) {
  const [pick, setPick] = useState<CandidateFilter>("All");
  const open = useOpen();
  const shown = useMemo(() => filterCandidates(candidates, pick), [candidates, pick]);
  return (
    <section className="desk-stack" style={{ gap: 8 }} aria-label="Candidates">
      <SectionHead title="Candidates" meta="from saved rankings and signals"
        right={<Segmented options={CANDIDATE_FILTERS} value={pick} onChange={setPick} ariaLabel="Filter candidates" />} />
      <DeskTable rows={shown} columns={CANDIDATE_COLUMNS} caption="Candidates from saved rankings and signals"
        getRowId={(c) => `${c.strategy}|${c.ticker}`} onRowClick={(c) => open(strategyPageHref(c.short, c.ticker))}
        empty="No candidates in the saved files for this filter." />
      <p className="rd-note">{candidateNote(peadHasSignals)}</p>
    </section>
  );
}

const STRATEGY_COLUMNS: DeskColumn<StrategyRow>[] = [
  { key: "name", label: "Strategy", kind: "name", priority: 1,
    render: (s) => <NameCell title={s.title} sub={strategySub(s)} /> },
  { key: "cagr", label: "Per year", kind: "num", priority: 1, sortValue: (s) => s.cagr_pct,
    render: (s) => <ChangePill value={s.cagr_pct} decimals={1} /> },
];

export function StrategiesCard({ strategies }: { strategies: StrategyRow[] }) {
  const open = useOpen();
  return (
    <section className="desk-stack" style={{ gap: 6 }} aria-label="Strategies">
      <SectionHead title="Strategies" meta="click to open" />
      <DeskTable rows={strategies} columns={STRATEGY_COLUMNS} caption="Saved strategies" getRowId={(s) => s.id}
        onRowClick={(s) => open(strategyPageHref(s.id))} empty="No strategies saved yet." />
      <p className="rd-note">{STRATEGIES_NOTE}</p>
    </section>
  );
}

const WINDOWS: readonly GrowthWindow[] = ["1Y", "3Y", "5Y", "Max"];

function readCss(name: string, fallback: string): string {
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return v || fallback;
}

function GrowthChart({ series }: { series: GrowthSeries[] }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el || series.length === 0) return;
    const muted = readCss("--rd-text-muted", "#77756E");
    const line = readCss("--rd-line", "#E7E4DD");
    const chart = createChart(el, {
      height: 290, autoSize: true,
      layout: { background: { type: ColorType.Solid, color: "transparent" }, textColor: muted, fontFamily: "inherit" },
      grid: { vertLines: { visible: false }, horzLines: { color: line } },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false },
      handleScroll: false, handleScale: false,
      localization: { priceFormatter: (p: number) => `${p.toFixed(0)}%` },
    });
    series.forEach((s, i) => {
      const ls = chart.addSeries(LineSeries, { color: s.colour, lineWidth: 2, priceLineVisible: false, lastValueVisible: false });
      ls.setData(s.points.map(([time, value]) => ({ time, value })));
      if (i === 0) ls.createPriceLine({ price: 0, color: muted, lineStyle: LineStyle.Dotted, lineWidth: 1, axisLabelVisible: false });
    });
    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [series]);
  return <div ref={ref} style={{ width: "100%", height: 290 }} role="img" aria-label="Growth of each strategy since the start of the window" />;
}

export function GrowthCard({ growth }: { growth: Record<GrowthWindow, GrowthSeries[]> }) {
  const [win, setWin] = useState<GrowthWindow>("Max");
  const series = growth[win] ?? [];
  return (
    <section className="desk-stack" style={{ gap: 8 }} aria-label="Growth of each strategy">
      <SectionHead title="Growth of each strategy" meta="saved backtests · gross"
        right={<Segmented options={WINDOWS} value={win} onChange={setWin} ariaLabel="Window" />} />
      <div className="desk-card" style={{ padding: "10px 12px" }}>
        <GrowthChart key={win} series={series} />
        <div style={{ marginTop: 6 }}>
          {series.map((s) => (
            <div className="rd-li" key={s.id} style={{ padding: "8px 4px" }}>
              <span className="rd-li__main">
                <span className="rd-li__title"><span className="rd-dot" style={{ background: s.colour }} />{s.title}</span>
                <span className="rd-li__sub">change since {s.start}</span>
              </span>
              <ChangePill value={s.last_pct} decimals={1} />
            </div>
          ))}
        </div>
      </div>
      <p className="rd-note">{GROWTH_NOTE}</p>
    </section>
  );
}
