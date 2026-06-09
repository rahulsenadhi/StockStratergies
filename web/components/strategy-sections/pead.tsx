import type { ReactNode } from "react";
import { getDecileSpread } from "@/lib/data/strategies";
import type { Strategy } from "@/lib/data/strategies";
import { HorizontalBars } from "@/components/horizontal-bars";

interface PeadSectionProps {
  strategy: Strategy;
}

export async function PeadSection({ strategy }: PeadSectionProps): Promise<ReactNode> {
  const spread = await getDecileSpread(strategy.decileSpreadCsv);
  if (spread.length === 0) return null;

  const bars = spread.map((p) => ({
    label: `Decile ${p.decile}`,
    value: p.fwdReturn,
    // fwdReturn is already in percentage points (e.g. 4.12 = 4.12%), not a fraction
    valueLabel: `${p.fwdReturn.toFixed(2)}%`,
    highlight: p.decile === 10,
  }));

  return (
    <section>
      <h2 className="mb-1 text-lg font-semibold">SUE Decile Spread</h2>
      <p className="mb-2 text-sm text-muted-foreground">
        Average forward 60-day return by earnings-surprise (SUE) decile. The strategy
        buys decile 10 (highlighted).
      </p>
      <HorizontalBars data={bars} />
    </section>
  );
}
