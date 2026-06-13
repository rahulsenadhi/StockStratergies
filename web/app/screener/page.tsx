import { getPeadScreener } from "@/lib/data/strategies";
import { sectorsOf } from "@/lib/pead-screener";
import { PeadScreenerClient } from "@/components/pead-screener-client";

export const dynamic = "force-dynamic"; // read pead_screener.json at request time

export default async function ScreenerPage() {
  const rows = await getPeadScreener();
  const sectors = sectorsOf(rows);

  return (
    <main className="mx-auto max-w-7xl px-6 py-4">
      <h1 className="mb-1 text-2xl font-bold">PEAD Screener</h1>
      <p className="mb-4 text-sm text-muted-foreground">
        Post-Earnings-Announcement Drift candidates. Filter the earnings universe by SUE
        (earnings surprise), Piotroski F-Score (quality), P/B (valuation), and sector.
      </p>

      {rows.length === 0 ? (
        <div className="rounded-md border border-border bg-muted/30 px-4 py-3 text-sm text-muted-foreground">
          No screener data yet. Run{" "}
          <code className="font-mono text-foreground">python precompute_pead_screener.py</code>{" "}
          to generate <code className="font-mono text-foreground">pead_screener.json</code>.
        </div>
      ) : (
        <PeadScreenerClient rows={rows} sectors={sectors} />
      )}
    </main>
  );
}
