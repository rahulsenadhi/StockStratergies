import { DeskTable } from "@/components/desk/desk-table";
import { EmptyState } from "@/components/desk/primitives";
import { ExitCurveChart } from "@/components/desk/exit-curve-chart";
import { EXIT_CAPTION, EXIT_EMPTY, EXIT_LABELS, exitTexts, type ExitRec } from "@/lib/desk/exit-text";
import type { DeskColumn } from "@/lib/desk/table";

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

export function ExitResearch({ rec, title }: { rec: ExitRec | null; title: string }) {
  if (!rec) return <EmptyState title={EXIT_EMPTY} />;
  const t = exitTexts(rec);
  const saved = rec.targets ?? [];
  const targets: TargetRow[] = t.targets.map((row, i) => ({
    ...row, pct: saved[i]?.pct ?? null, hitRate: saved[i]?.hit_rate ?? null,
  }));
  return (
    <div className="desk-stack" style={{ gap: 10 }}>
      <h3 className="desk-h3">{title}</h3>
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
