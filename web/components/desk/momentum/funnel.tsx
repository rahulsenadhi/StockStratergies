import { formatNumber } from "@/lib/desk/format";
import { FUNNEL_LABELS, type FunnelData } from "@/lib/desk/momentum-text";

/** Python _chart_me_funnel: one bar per filter step, width = count / universe; the last step is tinted. */
export function Funnel({ funnel }: { funnel: FunnelData }) {
  const last = funnel.steps.length - 1;
  return (
    <div className="desk-card desk-funnel" role="list" aria-label="Filter funnel">
      {funnel.steps.map((s, i) => {
        const pct = funnel.total > 0 ? Math.min(100, (s.count / funnel.total) * 100) : 0;
        const tone = i === last ? (funnel.is_bull ? " desk-funnel__fill--gain" : " desk-funnel__fill--loss") : "";
        return (
          <div key={s.key} role="listitem" style={{ display: "contents" }}>
            <span>{FUNNEL_LABELS[s.key] ?? s.key}</span>
            <span className="desk-funnel__track" aria-hidden="true">
              <span className={`desk-funnel__fill${tone}`} style={{ width: `${pct}%` }} />
            </span>
            <span className="desk-funnel__val">{formatNumber(s.count, 0)}</span>
          </div>
        );
      })}
    </div>
  );
}
