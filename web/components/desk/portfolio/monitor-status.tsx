import { StatusPill } from "@/components/desk/primitives";
import { SCHEDULER_NOTICE, stamp, type PortfolioView } from "@/lib/desk/portfolio-text";

export function MonitorStatus({ monitor, busy, onCheck }: { monitor: PortfolioView["monitor"]; busy: boolean; onCheck: () => void }) {
  return <section className="desk-card desk-stack" aria-label="Monitoring status">
    <div className="desk-row"><div><div className="rd-stat-label">Last successful check</div>
      <strong>{stamp(monitor.last_good_check)}</strong>{" "}<StatusPill label={monitor.ok ? "Check saved" : "Check needed"} tone={monitor.ok ? "info" : "warn"} /></div>
      <button type="button" className="desk-btn" disabled={busy} onClick={onCheck}>{busy ? "Working…" : "Check holdings now"}</button></div>
    <p className="rd-note">{SCHEDULER_NOTICE} Checks use saved prices; use Update all data for new prices.</p>
    {monitor.last_run && !monitor.ok ? <p className="rd-note">Last attempt: {stamp(monitor.last_run)}</p> : null}
    {monitor.errors.map((error, i) => <p key={i} role="alert" className="portfolio-error">{error}</p>)}
  </section>;
}
