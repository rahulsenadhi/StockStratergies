import type { ReactNode } from "react";
import { pct } from "@/lib/format";
import type { Summary } from "@/lib/summary";
import { Term } from "@/components/ui/term";
import { upDown } from "@/lib/dir";
import { cn } from "@/lib/utils";

function Tile({ label, value, sub, valueClass }: { label: ReactNode; value: string; sub?: string; valueClass?: string }) {
  return (
    <div className="rounded-lg border border-border p-3">
      <div className="text-xs uppercase text-muted-foreground">{label}</div>
      <div className={cn("text-lg font-semibold font-mono tabular-nums", valueClass)}>{value}</div>
      {sub ? <div className="text-xs text-muted-foreground">{sub}</div> : null}
    </div>
  );
}

export function HomeKpiStrip({ summary }: { summary: Summary }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      <Tile label="Total Strategies" value={String(summary.total)} sub={`${summary.live} live · ${summary.paper} paper`} />
      <Tile label={<Term k="CAGR">Avg CAGR</Term>} value={pct(summary.avgCagr)} sub={`Best ${pct(summary.bestCagr)}`} valueClass={upDown(summary.avgCagr)} />
      <Tile label={<Term k="Win_Rate">Avg Win Rate</Term>} value={pct(summary.avgWinRate)} />
      <Tile label="Total Trades" value={summary.totalTrades.toLocaleString()} />
    </div>
  );
}
