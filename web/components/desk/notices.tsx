import { formatPlain, type Tone } from "@/lib/desk/format";
import type { PriceFreshness, Regime } from "@/lib/desk/snapshot";
import { StatusPill } from "@/components/desk/primitives";

/** Exact text of core/workflow_ui.research_notice(). */
export const RESEARCH_NOTICE =
  "Historical simulation • These are model results, not your account performance. " +
  "Trading costs and performance on previously unseen periods are not verified for this report. " +
  "A best holding period has not yet been established.";

export function ResearchNotice() {
  return <p className="rd-note">{RESEARCH_NOTICE}</p>;
}

/** Banner message per regime, as master_dashboard._render_regime_banner. */
function regimeMessage(status: string | undefined): { text: string; tone: Tone } {
  if (status === "Bull") return { text: "BULL — all 3 regime conditions on. New entries allowed.", tone: "gain" };
  if (status === "Bear") return { text: "BEAR / SIDEWAYS — at least one regime condition has failed.", tone: "loss" };
  return { text: "Regime unknown — benchmark data unavailable.", tone: "info" };
}

/** Freshness chip: green under 24h, amber under 72h, red after (same thresholds as Streamlit). */
function freshnessChip(f: PriceFreshness): { label: string; tone: Tone } {
  const age = f.age_hours;
  if (age == null) return { label: "No data", tone: "muted" };
  if (age < 24) return { label: `${age.toFixed(1)}h ago`, tone: "gain" };
  if (age < 72) return { label: `${age.toFixed(0)}h ago`, tone: "warn" };
  return { label: `${(age / 24).toFixed(0)}d ago`, tone: "loss" };
}

/** "Market context and price-data status" disclosure shown above every page. */
export function MarketContext({ regime, freshness }: { regime: Regime; freshness: PriceFreshness }) {
  const msg = regimeMessage(regime.status);
  const chip = freshnessChip(freshness);
  const hasClose = regime.close != null && regime.sma50 != null && regime.sma200 != null;
  return (
    <details className="desk-disclosure">
      <summary>Market context and price-data status</summary>
      <div className="desk-stack" style={{ gap: 8 }}>
        <p className="rd-note">
          This describes the broad stock market and saved price files. Earnings dates and update status appear on
          the PEAD page. Each strategy has its own entry rules; this market label does not apply the same
          restriction to every strategy.
        </p>
        <div className="desk-row" style={{ justifyContent: "flex-start" }}>
          <StatusPill label={msg.text} tone={msg.tone} />
          <span className="rd-note">{regime.bars_since_flip ?? 0} bars since last flip</span>
          {hasClose ? (
            <span className="rd-note">
              Nifty <b>{formatPlain(regime.close!)}</b> · SMA50 <b>{formatPlain(regime.sma50!)}</b> · SMA200{" "}
              <b>{formatPlain(regime.sma200!)}</b> · {(regime.pct_from_high ?? 0) >= 0 ? "+" : ""}
              {(regime.pct_from_high ?? 0).toFixed(1)}% from 52W high · {regime.date}
            </span>
          ) : null}
          <span title={`Last bar ${freshness.latest_bar ?? "—"} · File saved ${freshness.file_mtime ?? "—"}`}>
            <StatusPill label={`● Data updated ${chip.label} · last bar ${freshness.latest_bar ?? "—"}`} tone={chip.tone} />
          </span>
        </div>
        <p className="rd-note">
          Nifty is the market reference. SMA50 and SMA200 are average prices over 50 and 200 trading days. A bar is
          one trading session; the 52-week high is the highest price in that period.
        </p>
      </div>
    </details>
  );
}
