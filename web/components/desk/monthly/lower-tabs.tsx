"use client";

import { DeskTable } from "@/components/desk/desk-table";
import { Checklist, EmptyState, SectionHead } from "@/components/desk/primitives";
import { Tabs } from "@/components/desk/tabs";
import { ExitCurveChart } from "@/components/desk/monthly/exit-curve-chart";
import {
  EMPTY_NO_REBALANCE, EXIT_CAPTION, EXIT_EMPTY, EXIT_LABELS, EXIT_TITLE, HOW_IT_WORKS, HOW_TO_READ, HOW_TO_READ_TITLE,
  REBALANCE_NOTE, TAB_TITLES, VALIDATION_META, VALIDATION_TITLE, exitTexts, rebalanceCells,
  type CheckRow, type ExitRec, type RebalanceRow,
} from "@/lib/desk/monthly-text";
import type { DeskColumn } from "@/lib/desk/table";

const REBALANCE_COLUMNS: DeskColumn<RebalanceRow>[] = [
  { key: "date", label: "Date", kind: "text", priority: 1, sortValue: (r) => r.date, render: (r) => rebalanceCells(r)[0] },
  { key: "top5", label: "Top 5 held", kind: "text", priority: 1, render: (r) => rebalanceCells(r)[1] },
  { key: "bought", label: "Bought", kind: "text", priority: 2, render: (r) => rebalanceCells(r)[2] },
  { key: "sold", label: "Sold", kind: "text", priority: 2, render: (r) => rebalanceCells(r)[3] },
  { key: "value", label: "Account value", kind: "num", priority: 1, sortValue: (r) => r.value,
    render: (r) => rebalanceCells(r)[4] },
];

function RebalanceLog({ rebalances }: { rebalances: { total: number; rows: RebalanceRow[] } }) {
  if (rebalances.rows.length === 0) {
    return <EmptyState title={EMPTY_NO_REBALANCE.title} reason={EMPTY_NO_REBALANCE.reason} />;
  }
  return (
    <div className="desk-stack" style={{ gap: 6 }}>
      <DeskTable rows={rebalances.rows} columns={REBALANCE_COLUMNS} getRowId={(r) => r.date}
        caption="Latest monthly rebalances, newest first" />
      <p className="rd-note" style={{ margin: 0 }}>{REBALANCE_NOTE(rebalances.total)}</p>
    </div>
  );
}

function RulesAndChecks({ checks, colour }: { checks: CheckRow[]; colour: string }) {
  return (
    <div className="desk-stack" style={{ gap: 10 }}>
      <div className="explain-box" style={{ borderLeftColor: colour, margin: 0 }}>
        {HOW_IT_WORKS.map((s, i) => (s.bold ? <b key={i}>{s.text}</b> : <span key={i}>{s.text}</span>))}
      </div>
      <p className="rd-note" style={{ margin: 0 }}>
        <b style={{ color: "var(--rd-text)" }}>{HOW_TO_READ_TITLE}</b><br />{HOW_TO_READ}
      </p>
      <SectionHead title={VALIDATION_TITLE} meta={VALIDATION_META} />
      <Checklist checks={checks} />
    </div>
  );
}

interface TargetRow { tier: string; target: string; book: string; hit: string; pct: number | null; hitRate: number | null }

const [TIER, TARGET, BOOK, HIT] = EXIT_LABELS.columns;
const TARGET_COLUMNS: DeskColumn<TargetRow>[] = [
  { key: "tier", label: TIER, kind: "text", priority: 1, sortValue: (t) => t.tier, render: (t) => t.tier },
  { key: "target", label: TARGET, kind: "num", priority: 1, sortValue: (t) => t.pct, render: (t) => t.target },
  { key: "book", label: BOOK, kind: "num", priority: 1, render: (t) => t.book },
  { key: "hit", label: HIT, kind: "num", priority: 1, sortValue: (t) => t.hitRate, render: (t) => t.hit },
];

function Metric({ label, value, help }: { label: string; value: string; help?: string }) {
  return (
    <div className="desk-card" title={help}>
      <div className="rd-stat-label">{label}</div>
      <div className="desk-metric">{value}</div>
      {help ? <div className="rd-stat-sub" style={{ marginTop: 2 }}>{help}</div> : null}
    </div>
  );
}

export function ExitResearch({ rec }: { rec: ExitRec | null }) {
  if (!rec) return <EmptyState title={EXIT_EMPTY} />;
  const t = exitTexts(rec);
  const saved = rec.targets ?? [];
  const targets: TargetRow[] = t.targets.map((row, i) => ({
    ...row, pct: saved[i]?.pct ?? null, hitRate: saved[i]?.hit_rate ?? null,
  }));
  return (
    <div className="desk-stack" style={{ gap: 10 }}>
      <h3 className="desk-h3">{EXIT_TITLE}</h3>
      <p className="rd-note" style={{ margin: 0 }}>{EXIT_CAPTION}</p>
      <div className="desk-metrics">
        <Metric label={EXIT_LABELS.hold} value={t.hold} help={EXIT_LABELS.holdHelp} />
        <Metric label={EXIT_LABELS.median} value={t.median} />
        <Metric label={EXIT_LABELS.winRate} value={t.winRate} />
      </div>
      {targets.length > 0 ? (
        <DeskTable rows={targets} columns={TARGET_COLUMNS} getRowId={(r) => r.tier} caption="Profit targets" />
      ) : null}
      <p className="rd-note" style={{ margin: 0 }}>{t.caption}</p>
      {rec.curve && rec.curve.length > 0 ? <ExitCurveChart curve={rec.curve} holdDays={rec.hold_days} /> : null}
    </div>
  );
}

interface LowerTabsProps {
  rebalances: { total: number; rows: RebalanceRow[] };
  checks: CheckRow[];
  exitRec: ExitRec | null;
  colour: string;
}

/** Python render_monthly st.tabs: Rebalance log / Rules and checks / Exit research. */
export function LowerTabs({ rebalances, checks, exitRec, colour }: LowerTabsProps) {
  const [reb, rules, exit] = TAB_TITLES;
  return (
    <Tabs tabs={[
      { id: "rebalance", label: reb, content: <RebalanceLog rebalances={rebalances} /> },
      { id: "rules", label: rules, content: <RulesAndChecks checks={checks} colour={colour} /> },
      { id: "exit", label: exit, content: <ExitResearch rec={exitRec} /> },
    ]} />
  );
}
