import { getFunnel, getRecentBreakouts } from "@/lib/data/strategies";
import type { Strategy } from "@/lib/data/strategies";
import { HorizontalBars } from "@/components/horizontal-bars";
import { TradesTable } from "@/components/trades-table";

interface MomentumEdgeSectionProps {
  strategy: Strategy;
}

export async function MomentumEdgeSection({ strategy }: MomentumEdgeSectionProps) {
  const funnel = await getFunnel(strategy.funnelJson);
  const breakouts = await getRecentBreakouts(strategy.recentBreakoutsCsv);

  const universe = funnel[0]?.value ?? 0;
  const bars = funnel.map((s, i) => ({
    label: s.label,
    value: s.value,
    valueLabel:
      universe > 0
        ? `${s.value} (${((s.value / universe) * 100).toFixed(0)}%)`
        : String(s.value),
    highlight: i === funnel.length - 1,
  }));

  const hasFunnel = funnel.length > 0;
  const hasBreakouts = breakouts.columns.length > 0 && breakouts.rows.length > 0;
  if (!hasFunnel && !hasBreakouts) return null;

  return (
    <>
      {hasFunnel && (
        <section>
          <h2 className="mb-1 text-lg font-semibold">Filter Funnel</h2>
          <p className="mb-2 text-sm text-muted-foreground">
            How the universe narrows to today&apos;s signals. Each bar is a gate; the
            drop to the next is how many stocks failed it.
          </p>
          <HorizontalBars data={bars} />
        </section>
      )}
      {hasBreakouts && (
        <section>
          <h2 className="mb-2 text-lg font-semibold">Recent Breakouts</h2>
          <TradesTable columns={breakouts.columns} rows={breakouts.rows} />
        </section>
      )}
    </>
  );
}
