"use client";

import { RefreshCw, SlidersHorizontal } from "lucide-react";
import { useStrategyUpdate } from "@/lib/desk/use-strategy-update";
import { errorHeadline, freshnessLabel, freshnessTone } from "@/lib/desk/format";
import { oldestAge, type SavedAge } from "@/lib/desk/ages";
import { UPDATE_STRATEGIES } from "@/lib/desk/update-steps";
import { StatusPill } from "@/components/desk/primitives";

/** Sidebar bottom block, always visible: data age, Update all data, Update one strategy. */
export function UpdatePanel({ ages }: { ages: SavedAge[] }) {
  const { running, lines, results, error, start, dismiss } = useStrategyUpdate();

  const oldest = oldestAge(ages);
  const ageLine = oldest == null ? null
    : oldest.ageDays === 0 ? "All saved data updated today"
      : `Oldest saved data: ${oldest.name}, ${freshnessLabel(oldest.ageDays)}`;

  return (
    <div className="desk-pinned">
      <p className="rd-note">
        Research only. Review a company, its rules and the historical evidence. No orders are placed here.
      </p>
      {ageLine ? <p className="rd-note">{ageLine}</p> : null}
      <button type="button" className="desk-btn desk-btn--primary" disabled={running !== null} onClick={() => start("all")}>
        <RefreshCw size={15} aria-hidden="true" /> {running === "all" ? "Updating…" : "Update all data"}
      </button>
      <details className="desk-disclosure">
        <summary className="desk-summary">
          <SlidersHorizontal size={14} aria-hidden="true" /> Update one strategy
        </summary>
        <div className="desk-stack" style={{ gap: 8 }}>
          <p className="rd-note">
            Monthly, IPO and Momentum update prices and simulations. PEAD requests earnings data and updates its
            saved candidates.
          </p>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6 }}>
            {UPDATE_STRATEGIES.map((s) => (
              <button key={s} type="button" className="desk-btn" disabled={running !== null} onClick={() => start(s)}>
                {running === s ? "Updating…" : s}
              </button>
            ))}
          </div>
          <div className="rd-list">
            <div className="rd-list__head">Last updated</div>
            {ages.map((a) => (
              <div className="rd-li" key={a.name}>
                <span className="rd-li__title">{a.name}</span>
                <StatusPill label={freshnessLabel(a.ageDays)} tone={freshnessTone(a.ageDays)} />
              </div>
            ))}
          </div>
        </div>
      </details>
      {running ? (
        <div className="rd-note desk-progress" aria-live="polite">
          {lines.map((l, i) => <div key={i}>{l}</div>)}
        </div>
      ) : null}
      {error ? <p className="rd-note" role="alert" style={{ color: "var(--rd-loss)" }}>{error}</p> : null}
      {results ? (
        <div className="rd-list" role="status">
          <div className="rd-list__head">
            Update results
            <button type="button" className="desk-link" onClick={dismiss}>Dismiss</button>
          </div>
          {results.map((r) => (
            <div className="rd-li" key={r.strategy} style={{ alignItems: "flex-start" }}>
              <span className="rd-li__main">
                <span className="rd-li__title">{r.strategy}</span>
                {r.ok ? null : (
                  <>
                    <span className="rd-li__sub desk-wrap">Failed at {r.failedStep}: {errorHeadline(r.errorTail)}</span>
                    <details>
                      <summary className="rd-li__sub" style={{ cursor: "pointer" }}>Full message</summary>
                      <pre className="rd-li__sub desk-wrap" style={{ margin: 0, fontFamily: "inherit" }}>{r.errorTail}</pre>
                    </details>
                  </>
                )}
              </span>
              <StatusPill label={r.ok ? "updated" : "failed"} tone={r.ok ? "gain" : "loss"} />
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
