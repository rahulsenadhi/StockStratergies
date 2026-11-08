"use client";

import { useState } from "react";
import { BigValue, EmptyState, StatBar } from "@/components/desk/primitives";
import { Segmented } from "@/components/desk/segmented";
import { EquityChart } from "@/components/desk/monthly/equity-chart";
import {
  CHART_LABEL, CHART_NOTE, CHART_WINDOWS, EMPTY_NO_SIMULATION, SUMMARY_LABEL,
  benchSub, cagrText, cagrTone, summaryStats,
  type ChartTrace, type ChartWindow, type MonthlySummary,
} from "@/lib/desk/monthly-text";

interface SummaryCardProps {
  summary: MonthlySummary;
  chart: Record<ChartWindow, ChartTrace[]> | null;
}

/** Python _render_monthly_summary: full-period figures left, windowed account chart right (1 : 2.3). */
export function SummaryCard({ summary, chart }: SummaryCardProps) {
  const [win, setWin] = useState<ChartWindow>("All");
  const traces = chart?.[win] ?? [];

  return (
    <section className="desk-card desk-duo" aria-label="Simulation summary">
      <div>
        <div className="rd-stat-label">{SUMMARY_LABEL}</div>
        <BigValue text={cagrText(summary)} tone={cagrTone(summary)} />
        <div className="rd-stat-sub">{benchSub(summary)}</div>
        {summaryStats(summary).map((s) => <StatBar key={s.label} label={s.label} value={s.value} tone={s.tone} />)}
      </div>
      <div className="desk-stack" style={{ gap: 6 }}>
        <div className="desk-row">
          <div className="rd-stat-label" style={{ margin: 0 }}>{CHART_LABEL}</div>
          <Segmented options={CHART_WINDOWS} value={win} onChange={setWin} ariaLabel="Chart window" />
        </div>
        {traces.length > 0
          ? <EquityChart key={win} traces={traces} />
          : <EmptyState title={EMPTY_NO_SIMULATION.title} reason={EMPTY_NO_SIMULATION.reason} />}
        <p className="rd-note" style={{ margin: 0 }}>{CHART_NOTE}</p>
      </div>
    </section>
  );
}
