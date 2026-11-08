import type { ReactNode } from "react";
import { bigValueParts, formatChange, type Tone } from "@/lib/desk/format";
import type { CheckRow } from "@/lib/desk/monthly-text";

/** Python status_pill. */
export function StatusPill({ label, tone = "muted" }: { label: string; tone?: Tone }) {
  return <span className={`rd-pill rd-pill--${tone}`}>{label}</span>;
}

/** Python change_pill: tinted, ↗/↘, value never altered. */
export function ChangePill({ value, decimals = 2 }: { value: number | null | undefined; decimals?: number }) {
  const { text, direction } = formatChange(value, decimals);
  return <span className={`rd-chg rd-chg--${direction}`}>{text}</span>;
}

export interface RailItem {
  key: string;
  title: ReactNode;
  sub?: string;
  value: ReactNode;
}

/** Right-rail list (rd-list): title + optional sub on the left, value or pill on the right. */
export function RailList({ title, meta, items }: { title: string; meta?: string; items: RailItem[] }) {
  return (
    <section className="rd-list" aria-label={title}>
      <div className="rd-list__head">
        {title} {meta ? <span>{meta}</span> : null}
      </div>
      {items.map((it) => (
        <div className="rd-li" key={it.key}>
          <span className="rd-li__main">
            <span className="rd-li__title">{it.title}</span>
            {it.sub ? <span className="rd-li__sub">{it.sub}</span> : null}
          </span>
          {it.value}
        </div>
      ))}
    </section>
  );
}

/** Page title + subtitle (rd-page), with optional right-hand content. */
export function PageHeader({ title, sub, right }: { title: string; sub?: string; right?: ReactNode }) {
  return (
    <header className="desk-head rd-page">
      <div>
        <h1 className="rd-page__title">{title}</h1>
        {sub ? <p className="rd-page__sub">{sub}</p> : null}
      </div>
      {right ? <div className="rd-note">{right}</div> : null}
    </header>
  );
}

/** Small section heading used above cards and tables (Streamlit _section_head). */
export function SectionHead({ title, meta, right }: { title: string; meta?: string; right?: ReactNode }) {
  return (
    <div className="desk-row">
      <h2 className="rd-list__head" style={{ border: 0, padding: 0 }}>
        {title} {meta ? <span>{meta}</span> : null}
      </h2>
      {right}
    </div>
  );
}

/** Python empty_state. */
export function EmptyState({ title, reason }: { title: string; reason?: string }) {
  return (
    <div className="rd-empty" role="status">
      <div className="rd-empty__title">{title}</div>
      {reason ? <div className="rd-empty__reason">{reason}</div> : null}
    </div>
  );
}

/** Python context_bar: one line stating what a result belongs to. */
export function ContextBar({ items, basis }: { items: [string, string][]; basis?: string }) {
  return (
    <div className="rd-ctx" role="group" aria-label="Result context">
      {items.map(([k, v]) => (
        <span className="rd-ctx__item" key={k}>
          <span className="rd-ctx__label">{k}</span>
          <span className="rd-ctx__value">{v}</span>
        </span>
      ))}
      {basis ? <span className="rd-ctx__basis">{basis}</span> : null}
    </div>
  );
}

/** Python big_value: large headline number with smaller decimals. */
export function BigValue({ text, tone }: { text: string; tone?: Tone }) {
  const { head, dec } = bigValueParts(text);
  return (
    <span className={tone ? `rd-big rd-big--${tone}` : "rd-big"}>
      {head}
      {dec !== null ? <span className="rd-big__dec">{dec}</span> : null}
    </span>
  );
}

/** Python stat_bar: label/value row with a coloured left bar. */
export function StatBar({ label, value, tone = "muted" }: { label: string; value: string; tone?: Tone }) {
  return (
    <div className={`rd-bar rd-bar--${tone}`}>
      <span>{label}</span>
      <span className="rd-bar__val">{value}</span>
    </div>
  );
}

/** Python validation_checklist: research checks with an honest status pill. */
export function Checklist({ checks }: { checks: CheckRow[] }) {
  return (
    <ul className="rd-checks" aria-label="Validation status">
      {checks.map((c) => (
        <li className="rd-check" key={c.title}>
          <span className="rd-check__title">{c.title}</span>
          <StatusPill label={c.label} tone={c.tone} />
          {c.note ? <span className="rd-check__note">{c.note}</span> : null}
        </li>
      ))}
    </ul>
  );
}
