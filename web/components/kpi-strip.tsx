import { pct, signed } from "@/lib/format";
import type { Kpis } from "@/lib/data/strategies";

function Tile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border p-3">
      <div className="text-xs uppercase text-muted-foreground">{label}</div>
      <div className="text-lg font-semibold">{value}</div>
    </div>
  );
}

export function KpiStrip({ kpis }: { kpis: Kpis }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
      <Tile label="CAGR" value={pct(kpis.cagr)} />
      <Tile label="Sharpe" value={signed(kpis.sharpe)} />
      <Tile label="Max DD" value={pct(kpis.maxDd)} />
      <Tile label="Win Rate" value={pct(kpis.winRate)} />
      <Tile label="Trades" value={kpis.numTrades == null ? "—" : String(kpis.numTrades)} />
    </div>
  );
}
