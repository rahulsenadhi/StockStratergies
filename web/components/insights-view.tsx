import { cn } from "@/lib/utils";
import type { InsightBucket, InsightsReport, StrategyInsights } from "@/lib/data/strategies";

const STRATEGY_NAME: Record<string, string> = {
  momentum_edge: "Momentum Edge",
  ipo_edge: "IPO Edge",
  monthly_rotation: "Monthly Rotation",
  pead: "PEAD",
};

// Ordered (key, label) — only present keys render.
const BUCKET_SECTIONS: { key: keyof StrategyInsights; label: string }[] = [
  { key: "byEntryType", label: "By Entry Type" },
  { key: "bySetupType", label: "By Setup Type" },
  { key: "byRecoverySpeed", label: "By Recovery Speed" },
  { key: "byEntryStage", label: "By Entry Stage" },
  { key: "byScoreBucket", label: "By Score Bucket" },
  { key: "byExitReason", label: "By Exit Reason" },
];

const num = (v: number | null, suffix = ""): string => (v == null ? "—" : `${v}${suffix}`);
const wrClass = (v: number | null): string =>
  v == null ? "" : v >= 50 ? "text-green-500" : v >= 40 ? "text-amber-500" : "text-red-500";
const pnlClass = (v: number | null): string =>
  v == null ? "" : v > 0 ? "text-green-500" : "text-red-500";

const TH = "px-3 py-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground";
const THR = `${TH} text-right`;

function BucketTable({ label, rows }: { label: string; rows: InsightBucket[] }) {
  if (!rows.length) return null;
  return (
    <div>
      <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {label}
      </h4>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border">
              <th className={`${TH} text-left`}>Bucket</th>
              <th className={THR}>N</th>
              <th className={THR}>Win %</th>
              <th className={THR}>Avg PnL</th>
              <th className={THR}>Median</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr
                key={r.group}
                className={cn(
                  "border-b border-border transition-colors last:border-0 hover:bg-muted/40",
                  i % 2 !== 0 && "bg-muted/10",
                )}
              >
                <td className="px-3 py-1.5">{r.group}</td>
                <td className="px-3 py-1.5 text-right font-mono tabular-nums text-muted-foreground">
                  {r.count}
                </td>
                <td className={cn("px-3 py-1.5 text-right font-mono tabular-nums", wrClass(r.winRate))}>
                  {num(r.winRate, "%")}
                </td>
                <td className={cn("px-3 py-1.5 text-right font-mono tabular-nums", pnlClass(r.avgPnl))}>
                  {r.avgPnl == null ? "—" : `${r.avgPnl > 0 ? "+" : ""}${r.avgPnl}%`}
                </td>
                <td className="px-3 py-1.5 text-right font-mono tabular-nums text-muted-foreground">
                  {r.medianPnl == null ? "—" : `${r.medianPnl}%`}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function StrategyInsightsBlock({ id, ins }: { id: string; ins: StrategyInsights }) {
  const sections = BUCKET_SECTIONS.filter((s) => (ins[s.key] as InsightBucket[] | undefined)?.length);
  if (!ins.overall && sections.length === 0) return null;
  const o = ins.overall;

  return (
    <section className="space-y-3">
      <h2 className="text-lg font-semibold">{STRATEGY_NAME[id] ?? id}</h2>
      {o && (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <div className="rounded-md border border-border bg-muted/20 px-3 py-2.5">
            <div className="text-[10px] uppercase tracking-wide text-muted-foreground">Closed trades</div>
            <div className="text-lg font-bold font-mono tabular-nums">{o.n}</div>
          </div>
          <div className="rounded-md border border-border bg-muted/20 px-3 py-2.5">
            <div className="text-[10px] uppercase tracking-wide text-muted-foreground">Win rate</div>
            <div className={cn("text-lg font-bold font-mono tabular-nums", wrClass(o.winRate))}>
              {num(o.winRate, "%")}
            </div>
          </div>
          <div className="rounded-md border border-border bg-muted/20 px-3 py-2.5">
            <div className="text-[10px] uppercase tracking-wide text-muted-foreground">Avg PnL</div>
            <div className={cn("text-lg font-bold font-mono tabular-nums", pnlClass(o.avgPnl))}>
              {o.avgPnl == null ? "—" : `${o.avgPnl > 0 ? "+" : ""}${o.avgPnl}%`}
            </div>
          </div>
          <div className="rounded-md border border-border bg-muted/20 px-3 py-2.5">
            <div className="text-[10px] uppercase tracking-wide text-muted-foreground">Median PnL</div>
            <div className="text-lg font-bold font-mono tabular-nums">
              {o.medianPnl == null ? "—" : `${o.medianPnl}%`}
            </div>
          </div>
        </div>
      )}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {sections.map((s) => (
          <BucketTable key={s.key} label={s.label} rows={ins[s.key] as InsightBucket[]} />
        ))}
      </div>
    </section>
  );
}

export function InsightsView({ report }: { report: InsightsReport }) {
  const entries = Object.entries(report).filter(
    ([, ins]) => ins.overall || Object.keys(ins).length > 0,
  );
  if (entries.length === 0) {
    return <p className="text-sm text-muted-foreground">No trade analytics yet.</p>;
  }
  return (
    <div className="space-y-8">
      {entries.map(([id, ins]) => (
        <StrategyInsightsBlock key={id} id={id} ins={ins} />
      ))}
    </div>
  );
}
