import { getStrategies, getEquitySeries } from "@/lib/data/strategies";
import { LeaderboardTable, type Row } from "@/components/leaderboard-table";
import { RecomputeButton } from "@/components/recompute-button";

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
        <RecomputeButton />
      </div>
      <p className="mb-6 text-sm text-muted-foreground">
        Ranked by composite score · {rows.length} strategies
      </p>
      <LeaderboardTable rows={rows} />
    </main>
  );
}
