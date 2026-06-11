# Restore Slice 1 — Glossary + Plain-English + Tooltips

> Subagent-driven. Additive into the existing dense layout — NO restyle (see feedback-dashboard-density). Faithful port of Streamlit `core/glossary.py` + `_explain_box`/`_tip_box`.

**Goal:** Bring the Streamlit explanatory layer to the Next.js app: a 30-term glossary, hover tooltips on KPI labels, a glossary page, and per-strategy "How it works"/risk explainer text — all plain-English (user priority).

**Architecture:** Static glossary data in TS (no data load). A zero-dep `<Term>` tooltip using native `title` (matches Streamlit's `title=` + dotted underline). A `/glossary` page + Nav link. Per-strategy explainer copy ported verbatim from `master_dashboard.py`.

**Source of truth:** `core/glossary.py` (TERMS dict, 30 terms), `master_dashboard.py` `_explain_box`/`_tip_box` calls (lines ~5942, 6064, 6297, 6437, 6524, 7894 — read for exact per-strategy copy).

---

## Task 1: glossary data + helpers
**Files:** Create `web/lib/glossary.ts`, `web/tests/glossary.test.ts`.

- [ ] Step 1 — failing test `web/tests/glossary.test.ts`:
```typescript
import { describe, it, expect } from "vitest";
import { GLOSSARY, glossaryTerm, glossaryLabel } from "@/lib/glossary";

describe("glossary", () => {
  it("has the core terms", () => {
    expect(GLOSSARY.CAGR.label).toMatch(/Compound Annual Growth/);
    expect(GLOSSARY.MAE.label).toMatch(/Max Adverse/);
    expect(Object.keys(GLOSSARY).length).toBeGreaterThanOrEqual(30);
  });
  it("glossaryTerm returns explanation, falls back to key", () => {
    expect(glossaryTerm("Sharpe")).toMatch(/volatility/);
    expect(glossaryTerm("NOPE")).toBe("NOPE");
  });
  it("glossaryLabel returns full label, falls back to key", () => {
    expect(glossaryLabel("EMA220")).toMatch(/220-day/);
    expect(glossaryLabel("NOPE")).toBe("NOPE");
  });
});
```
- [ ] Step 2 — run → fail (no module).
- [ ] Step 3 — implement `web/lib/glossary.ts`: port ALL 30 entries from `core/glossary.py` `TERMS` verbatim into:
```typescript
export interface GlossaryEntry { label: string; explain: string; }
export const GLOSSARY: Record<string, GlossaryEntry> = {
  SMA50: { label: "50-day Simple Moving Average", explain: "Average closing price over the last 50 trading days. Tracks short-term trend." },
  // … all 30 terms from core/glossary.py (key → {label, explain}) …
};
export function glossaryTerm(key: string): string { return GLOSSARY[key]?.explain ?? key; }
export function glossaryLabel(key: string): string { return GLOSSARY[key]?.label ?? key; }
```
(Read `core/glossary.py` and copy every term: SMA50, SMA150, SMA200, EMA10, EMA220, ATR, Choppiness, 52W_High, ATH, Momentum_6M, RS, Regime_Filter, Bull_Regime, Bear_Regime, F1_to_F6, Base_Breakout, Partial_Booking, Hard_Stop, Trailing_Stop, Recovery_Speed, Entry_Type, Score, MAE, MFE, CAGR, Drawdown, Sharpe, Win_Rate. Keys with a leading digit like `52W_High` must be quoted.)
- [ ] Step 4 — run → pass.
- [ ] Step 5 — commit: `feat(restore): glossary data + term/label helpers`

## Task 2: Term tooltip + glossary page + nav link
**Files:** Create `web/components/ui/term.tsx`, `web/app/glossary/page.tsx`; modify `web/components/nav.tsx`.

- [ ] Term component (`term.tsx`):
```tsx
import { GLOSSARY } from "@/lib/glossary";
import { cn } from "@/lib/utils";

export function Term({ k, children, className }: { k: string; children?: React.ReactNode; className?: string }) {
  const entry = GLOSSARY[k];
  if (!entry) return <>{children ?? k}</>;
  return (
    <span title={entry.explain} className={cn("cursor-help underline decoration-dotted underline-offset-2", className)}>
      {children ?? entry.label}
    </span>
  );
}
```
- [ ] Glossary page (`app/glossary/page.tsx`): server component, dense table — for each `GLOSSARY` entry sorted by key: term key · full label · explanation. Plain `<table>` styled like existing tables (compact). Page heading "Glossary".
- [ ] Nav: add a third link "Glossary" → `/glossary` (active when pathname === "/glossary"); keep the existing compact nav style (this is the OLD nav restored after revert — match its markup).
- [ ] tsc clean. Commit: `feat(restore): Term tooltip + /glossary page + nav link`

## Task 3: wire tooltips into KPI labels
**Files:** Modify `web/components/kpi-strip.tsx`, `web/components/home-kpi-strip.tsx`, `web/components/leaderboard-table.tsx`.

- [ ] Read each. Wrap the KPI **labels** (not values) in `<Term k="...">`: CAGR→`CAGR`, Sharpe→`Sharpe`, Max Drawdown→`Drawdown`, Win Rate→`Win_Rate`, Alpha→(no term; leave or add). In `leaderboard-table.tsx` wrap the column header text for CAGR/Sharpe/MaxDD/WinRate in `<Term>` (keep the sort click working — Term is just inline text inside the header button; native `title` on the span is fine).
- [ ] Behavior unchanged (sorting, values). tsc clean. Commit: `feat(restore): glossary tooltips on KPI labels`

## Task 4: per-strategy plain-English explainer
**Files:** Create `web/components/strategy-explainer.tsx`; modify `web/app/strategy/[id]/page.tsx`.

- [ ] Read `master_dashboard.py` `_explain_box`/`_tip_box` calls (lines ~5942/6064/6297/6437/6524/7894) and lift the exact per-strategy "How it works" + risk-disclaimer copy for each of the 4 strategies (monthly_rotation, ipo_edge, momentum_edge, pead).
- [ ] `strategy-explainer.tsx`: a server component `<StrategyExplainer id={id} />` with a `Record<id, { how: string; risk?: string }>` of the lifted copy; renders a compact bordered "How it works" block + an optional muted risk line. Dense (small text, thin border — match existing `rounded border bg-muted` style, NOT big cards). Unknown id → null.
- [ ] Detail page: render `<StrategyExplainer id={s.id} />` near the top (after the title/KPIs, before the equity section).
- [ ] tsc clean; `npx next build` clean. Commit: `feat(restore): per-strategy plain-English explainer`

## Task 5: verify + finish
- [ ] (web/) `npx vitest run` (165 + glossary tests green); `npx tsc --noEmit`; `npx next build` clean.
- [ ] Runtime: `/glossary` 200 + lists terms; KPI labels show dotted underline + hover title; detail page shows explainer text; nav Glossary link active.
- [ ] Update `streamlit_feature_restore_program.md` (slice 1 DONE). Finish branch (merge main + push).

---

## Self-Review
Covers: glossary data (T1) ✓, tooltip+page+nav (T2) ✓, KPI tooltips (T3) ✓, explainer copy (T4) ✓, verify (T5) ✓. Additive only — no restyle, no big cards (dense `rounded border bg-muted`). Tooltip = native `title` (zero-dep). Copy ported verbatim from Streamlit. `Term` k-keys match `glossary.ts` keys.
