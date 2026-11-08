"use client";

import { BigValue, EmptyState, StatBar, StatusPill } from "@/components/desk/primitives";
import { EquityChart } from "@/components/desk/monthly/equity-chart";
import { formatSigned, orDash } from "@/lib/desk/format";
import { CHART_LABEL, CHART_NOTE, healthStats, type Health, type MomentumSummary } from "@/lib/desk/momentum-text";
import type { ChartTrace } from "@/lib/desk/monthly-text";

const NO_SIM = {
  title: "No momentum simulation is saved",
  reason: "momentum_edge_equity.csv is missing or unreadable.",
};

interface SummaryCardProps {
  summary: MomentumSummary | null;
  chart: ChartTrace[] | null | undefined;
  health: Health;
}

/** Full-period figures on the left (trade stats follow the switch), simulated account chart on the right. */
export function SummaryCard({ summary, chart, health }: SummaryCardProps) {
  const cagr = summary?.cagr;
  const traces = chart ?? [];
  const stats = healthStats(health, summary);
  return (
    <section className="desk-card desk-duo" aria-label="Simulation summary"
      style={summary === null ? { gridTemplateColumns: "minmax(0, 1fr)" } : undefined}>
      <div>
        <div className="rd-stat-label">Avg yearly return (CAGR)</div>
        {summary === null ? <EmptyState title={NO_SIM.title} reason={NO_SIM.reason} /> : (
          <>
            <BigValue text={orDash(cagr, (n) => `${formatSigned(n, 1)}%`)} tone={cagr == null ? "muted" : cagr >= 0 ? "gain" : "loss"} />
            <div className="rd-stat-sub" style={{ marginBottom: 10 }}><StatusPill label={health.verdict_text} tone={health.verdict_tone} /></div>
          </>
        )}
        {stats.map((s) => (
          <StatBar key={s.label} label={s.label} value={s.sub ? `${s.value} · ${s.sub}` : s.value} tone={s.tone} />
        ))}
        <p className="rd-note" style={{ margin: "8px 0 0" }}>Best historical combo: {health.best_combo} ({health.top_lift})</p>
        <p className="rd-note" style={{ margin: 0 }}>{health.universe}</p>
      </div>
      {summary === null ? null : (
        <div className="desk-stack" style={{ gap: 6 }}>
          <div className="rd-stat-label" style={{ margin: 0 }}>{CHART_LABEL}</div>
          {traces.length > 0 ? <EquityChart traces={traces} /> : <EmptyState title={NO_SIM.title} reason={NO_SIM.reason} />}
          <p className="rd-note" style={{ margin: 0 }}>{CHART_NOTE}</p>
        </div>
      )}
    </section>
  );
}
