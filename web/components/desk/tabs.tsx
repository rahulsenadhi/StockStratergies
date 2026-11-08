"use client";

import { useRef, useState, type KeyboardEvent, type ReactNode } from "react";

export interface TabItem {
  id: string;
  label: string;
  content: ReactNode;
}

/** Accessible tab strip: Left/Right arrows move and select; only the selected panel renders. */
export function Tabs({ tabs, value, onChange }: { tabs: TabItem[]; value?: string; onChange?: (id: string) => void }) {
  const [own, setOwn] = useState(tabs[0]?.id ?? "");
  // Controlled when `value` is given (the caller owns the selection); otherwise the strip keeps its own.
  const selected = value ?? own;
  const setSelected = (id: string) => { setOwn(id); onChange?.(id); };
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});

  const onKeyDown = (e: KeyboardEvent<HTMLButtonElement>, index: number) => {
    if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
    e.preventDefault();
    const step = e.key === "ArrowRight" ? 1 : -1;
    const next = tabs[(index + step + tabs.length) % tabs.length];
    setSelected(next.id);
    refs.current[next.id]?.focus();
  };

  const active = tabs.find((t) => t.id === selected) ?? tabs[0];
  return (
    <div className="desk-tabs">
      <div role="tablist">
        {tabs.map((t, i) => (
          <button
            key={t.id}
            ref={(el) => { refs.current[t.id] = el; }}
            id={`tab-${t.id}`}
            type="button"
            role="tab"
            aria-selected={t.id === active?.id}
            aria-controls={`panel-${t.id}`}
            tabIndex={t.id === active?.id ? 0 : -1}
            onClick={() => setSelected(t.id)}
            onKeyDown={(e) => onKeyDown(e, i)}
          >
            {t.label}
          </button>
        ))}
      </div>
      {active ? (
        <div role="tabpanel" id={`panel-${active.id}`} aria-labelledby={`tab-${active.id}`}>
          {active.content}
        </div>
      ) : null}
    </div>
  );
}
