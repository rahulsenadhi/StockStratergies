import type { ReactNode } from "react";
import { getEquityWithBenchmark } from "@/lib/data/strategies";
import type { Strategy } from "@/lib/data/strategies";
import { MultiLineChart } from "@/components/multi-line-chart";
import { pct } from "@/lib/format";
import { PriceChartBlock } from "@/components/strategy-sections/price-chart-block";

interface IpoEdgeSectionProps {
  strategy: Strategy;
  chart?: string;
}

export async function IpoEdgeSection({ strategy, chart }: IpoEdgeSectionProps): Promise<ReactNode> {
  const eq = await getEquityWithBenchmark(strategy.equityCsv);
  const series = [
    { name: "IPO Edge", color: "#22c55e", points: eq.strategy },
    { name: "Nifty", color: "#f59e0b", points: eq.benchmark },
  ].filter((s) => s.points.length > 0);
  const hasOther = series.length > 0;

  const alpha =
    strategy.kpis.cagr != null && eq.benchmarkCagr != null
      ? strategy.kpis.cagr - eq.benchmarkCagr
      : null;

  return (
    <>
      <PriceChartBlock strategy={strategy} chart={chart} />
      {hasOther && (
        <section>
          <div className="mb-2 flex items-baseline justify-between">
            <h2 className="text-lg font-semibold">Growth vs Nifty</h2>
            <span className="text-sm text-muted-foreground">
              Extra vs Nifty (Alpha):{" "}
              <span
                className={
                  alpha == null
                    ? "text-muted-foreground"
                    : alpha >= 0
                      ? "text-green-500"
                      : "text-red-500"
                }
              >
                {pct(alpha)}
              </span>
            </span>
          </div>
          <MultiLineChart series={series} />
        </section>
      )}
    </>
  );
}
