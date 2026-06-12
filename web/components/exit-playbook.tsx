import { getExitPlaybook } from "@/lib/data/strategies";
import { Sparkline } from "@/components/sparkline";

export async function ExitPlaybook({ id }: { id: string }) {
  const rec = await getExitPlaybook(id);
  if (!rec) {
    return (
      <p className="text-sm text-muted-foreground">
        Exit Playbook: insufficient trade history yet.
      </p>
    );
  }

  const t = rec.targets;
  const summary =
    t.length >= 3
      ? `Hold ~${Math.round(rec.holdDays)}d · T1/T2/T3 +${Math.round(t[0].pct)}%/+${Math.round(t[1].pct)}%/+${Math.round(t[2].pct)}% · Stop ${Math.round(rec.stopPct)}%`
      : `Hold ~${Math.round(rec.holdDays)}d · targets n/a · Stop ${Math.round(rec.stopPct)}%`;

  const dataLabel =
    rec.dataQuality === "ohlcv" ? "intraday OHLCV" : "close-only (approx.)";

  return (
    <div className="space-y-2 text-sm">
      <h3 className="text-sm font-semibold">Exit Playbook</h3>
      <p className="text-xs text-muted-foreground">{summary}</p>
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
        <span>
          Recommended hold{" "}
          <span className="font-medium text-foreground">{rec.holdDays} days</span>
        </span>
        <span>
          Median return at hold{" "}
          <span className="font-medium text-foreground">
            {rec.holdMedianReturn.toFixed(1)}%
          </span>
        </span>
        <span>
          Win rate at hold{" "}
          <span className="font-medium text-foreground">
            {(rec.holdWinRate * 100).toFixed(0)}%
          </span>
        </span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full caption-bottom text-xs">
          <thead>
            <tr className="border-b border-border">
              <th className="px-3 py-1.5 text-left text-xs font-medium uppercase tracking-wide whitespace-nowrap text-muted-foreground">
                Tier
              </th>
              <th className="px-3 py-1.5 text-right text-xs font-medium uppercase tracking-wide whitespace-nowrap text-muted-foreground">
                Profit target
              </th>
              <th className="px-3 py-1.5 text-right text-xs font-medium uppercase tracking-wide whitespace-nowrap text-muted-foreground">
                Book
              </th>
              <th className="px-3 py-1.5 text-right text-xs font-medium uppercase tracking-wide whitespace-nowrap text-muted-foreground">
                Hit rate (hist.)
              </th>
            </tr>
          </thead>
          <tbody>
            {rec.targets.map((tgt, i) => (
              <tr
                key={i}
                className="border-b border-border transition-colors last:border-0 hover:bg-muted/40 odd:bg-muted/10"
              >
                <td className="px-3 py-1.5 whitespace-nowrap text-muted-foreground">
                  T{i + 1}
                </td>
                <td className="px-3 py-1.5 text-right font-mono tabular-nums whitespace-nowrap">
                  +{tgt.pct.toFixed(1)}%
                </td>
                <td className="px-3 py-1.5 text-right font-mono tabular-nums whitespace-nowrap">
                  {tgt.bookPct}%
                </td>
                <td className="px-3 py-1.5 text-right font-mono tabular-nums whitespace-nowrap">
                  {(tgt.hitRate * 100).toFixed(0)}%
                </td>
              </tr>
            ))}
          </tbody>
          <caption className="mt-2 text-left text-xs text-muted-foreground">
            Stop {rec.stopPct.toFixed(1)}% · sample {rec.sampleSize} trades · data {dataLabel}
          </caption>
        </table>
      </div>
      {rec.curve.length >= 2 && (
        <div className="flex items-center gap-2">
          <Sparkline points={rec.curve.map((c) => c.median)} width={96} height={24} />
          <span className="text-xs text-muted-foreground">median return by day</span>
        </div>
      )}
    </div>
  );
}
