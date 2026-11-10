import { SectionHead, StatusPill } from "@/components/desk/primitives";
import { actionTone, stamp, type PortfolioAlert } from "@/lib/desk/portfolio-text";

export function AlertsList({ alerts, busy, onAcknowledge }: { alerts: PortfolioAlert[]; busy: boolean; onAcknowledge: (id: string) => void }) {
  const pending = alerts.filter((a) => !a.acknowledged_at).slice().reverse();
  return <section className="desk-stack" aria-label="Alerts"><SectionHead title="Alerts" meta={`${pending.length} unacknowledged`} />
    <p className="rd-note">Acknowledging records that you saw an alert. Record a sale separately after you sell. Earlier alerts may differ from the latest holding check.</p>
    {pending.length ? <div className="rd-list">{pending.map((a) => <div className="rd-li portfolio-alert" key={a.id}>
      <div className="rd-li__main"><strong>{a.symbol}</strong>{" "}<StatusPill label={a.action} tone={actionTone(a.action)} />
        <p className="rd-note">{a.rule ?? "Data check"} · Bar: {a.trigger_bar_date ?? "unavailable"}</p>
        <p className="portfolio-copy">{a.message}</p><span className="rd-li__sub">Raised {stamp(a.created_at)}</span></div>
      <button type="button" className="desk-btn" disabled={busy} onClick={() => onAcknowledge(a.id)}>Acknowledge</button>
    </div>)}</div> : <p className="rd-note">No unacknowledged alerts.</p>}
  </section>;
}
