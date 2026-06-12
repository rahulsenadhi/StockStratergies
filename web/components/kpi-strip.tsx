import type { ReactNode } from "react";
import { pct, signed } from "@/lib/format";
import type { Kpis } from "@/lib/data/strategies";
import { Term } from "@/components/ui/term";
import { upDown } from "@/lib/dir";
import { cn } from "@/lib/utils";

function Tile({ label, value, valueClass }: { label: ReactNode; value: string; valueClass?: string }) {
  return (
    <div className="rounded-lg border border-border p-3">
      <div className="text-xs uppercase text-muted-foreground">{label}</div>
      <div className={cn("text-lg font-semibold font-mono tabular-nums", valueClass)}>{value}</div>
    </div>
  );
}

export function KpiStrip({ kpis }: { kpis: Kpis }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
      <Tile label={<Term k="CAGR">CAGR</Term>} value={pct(kpis.cagr)} valueClass={upDown(kpis.cagr)} />
      <Tile label={<Term k="Sharpe">Sharpe</Term>} value={signed(kpis.sharpe)} />
      <Tile label={<Term k="Drawdown">Max DD</Term>} value={pct(kpis.maxDd)} valueClass={upDown(kpis.maxDd)} />
      <Tile label={<Term k="Win_Rate">Win Rate</Term>} value={pct(kpis.winRate)} />
      <Tile label="Trades" value={kpis.numTrades == null ? "—" : String(kpis.numTrades)} />
    </div>
  );
}
