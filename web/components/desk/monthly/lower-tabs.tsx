"use client";

import { DeskTable } from "@/components/desk/desk-table";
import { Checklist, EmptyState, SectionHead } from "@/components/desk/primitives";
import { Tabs } from "@/components/desk/tabs";
import {
  EMPTY_NO_REBALANCE, HOW_IT_WORKS, HOW_TO_READ, HOW_TO_READ_TITLE,
  REBALANCE_NOTE, TAB_TITLES, VALIDATION_META, VALIDATION_TITLE, rebalanceCells,
  type CheckRow, type RebalanceRow,
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

interface LowerTabsProps {
  rebalances: { total: number; rows: RebalanceRow[] };
  checks: CheckRow[];
  colour: string;
}

/** Python render_monthly st.tabs: Rebalance log / Rules and checks. */
export function LowerTabs({ rebalances, checks, colour }: LowerTabsProps) {
  const [reb, rules] = TAB_TITLES;
  return (
    <Tabs tabs={[
      { id: "rebalance", label: reb, content: <RebalanceLog rebalances={rebalances} /> },
      { id: "rules", label: rules, content: <RulesAndChecks checks={checks} colour={colour} /> },
    ]} />
  );
}
