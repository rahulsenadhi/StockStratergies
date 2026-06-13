import { getMonthlyReturns, getEquityWithBenchmark } from "@/lib/data/strategies";
import { annualReturns, buildHistoryProof } from "@/lib/history-proof";
import { cn } from "@/lib/utils";

const fmtRs = (v: number): string =>
  `₹${v.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
const fmtPct = (v: number | null): string =>
  v == null ? "—" : `${v >= 0 ? "+" : ""}${(v * 100).toFixed(1)}%`;
const retClass = (v: number | null): string =>
  v == null ? "text-muted-foreground" : v >= 0 ? "text-green-500" : "text-red-500";

const STAT_LABEL = "text-[10px] uppercase tracking-wide text-muted-foreground";
const STAT_VALUE = "text-lg font-bold font-mono tabular-nums";
const TH = "px-3 py-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground";
const THR = `${TH} text-right`;

export async function HistoryProofSection({
  equityCsv,
  totalReturn,
}: {
  equityCsv: string | null;
  totalReturn: number | null;
}) {
  const monthly = await getMonthlyReturns(equityCsv);
  const strategyAnnual = new Map<number, number>();
  for (const r of monthly) {
    if (r.annual != null) strategyAnnual.set(r.year, r.annual);
  }
  const { benchmark } = await getEquityWithBenchmark(equityCsv);
  const benchmarkAnnual = annualReturns(benchmark);
  const h = buildHistoryProof(strategyAnnual, benchmarkAnnual, totalReturn);

  if (h.nYears === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        History &amp; Proof: not enough yearly data yet.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      <div>
        <h3 className="text-sm font-semibold">History &amp; Proof — did it actually make money?</h3>
        <p className="text-xs text-muted-foreground">
          {h.nYears} year{h.nYears !== 1 ? "s" : ""} of record · {h.yearRange}
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <div className="rounded-md border border-border bg-muted/20 px-3 py-2.5">
          <div className={STAT_LABEL}>₹1 lakh grew to</div>
          <div className={cn(STAT_VALUE, "text-green-500")}>
            {h.growth1L != null ? fmtRs(h.growth1L) : "—"}
          </div>
        </div>
        <div className="rounded-md border border-border bg-muted/20 px-3 py-2.5">
          <div className={STAT_LABEL}>Avg yearly return</div>
          <div className={cn(STAT_VALUE, retClass(h.avgYearly))}>{fmtPct(h.avgYearly)}</div>
        </div>
        <div className="rounded-md border border-border bg-muted/20 px-3 py-2.5">
          <div className={STAT_LABEL}>Beat Nifty</div>
          <div className={STAT_VALUE}>
            {h.beatTotal ? `${h.beatCount} of ${h.beatTotal} yrs` : "—"}
          </div>
        </div>
        <div className="rounded-md border border-border bg-muted/20 px-3 py-2.5">
          <div className={STAT_LABEL}>Worst year</div>
          <div className={cn(STAT_VALUE, "text-red-500")}>{fmtPct(h.worstYear)}</div>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border">
              <th className={`${TH} text-left`}>Year</th>
              <th className={THR}>Strategy</th>
              <th className={THR}>Nifty</th>
              <th className={`${TH} text-right`}>Verdict</th>
            </tr>
          </thead>
          <tbody>
            {h.rows.map((r, i) => (
              <tr
                key={r.year}
                className={cn(
                  "border-b border-border transition-colors last:border-0 hover:bg-muted/40",
                  i % 2 !== 0 && "bg-muted/10",
                )}
              >
                <td className="px-3 py-1.5 font-mono tabular-nums">{r.year}</td>
                <td className={cn("px-3 py-1.5 text-right font-mono tabular-nums", retClass(r.strategyRet))}>
                  {fmtPct(r.strategyRet)}
                </td>
                <td className={cn("px-3 py-1.5 text-right font-mono tabular-nums", retClass(r.benchmarkRet))}>
                  {fmtPct(r.benchmarkRet)}
                </td>
                <td className="px-3 py-1.5 text-right">
                  {r.beat == null ? (
                    <span className="text-xs text-muted-foreground">—</span>
                  ) : r.beat ? (
                    <span className="text-xs font-medium text-green-500">Beat</span>
                  ) : (
                    <span className="text-xs font-medium text-red-500">Lagged</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
