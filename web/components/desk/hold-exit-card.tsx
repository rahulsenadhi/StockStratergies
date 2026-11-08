"use client";

import { DeskTable } from "@/components/desk/desk-table";
import { ExitCurveChart } from "@/components/desk/exit-curve-chart";
import { EmptyState, SectionHead, StatBar } from "@/components/desk/primitives";
import {
  EXIT_EMPTY, HOLD_EXIT_LABELS, HONESTY_NOTE, SMALL_SAMPLE_NOTE, holdExitRows, type ExitRec,
} from "@/lib/desk/exit-text";
import type { DeskColumn } from "@/lib/desk/table";

type TargetText = ReturnType<typeof holdExitRows>["targets"][number];
export interface HoldExitExtra { label: string; value: string; sub?: string }

const [TIER, SELL_AT, SELL_THIS_MUCH, HIT] = HOLD_EXIT_LABELS.columns;
const TARGET_COLUMNS: DeskColumn<TargetText>[] = [
  { key: "tier", label: TIER, kind: "text", priority: 1, render: (t) => t.tier },
  { key: "target", label: SELL_AT, kind: "num", priority: 1, render: (t) => t.target },
  { key: "book", label: SELL_THIS_MUCH, kind: "num", priority: 1, render: (t) => t.book },
  { key: "hit", label: HIT, kind: "num", priority: 1, render: (t) => t.hit },
];

/** Hold and exit plan from the saved exit_rec: history only, with the sample size and the share that still lost. */
export function HoldExitCard({ rec, title, extra = [] }: { rec: ExitRec | null; title: string; extra?: HoldExitExtra[] }) {
  if (!rec) {
    return (
      <section className="desk-stack" style={{ gap: 8 }} aria-label={title}>
        <SectionHead title={title} />
        <EmptyState title={EXIT_EMPTY} />
      </section>
    );
  }
  const r = holdExitRows(rec);
  return (
    <section className="desk-card hx-card desk-stack" style={{ gap: 10 }} aria-label={title}>
      <SectionHead title={title} />
      <div className="hx-grid">
        <div className="desk-stack" style={{ gap: 4 }}>
          <StatBar label={HOLD_EXIT_LABELS.hold} value={r.hold} tone="info" />
          <StatBar label={HOLD_EXIT_LABELS.winRate} value={r.winRate} />
          <StatBar label={HOLD_EXIT_LABELS.median} value={r.median} />
          <StatBar label={HOLD_EXIT_LABELS.stop} value={r.stop} tone="loss" />
          {extra.map((e) => (
            <StatBar key={e.label} label={e.sub ? `${e.label} (${e.sub})` : e.label} value={e.value} />
          ))}
        </div>
        {r.targets.length > 0 ? (
          <div className="desk-stack" style={{ gap: 4 }}>
            <div className="rd-stat-label">{HOLD_EXIT_LABELS.sellPlan}</div>
            <DeskTable rows={r.targets} columns={TARGET_COLUMNS} getRowId={(t) => t.tier} caption={HOLD_EXIT_LABELS.sellPlan} />
          </div>
        ) : null}
      </div>
      <p className="rd-note" style={{ margin: 0 }}>
        {r.basis} (price data: {r.dataQuality}).{r.isSmallSample ? ` ${SMALL_SAMPLE_NOTE}` : ""}
      </p>
      {r.lossPct != null ? <p className="rd-note" style={{ margin: 0 }}>{HONESTY_NOTE(r.lossPct)}</p> : null}
      {rec.curve && rec.curve.length > 0 ? (
        <details className="desk-disclosure">
          <summary>Return by days held</summary>
          <div><ExitCurveChart curve={rec.curve} holdDays={rec.hold_days} /></div>
        </details>
      ) : null}
    </section>
  );
}
