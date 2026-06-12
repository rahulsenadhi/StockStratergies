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
    <main className="mx-auto max-w-7xl px-6 py-4">
      <div className="mb-1 flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">
            Strategy Leaderboard
          </h1>
          <p className="text-xs text-muted-foreground">
            Ranked by composite score · {rows.length}{" "}
            {rows.length === 1 ? "strategy" : "strategies"}
          </p>
        </div>
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
      <div className="mt-3 rounded-lg border border-border overflow-hidden">
        <LeaderboardTable rows={rows} />
      </div>
    </main>
  );
}
