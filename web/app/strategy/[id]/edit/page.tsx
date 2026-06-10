import { notFound } from "next/navigation";
import Link from "next/link";
import { getStrategySpec, type ExitsSpec } from "@/lib/data/strategies";
import { StrategyForm, type StrategyFormValues } from "@/components/strategy-form";

export const dynamic = "force-dynamic";

function specToInitial(spec: Record<string, unknown>): Partial<StrategyFormValues> {
  const exits = (spec.exits ?? {}) as ExitsSpec;
  const sizing = (spec.sizing ?? {}) as Record<string, unknown>;
  const str = (v: unknown, d: string) => (typeof v === "string" ? v : d);
  const num = (v: unknown, d: number) => (typeof v === "number" ? v : d);
  return {
    name: str(spec.name, ""),
    type: str(spec.type, "Momentum"),
    description: str(spec.description, ""),
    universe: str(spec.universe, "Nifty 50"),
    entryFormula: str(spec.entry_formula, ""),
    timeEnabled: exits.time_enabled ?? false,
    timeDays: exits.time_days ?? 30,
    hardStopEnabled: exits.hard_stop_enabled ?? false,
    hardStopPct: exits.hard_stop_pct ?? 8,
    trailEnabled: exits.trail_enabled ?? false,
    trailPct: exits.trail_pct ?? 12,
    maxPositions: num(sizing.max_positions, 5),
    initialCash: num(sizing.initial_cash, 1000000),
  };
}

export default async function EditStrategyPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  if (!/^[a-z0-9_]+$/.test(id)) notFound(); // traversal guard before fs read
  const spec = await getStrategySpec(id);
  if (!spec) notFound();

  return (
    <main className="mx-auto max-w-5xl space-y-6 p-8">
      <Link href={`/strategy/${id}`} className="text-sm text-muted-foreground">← Back to strategy</Link>
      <h1 className="text-2xl font-bold">Edit Strategy</h1>
      <p className="text-sm text-muted-foreground">
        Saving re-runs the backtest (1–3 min) and refreshes KPIs. The name is fixed — use Clone to rename.
      </p>
      <StrategyForm mode="edit" strategyId={id} lockName initial={specToInitial(spec)} />
    </main>
  );
}
