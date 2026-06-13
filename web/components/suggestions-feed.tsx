import Link from "next/link";
import { cn } from "@/lib/utils";
import type {
  SuggestionPick,
  SuggestionsFeed,
  SuggestionsRegime,
} from "@/lib/data/strategies";

const fmtPrice = (v: number): string =>
  `₹${v.toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;

function confidenceClass(c: number): string {
  if (c >= 60) return "text-green-500";
  if (c >= 50) return "text-amber-500";
  return "text-red-500";
}

function strategyBadgeClass(id: string): string {
  if (id === "momentum_edge") return "bg-accent-blue/15 text-accent-blue border-accent-blue/30";
  if (id === "monthly_rotation") return "bg-green-600/15 text-green-500 border-green-600/30";
  if (id === "ipo_edge") return "bg-amber-500/15 text-amber-500 border-amber-500/30";
  return "bg-muted text-muted-foreground border-border";
}

function RegimeBanner({ regime }: { regime: SuggestionsRegime }) {
  const isBull = regime.status === "Bull";
  const isUnknown = regime.status !== "Bull" && regime.status !== "Bear";
  const tone = isBull
    ? "border-green-600/40 bg-green-600/10 text-green-500"
    : isUnknown
      ? "border-border bg-muted/30 text-muted-foreground"
      : "border-red-600/40 bg-red-600/10 text-red-500";
  const msg = isBull
    ? "BULL regime — all 3 Nifty conditions on. New entries allowed."
    : isUnknown
      ? "Regime unknown — benchmark data unavailable."
      : "BEAR / SIDEWAYS regime — at least one Nifty condition is failing. Position sizes halved; IPO Edge picks suspended.";

  return (
    <div className={cn("rounded-md border px-4 py-2.5 text-sm", tone)}>
      <span className="font-medium">{msg}</span>
      {regime.close != null && (
        <span className="ml-3 text-xs text-muted-foreground">
          Nifty {regime.close.toLocaleString("en-IN")} · SMA50{" "}
          {regime.sma50?.toLocaleString("en-IN")} · SMA200{" "}
          {regime.sma200?.toLocaleString("en-IN")} ·{" "}
          {regime.pctFromHigh != null
            ? `${regime.pctFromHigh > 0 ? "+" : ""}${regime.pctFromHigh.toFixed(1)}% from 52W high`
            : ""}{" "}
          · {regime.date}
        </span>
      )}
    </div>
  );
}

function KpiTile({
  label,
  value,
  sub,
  valueClass,
}: {
  label: string;
  value: string;
  sub: string;
  valueClass?: string;
}) {
  return (
    <div className="rounded-md border border-border bg-muted/20 px-4 py-3">
      <div className="text-xs uppercase tracking-wide text-muted-foreground">{label}</div>
      <div className={cn("mt-1 text-2xl font-bold font-mono tabular-nums", valueClass)}>
        {value}
      </div>
      <div className="mt-0.5 text-xs text-muted-foreground">{sub}</div>
    </div>
  );
}

const STAT_LABEL = "text-[10px] uppercase tracking-wide text-muted-foreground";
const STAT_VALUE = "text-sm font-semibold font-mono tabular-nums";

function PickCard({ p }: { p: SuggestionPick }) {
  return (
    <div className="rounded-lg border border-border bg-muted/10 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-[10px] uppercase tracking-wide text-muted-foreground">
            #{p.rank} ·{" "}
            <Link
              href={`/strategy/${p.strategyId}`}
              className="hover:text-foreground hover:underline"
            >
              {p.strategy}
            </Link>
          </div>
          <div className="mt-0.5 text-lg font-bold">{p.ticker}</div>
          {p.company && p.company !== p.ticker && (
            <div className="text-xs text-muted-foreground">{p.company}</div>
          )}
        </div>
        <div className="text-right">
          <div className="text-[10px] uppercase tracking-wide text-muted-foreground">
            Confidence
          </div>
          <div className={cn("text-2xl font-bold font-mono tabular-nums", confidenceClass(p.confidence))}>
            {p.confidence.toFixed(0)}%
          </div>
          <div className="text-[10px] text-muted-foreground">hist. win rate · n={p.nHist}</div>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <span
          className={cn(
            "inline-block rounded border px-1.5 py-0.5 text-xs font-medium",
            strategyBadgeClass(p.strategyId),
          )}
        >
          {p.signal}
        </span>
      </div>

      <div className="mt-3 grid grid-cols-5 gap-3 border-t border-border pt-3">
        <div>
          <div className={STAT_LABEL}>Entry</div>
          <div className={STAT_VALUE}>{fmtPrice(p.close)}</div>
        </div>
        <div>
          <div className={STAT_LABEL}>Stop</div>
          <div className={cn(STAT_VALUE, "text-red-500")}>{fmtPrice(p.stop)}</div>
        </div>
        <div>
          <div className={STAT_LABEL}>Target</div>
          <div className={cn(STAT_VALUE, "text-green-500")}>{fmtPrice(p.target)}</div>
        </div>
        <div>
          <div className={STAT_LABEL}>R : R</div>
          <div className={STAT_VALUE}>1 : {p.rr.toFixed(2)}</div>
        </div>
        <div>
          <div className={STAT_LABEL}>Max size</div>
          <div className={STAT_VALUE}>{p.positionPct.toFixed(0)}%</div>
        </div>
      </div>

      <div className="mt-2 grid grid-cols-2 gap-3">
        <div>
          <div className={STAT_LABEL}>Avg hist PnL</div>
          <div className={cn(STAT_VALUE, p.avgPnl > 0 ? "text-green-500" : "text-red-500")}>
            {p.avgPnl > 0 ? "+" : ""}
            {p.avgPnl.toFixed(2)}%
          </div>
        </div>
        <div>
          <div className={STAT_LABEL}>Edge score</div>
          <div className={STAT_VALUE}>{p.edgeScore.toFixed(1)}</div>
        </div>
      </div>

      <p className="mt-3 text-xs leading-relaxed text-muted-foreground">💡 {p.rationale}</p>
    </div>
  );
}

export function SuggestionsFeedView({ feed }: { feed: SuggestionsFeed }) {
  const { regime, summary, picks } = feed;
  return (
    <div className="space-y-4">
      <RegimeBanner regime={regime} />

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <KpiTile label="Picks Today" value={`${summary.picks}`} sub="after edge + regime filter" />
        <KpiTile
          label="Avg Confidence"
          value={`${summary.avgConfidence.toFixed(0)}%`}
          sub="hist. win rate"
          valueClass={confidenceClass(summary.avgConfidence)}
        />
        <KpiTile
          label="Total Allocation"
          value={`${summary.totalAllocation.toFixed(0)}%`}
          sub="of capital deployed"
        />
        <KpiTile
          label="Cash Reserve"
          value={`${summary.cashReserve.toFixed(0)}%`}
          sub="idle (dry powder)"
          valueClass="text-green-500"
        />
      </div>

      {picks.length === 0 ? (
        <div className="rounded-md border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-500">
          No suggestions today. Either the regime is Bear and entries are gated, or no live
          signal matches an approved historical bucket. Holding cash is a position too — wait
          for the next signal.
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
          {picks.map((p) => (
            <PickCard key={`${p.strategyId}-${p.ticker}-${p.rank}`} p={p} />
          ))}
        </div>
      )}
    </div>
  );
}
