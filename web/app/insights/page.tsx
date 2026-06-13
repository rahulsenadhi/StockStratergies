import { getInsights } from "@/lib/data/strategies";
import { InsightsView } from "@/components/insights-view";

export const dynamic = "force-dynamic"; // read insights.json at request time

export default async function InsightsPage() {
  const report = await getInsights();

  return (
    <main className="mx-auto max-w-7xl px-6 py-4">
      <h1 className="mb-1 text-2xl font-bold">Insights — What Predicts Winners?</h1>
      <p className="mb-4 text-sm text-muted-foreground">
        Closed-trade analytics: win rate and average PnL grouped by setup, recovery speed,
        score, and exit reason. Use these to favour the buckets that historically paid.
      </p>

      {report === null ? (
        <div className="rounded-md border border-border bg-muted/30 px-4 py-3 text-sm text-muted-foreground">
          No insights yet. Run{" "}
          <code className="font-mono text-foreground">python precompute_insights.py</code> to
          generate <code className="font-mono text-foreground">insights.json</code>.
        </div>
      ) : (
        <InsightsView report={report} />
      )}
    </main>
  );
}
