import Link from "next/link";
import { StrategyForm } from "@/components/strategy-form";

export const dynamic = "force-dynamic";

export default function NewStrategyPage() {
  return (
    <main className="mx-auto max-w-5xl space-y-6 p-8">
      <Link href="/leaderboard" className="text-sm text-muted-foreground">← Leaderboard</Link>
      <h1 className="text-2xl font-bold">New Strategy</h1>
      <p className="text-sm text-muted-foreground">
        Define a formula-based strategy. Creating runs a backtest (1–3 min) and adds it to the leaderboard.
      </p>
      <StrategyForm />
    </main>
  );
}
