import { notFound } from "next/navigation";
import Link from "next/link";
import { getStrategy, getEquityCurve, computeDrawdown, getTrades, getMonthlyReturns, getStrategySpec } from "@/lib/data/strategies";
import { LineChart } from "@/components/line-chart";
import { KpiStrip } from "@/components/kpi-strip";
import { TradesTable } from "@/components/trades-table";
import { StrategySection } from "@/components/strategy-sections";
import { MonthlyHeatmap } from "@/components/monthly-heatmap";
import { BacktestButton } from "@/components/backtest-button";
import { DeleteStrategyButton } from "@/components/delete-strategy-button";
import { StrategyExplainer } from "@/components/strategy-explainer";
import { ExitPlaybook } from "@/components/exit-playbook";

export const dynamic = "force-dynamic";

export default async function StrategyPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const s = await getStrategy(id);
  if (!s) notFound();

  const spec = await getStrategySpec(id);

  const curve = await getEquityCurve(s.equityCsv);
  const dd = computeDrawdown(curve);
  const trades = await getTrades(s.tradesCsv);
  const monthly = await getMonthlyReturns(s.equityCsv);

  return (
    <main className="mx-auto max-w-7xl space-y-6 px-6 py-4">
      <Link href="/leaderboard" className="text-sm text-muted-foreground">← Leaderboard</Link>
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold">{s.name}</h1>
          <p className="text-sm text-muted-foreground">{s.type} · {s.status}</p>
        </div>
        <div className="flex items-center gap-2">
          {spec && <Link href={`/strategy/${id}/edit`} className="rounded-md border px-3 py-1.5 text-sm font-medium hover:bg-accent">Edit</Link>}
          {spec && <Link href={`/strategy/new?from=${id}`} className="rounded-md border px-3 py-1.5 text-sm font-medium hover:bg-accent">Clone</Link>}
          {spec && <DeleteStrategyButton id={id} />}
          {s.backtest && <BacktestButton strategyId={s.id} />}
        </div>
      </div>
      <KpiStrip kpis={s.kpis} />
      <StrategyExplainer id={s.id} />
      <ExitPlaybook id={s.id} />
      <section>
        <h2 className="mb-2 text-lg font-semibold">Equity Curve</h2>
        <LineChart data={curve} color="#22c55e" />
      </section>
      <section>
        <h2 className="mb-2 text-lg font-semibold">Drawdown</h2>
        <LineChart data={dd} color="#ef4444" />
      </section>
      {monthly.length > 0 && (
        <section>
          <h2 className="mb-2 text-lg font-semibold">Monthly Returns</h2>
          <MonthlyHeatmap rows={monthly} />
        </section>
      )}
      <section>
        <h2 className="mb-2 text-lg font-semibold">Trade History ({trades.rows.length})</h2>
        <TradesTable {...trades} />
      </section>
      <StrategySection strategy={s} />
    </main>
  );
}
