"use client";

import { RefreshCw } from "lucide-react";
import { errorHeadline } from "@/lib/desk/format";
import { useStrategyUpdate, type UpdateTarget } from "@/lib/desk/use-strategy-update";
import type { UpdateResult } from "@/lib/desk/run-update";
import { StatusPill } from "@/components/desk/primitives";

interface ViewProps {
  label: string;
  /** True while this button's own job runs. */
  busy: boolean;
  /** True while any update job runs (this one or the sidebar's). */
  disabled: boolean;
  lines: string[];
  results: UpdateResult[] | null;
  error: string | null;
  onStart: () => void;
  onDismiss: () => void;
}

/** Presentational part: button label and disabled state follow the running flag. */
export function PageUpdateButtonView(p: ViewProps) {
  return (
    <div className="desk-stack" style={{ gap: 8 }}>
      <button type="button" className="desk-btn desk-btn--primary" disabled={p.disabled} onClick={p.onStart}>
        <RefreshCw size={15} aria-hidden="true" /> {p.busy ? "Updating…" : p.label}
      </button>
      {p.busy ? (
        <div className="rd-note desk-progress" aria-live="polite">
          {p.lines.map((l, i) => <div key={i}>{l}</div>)}
        </div>
      ) : null}
      {p.error ? (
        <p className="rd-note" role="alert" style={{ color: "var(--rd-loss)" }}>
          {p.error} <button type="button" className="desk-link" onClick={p.onDismiss}>Dismiss</button>
        </p>
      ) : null}
      {p.results ? (
        <div className="rd-list" role="status">
          <div className="rd-list__head">
            Update results
            <button type="button" className="desk-link" onClick={p.onDismiss}>Dismiss</button>
          </div>
          {p.results.map((r) => (
            <div className="rd-li" key={r.strategy} style={{ alignItems: "flex-start" }}>
              <span className="rd-li__main">
                <span className="rd-li__title">{r.strategy}</span>
                {r.ok ? null : (
                  <span className="rd-li__sub desk-wrap">Failed at {r.failedStep}: {errorHeadline(r.errorTail)}</span>
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

/** Update button for one strategy page, sharing its running flag with the sidebar. */
export function PageUpdateButton({ strategy, label }: { strategy: UpdateTarget; label: string }) {
  const u = useStrategyUpdate();
  return (
    <PageUpdateButtonView label={label} busy={u.running === strategy} disabled={u.running !== null}
      lines={u.lines} results={u.results} error={u.error}
      onStart={() => u.start(strategy)} onDismiss={u.dismiss} />
  );
}
