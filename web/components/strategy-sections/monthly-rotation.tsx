import { getEquityWithBenchmark, getRankings } from "@/lib/data/strategies";
import type { Strategy } from "@/lib/data/strategies";
import { MultiLineChart } from "@/components/multi-line-chart";
import { RankingsTable } from "@/components/rankings-table";
import { pct } from "@/lib/format";

interface MonthlyRotationSectionProps {
  strategy: Strategy;
}

export async function MonthlyRotationSection({ strategy }: MonthlyRotationSectionProps) {
  const eq = await getEquityWithBenchmark(strategy.equityCsv);
  const rankings = await getRankings(strategy.liveSignalsCsv);

  const series = [
    { name: "Monthly Rotation", color: "#22c55e", points: eq.strategy },
    { name: "Nifty", color: "#f59e0b", points: eq.benchmark },
  ].filter((s) => s.points.length > 0);

  const alpha =
    strategy.kpis.cagr != null && eq.benchmarkCagr != null
      ? strategy.kpis.cagr - eq.benchmarkCagr
      : null;

  const hasOverlay = series.length > 0;
  const hasRankings = rankings.length > 0;
  if (!hasOverlay && !hasRankings) return null;

  return (
    <>
      {hasOverlay && (
        <section>
          <div className="mb-2 flex items-baseline justify-between">
            <h2 className="text-lg font-semibold">Growth vs Nifty</h2>
            <span className="text-sm text-muted-foreground">
              Extra vs Nifty (Alpha):{" "}
              <span className={alpha == null ? "text-muted-foreground" : alpha >= 0 ? "text-green-500" : "text-red-500"}>
                {pct(alpha)}
              </span>
            </span>
          </div>
          <MultiLineChart series={series} />
        </section>
      )}
      {hasRankings && (
        <section>
          <h2 className="mb-2 text-lg font-semibold">
            All Stocks — Ranked by Strength (Top 5 held)
          </h2>
          <RankingsTable rows={rankings} />
        </section>
      )}
    </>
  );
}
