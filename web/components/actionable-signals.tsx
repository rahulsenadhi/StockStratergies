import { getActionableSignals } from "@/lib/data/strategies";
import { cn } from "@/lib/utils";

function actionBadgeClass(action: string): string {
  if (action === "BUY NOW") return "bg-green-600/15 text-green-500 border-green-600/30";
  if (action === "WATCH") return "bg-amber-500/15 text-amber-500 border-amber-500/30";
  if (action === "FORMING") return "bg-sky-500/15 text-sky-400 border-sky-500/30";
  return "bg-muted text-muted-foreground border-border";
}

const fmtPrice = (v: number | null): string =>
  v == null ? "—" : `₹${v.toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
const fmtNum = (v: number | null): string => (v == null ? "—" : v.toFixed(2));
const fmtSignedPct = (v: number | null): string =>
  v == null ? "—" : `${v.toFixed(2)}%`;

const TH = "px-2 py-1 text-xs font-medium uppercase text-muted-foreground";
const THR = `${TH} text-right`;
const TD = "px-2 py-1";
const TDR = `${TD} text-right tabular-nums`;

export async function ActionableSignals({ csv }: { csv: string }) {
  const rows = await getActionableSignals(csv);
  if (!rows.length) {
    return <p className="text-sm text-muted-foreground">No live signals right now.</p>;
  }

  return (
    <section>
      <h3 className="text-sm font-semibold">Live Signals — what to buy</h3>
      <p className="mb-2 text-xs text-muted-foreground">
        BUY NOW = breakout today · WATCH = near breakout · FORMING = building. Stop = 15% hard stop.
      </p>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border">
              <th className={`${TH} text-left`}>Action</th>
              <th className={`${TH} text-left`}>Ticker</th>
              <th className={THR}>Close</th>
              <th className={THR}>Stop</th>
              <th className={THR}>Score</th>
              <th className={`${TH} text-left`}>Entry Type</th>
              <th className={THR}>Dist ATH%</th>
              <th className={`${TH} text-left`}>Recovery</th>
              <th className={THR}>Vol Ratio</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} className="border-b border-border hover:bg-muted/40">
                <td className={TD}>
                  <span
                    className={cn(
                      "inline-block rounded border px-1.5 py-0.5 text-xs font-medium",
                      actionBadgeClass(r.action),
                    )}
                  >
                    ● {r.action}
                  </span>
                </td>
                <td className={TD}>
                  <span className="font-bold">{r.ticker}</span>
                  <span className="block text-xs text-muted-foreground">{r.company}</span>
                </td>
                <td className={TDR}>{fmtPrice(r.close)}</td>
                <td className={TDR}>
                  {fmtPrice(r.stopPrice)}
                  <span className="ml-1 text-xs text-muted-foreground">−15%</span>
                </td>
                <td className={TDR}>{fmtNum(r.score)}</td>
                <td className={TD}>{r.entryType}</td>
                <td className={TDR}>{fmtSignedPct(r.distAthPct)}</td>
                <td className={TD}>{r.recovery}</td>
                <td className={TDR}>{fmtNum(r.volRatio)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
