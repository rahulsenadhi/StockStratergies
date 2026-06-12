import Link from "next/link";
import { getStrategySpec, type ExitsSpec } from "@/lib/data/strategies";
import { StrategyForm, type StrategyFormValues } from "@/components/strategy-form";

export const dynamic = "force-dynamic";

function cloneInitial(spec: Record<string, unknown>): Partial<StrategyFormValues> {
  const exits = (spec.exits ?? {}) as ExitsSpec;
  const sizing = (spec.sizing ?? {}) as Record<string, unknown>;
  const str = (v: unknown, d: string) => (typeof v === "string" ? v : d);
  const num = (v: unknown, d: number) => (typeof v === "number" ? v : d);
  return {
    name: `Copy of ${str(spec.name, "strategy")}`,
    type: str(spec.type, "Momentum"),
    description: str(spec.description, ""),
    universe: str(spec.universe, "Nifty 50"),
    entryFormula: str(spec.entry_formula, ""),
    timeEnabled: exits.time_enabled ?? true,
    timeDays: exits.time_days ?? 30,
    hardStopEnabled: exits.hard_stop_enabled ?? true,
    hardStopPct: exits.hard_stop_pct ?? 8,
    trailEnabled: exits.trail_enabled ?? false,
    trailPct: exits.trail_pct ?? 12,
    maxPositions: num(sizing.max_positions, 5),
    initialCash: num(sizing.initial_cash, 1000000),
  };
}

export default async function NewStrategyPage({
  searchParams,
}: { searchParams: Promise<{ from?: string }> }) {
  const { from } = await searchParams;
  // Only a well-formed id reaches the fs read; anything else → no prefill (traversal guard).
  const validFrom = from && /^[a-z0-9_]+$/.test(from) ? from : null;
  const sourceSpec = validFrom ? await getStrategySpec(validFrom) : null;
  const initial = sourceSpec ? cloneInitial(sourceSpec) : undefined;

  return (
    <main className="mx-auto max-w-7xl space-y-6 px-6 py-4">
      <Link href="/leaderboard" className="text-sm text-muted-foreground">← Leaderboard</Link>
      <h1 className="text-2xl font-bold">{sourceSpec ? "Clone Strategy" : "New Strategy"}</h1>
      <p className="text-sm text-muted-foreground">
        Define a formula-based strategy. Creating runs a backtest (1–3 min) and adds it to the leaderboard.
      </p>
      <StrategyForm initial={initial} />
    </main>
  );
}
