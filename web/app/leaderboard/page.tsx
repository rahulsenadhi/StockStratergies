import Link from "next/link";
import { getStrategies, getEquitySeries } from "@/lib/data/strategies";
import { LeaderboardTable, type Row } from "@/components/leaderboard-table";
import { RecomputeButton } from "@/components/recompute-button";
import { RebuildAllButton } from "@/components/rebuild-all-button";

export const dynamic = "force-dynamic"; // read files at request time

export default async function LeaderboardPage() {
  const strategies = await getStrategies();
  const rows: Row[] = await Promise.all(
    strategies.map(async (s) => ({
      ...s,
      series: await getEquitySeries(s.equityCsv),
    })),
  );
  return (
    <main className="mx-auto max-w-5xl p-8">
      <div className="mb-1 flex items-center justify-between">
        <h1 className="text-2xl font-bold">Strategy Leaderboard</h1>
        <div className="flex items-center gap-2">
          <Link
            href="/strategy/new"
            className="rounded-md border px-3 py-1.5 text-sm font-medium hover:bg-accent"
          >
            + New strategy
          </Link>
          <RecomputeButton />
          <RebuildAllButton />
        </div>
      </div>
      <p className="mb-6 text-sm text-muted-foreground">
        Ranked by composite score · {rows.length} strategies
      </p>
      <LeaderboardTable rows={rows} />
    </main>
  );
}
