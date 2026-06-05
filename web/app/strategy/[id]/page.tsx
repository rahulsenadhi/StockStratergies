import { notFound } from "next/navigation";
import Link from "next/link";
import { getStrategy, getEquityCurve, computeDrawdown, getTrades } from "@/lib/data/strategies";
import { LineChart } from "@/components/line-chart";
import { KpiStrip } from "@/components/kpi-strip";
import { TradesTable } from "@/components/trades-table";

export const dynamic = "force-dynamic";

export default async function StrategyPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const s = await getStrategy(id);
  if (!s) notFound();

  const curve = await getEquityCurve(s.equityCsv);
  const dd = computeDrawdown(curve);
  const trades = await getTrades(s.tradesCsv);

  return (
    <main className="mx-auto max-w-5xl space-y-6 p-8">
      <Link href="/leaderboard" className="text-sm text-muted-foreground">← Leaderboard</Link>
      <div>
        <h1 className="text-2xl font-bold">{s.name}</h1>
        <p className="text-sm text-muted-foreground">{s.type} · {s.status}</p>
      </div>
      <KpiStrip kpis={s.kpis} />
      <section>
        <h2 className="mb-2 text-lg font-semibold">Equity Curve</h2>
        <LineChart data={curve} color="#22c55e" />
      </section>
      <section>
        <h2 className="mb-2 text-lg font-semibold">Drawdown</h2>
        <LineChart data={dd} color="#ef4444" />
      </section>
      <section>
        <h2 className="mb-2 text-lg font-semibold">Trade History ({trades.rows.length})</h2>
        <TradesTable {...trades} />
      </section>
    </main>
  );
}
