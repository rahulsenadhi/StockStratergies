import { getStrategies, getEquityCurve, rebaseToReturn, getLiveSignals } from "@/lib/data/strategies";
import { LiveSignals, type LivePanel } from "@/components/live-signals";
import { summarizeStrategies } from "@/lib/summary";
import { HomeKpiStrip } from "@/components/home-kpi-strip";
import { MultiLineChart, type Series } from "@/components/multi-line-chart";
import { TopPerformers } from "@/components/top-performers";
import { RecentBacktests } from "@/components/recent-backtests";

export const dynamic = "force-dynamic";

const PALETTE = ["#22c55e", "#3b82f6", "#f59e0b", "#ef4444", "#a855f7", "#14b8a6"];

export default async function Home() {
  const strategies = await getStrategies();
  const summary = summarizeStrategies(strategies);
  const top = [...strategies]
    .sort((a, b) => (b.kpis.sharpe ?? -Infinity) - (a.kpis.sharpe ?? -Infinity))
    .slice(0, 3);
  const recent = [...strategies]
    .sort((a, b) => (b.lastRun ?? "").localeCompare(a.lastRun ?? ""))
    .slice(0, 5);
  const panels: LivePanel[] = (
    await Promise.all(
      strategies.map(async (s) => ({
        name: s.name,
        picks: s.liveSignalsCsv ? await getLiveSignals(s.liveSignalsCsv) : [],
      })),
    )
  ).filter((p) => p.picks.length > 0);

  const series: Series[] = (
    await Promise.all(
      strategies.map(async (s, i) => ({
        name: s.name,
        color: PALETTE[i % PALETTE.length],
        points: rebaseToReturn(await getEquityCurve(s.equityCsv)),
      })),
    )
  ).filter((x) => x.points.length > 0);

  return (
    <main className="mx-auto max-w-5xl space-y-8 p-8">
      <h1 className="text-2xl font-bold">NSE Strategy Hub</h1>
      <HomeKpiStrip summary={summary} />
      <section>
        <h2 className="mb-2 text-lg font-semibold">Combined Equity (rebased to start)</h2>
        <MultiLineChart series={series} />
      </section>
      <section>
        <h2 className="mb-2 text-lg font-semibold">Top Performers</h2>
        <TopPerformers items={top} />
      </section>
      <section>
        <h2 className="mb-2 text-lg font-semibold">Recent Backtests</h2>
        <RecentBacktests items={recent} />
      </section>
      <section>
        <h2 className="mb-2 text-lg font-semibold">Live Signals</h2>
        <LiveSignals panels={panels} />
      </section>
    </main>
  );
}
