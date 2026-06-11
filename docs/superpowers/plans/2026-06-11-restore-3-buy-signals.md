# Restore Slice 3 — Actionable BUY NOW signals (Momentum Edge)

> Subagent-driven. Additive, dense — NO restyle. Faithful port of the :8500 momentum live-signal "what to buy now" screen. **NOTE: the semantic color tokens (text-success/warning/info) were REVERTED — use plain Tailwind colors (green/amber/blue) matching existing components like kpi-cell (`text-green-500`/`text-red-500`).**

**Goal:** Turn the momentum live signals into an actionable buy table: per ticker — Action badge (BUY NOW / WATCH / FORMING), Close ₹, suggested Stop ₹ (−15% hard stop) + Stop %, Score, Entry Type, Dist-ATH%, Recovery, Vol Ratio. The core buying screen from master_dashboard.

**Data:** `momentum_edge_signals.csv` (repo root; = momentum_edge's `live_signals_csv`). Columns: `Ticker,Company,Signal,Close,ATH (₹),Dist ATH%,Entry Type,Chart Qual,Choppiness,Recovery,220 EMA,52W High,vs High%,Vol Ratio,Score`.

**Faithful logic (from master_dashboard.py):**
- Action from Signal (`_action_from_signal` 2952-2956): `"Breakout Today"→"BUY NOW"`, `"Near Breakout"→"WATCH"`, `"Watch Zone"→"FORMING"`, else the signal string or "—".
- Stop ₹ = `Close × 0.85` (15% hard stop, line 4120 `round(close_now*0.85, 2)`); Stop % = −15.

---

## Task 1: getActionableSignals loader
**Files:** Modify `web/lib/data/strategies.ts`; create `web/tests/actionable-signals.test.ts`.

- [ ] Step 1 — failing test (temp-dir fixture; mirror existing CSV-loader tests). Seed a CSV with the real header + 2 rows (one `Breakout Today`, one `Watch Zone`):
```typescript
import { describe, it, expect } from "vitest";
import path from "node:path"; import os from "node:os"; import { promises as fsp } from "node:fs";
import { getActionableSignals } from "@/lib/data/strategies";

async function seed(): Promise<string> {
  const dir = await fsp.mkdtemp(path.join(os.tmpdir(), "act-"));
  await fsp.writeFile(path.join(dir, "sig.csv"),
    "Ticker,Company,Signal,Close,ATH (₹),Dist ATH%,Entry Type,Chart Qual,Choppiness,Recovery,220 EMA,52W High,vs High%,Vol Ratio,Score\n" +
    "ABC,ABC Ltd,Breakout Today,100,110,-9.1,52W High,Clean ✅,40,Fast 🟢,90,110,-9.1,1.2,55\n" +
    "XYZ,XYZ Ltd,Watch Zone,200,260,-23,52W High,Clean ✅,50,Slow,180,260,-23,0.5,40\n");
  return dir;
}

describe("getActionableSignals", () => {
  it("maps Signal→Action, derives Stop ₹ at -15%, parses cols", async () => {
    const dir = await seed();
    const rows = await getActionableSignals("sig.csv", dir);
    expect(rows).toHaveLength(2);
    const a = rows[0];
    expect(a.ticker).toBe("ABC");
    expect(a.action).toBe("BUY NOW");
    expect(a.close).toBeCloseTo(100);
    expect(a.stopPrice).toBeCloseTo(85);   // 100 * 0.85
    expect(a.stopPct).toBe(-15);
    expect(a.score).toBeCloseTo(55);
    expect(a.entryType).toBe("52W High");
    expect(rows[1].action).toBe("FORMING"); // Watch Zone
  });
  it("returns [] when the file is missing", async () => {
    const dir = await fsp.mkdtemp(path.join(os.tmpdir(), "act-empty-"));
    expect(await getActionableSignals("nope.csv", dir)).toEqual([]);
  });
});
```
- [ ] Step 2 — run → fail.
- [ ] Step 3 — implement in `web/lib/data/strategies.ts`. Reuse the module's existing CSV parsing (`parseCsvLines` helper, case-insensitive header lookup) + `dataDir`/`DATA_DIR` resolution like sibling loaders. Read the file first to match conventions.
```typescript
export type SignalAction = "BUY NOW" | "WATCH" | "FORMING" | string;
export interface ActionableSignal {
  ticker: string; company: string; signal: string; action: SignalAction;
  close: number | null; stopPrice: number | null; stopPct: number;
  score: number | null; entryType: string; distAthPct: number | null;
  recovery: string; volRatio: number | null;
}
const ACTION_MAP: Record<string, string> = {
  "Breakout Today": "BUY NOW", "Near Breakout": "WATCH", "Watch Zone": "FORMING",
};
export async function getActionableSignals(csv: string, dataDir?: string): Promise<ActionableSignal[]> {
  // parse <dataDir>/<csv>; missing/empty → []. For each row:
  //   close = num(Close); stopPrice = close==null ? null : round(close*0.85, 2); stopPct = -15;
  //   action = ACTION_MAP[signal] ?? (signal || "—");
  //   pull Company, "Entry Type", "Dist ATH%", Recovery, "Vol Ratio", Score (null if NaN).
}
```
- [ ] Step 4 — run → PASS. Step 5 — `npx tsc --noEmit`; commit `feat(restore): getActionableSignals loader (BUY NOW + stop)`.

## Task 2: ActionableSignals component + wire into momentum section
**Files:** Create `web/components/actionable-signals.tsx`; modify `web/components/strategy-sections/momentum-edge.tsx`.

- [ ] Read `components/strategy-sections/momentum-edge.tsx` (how it loads + renders Funnel/Recent-Breakouts; it has `strategy.liveSignalsCsv`) and an existing dense table (e.g. `rankings-table.tsx`) for the style.
- [ ] `actionable-signals.tsx` — async server component `<ActionableSignals csv={csv} />`:
  - `const rows = await getActionableSignals(csv);` empty → muted "No live signals." note.
  - Dense `<table>` (raw `<table>` — `ui/table.tsx` is "use client", can't be used in async RSC). Columns: **Action** (color badge), **Ticker** (+ company small/muted), **Close ₹**, **Stop ₹** (with `−15%` small), **Score**, **Entry Type**, **Dist ATH%**, **Recovery**, **Vol Ratio**. Numbers `tabular-nums`/right-aligned, `text-sm`, tight rows.
  - Action badge = a small pill. Colors via PLAIN Tailwind (semantic tokens are gone): BUY NOW → `bg-green-600/15 text-green-500 border border-green-600/30`; WATCH → `bg-amber-500/15 text-amber-500 border-amber-500/30`; FORMING → `bg-sky-500/15 text-sky-400 border-sky-500/30`; else → `bg-muted text-muted-foreground`. A small helper `actionBadgeClass(action)`.
  - Heading `<h3 className="text-sm font-semibold">Live Signals — what to buy</h3>` + a one-line caption: `BUY NOW = breakout today · WATCH = near breakout · FORMING = building. Stop = 15% hard stop.`
- [ ] In `momentum-edge.tsx`, render `<ActionableSignals csv={strategy.liveSignalsCsv} />` near the TOP of the section (before/above Recent Breakouts), guarded if `strategy.liveSignalsCsv` is set. Keep Funnel + Recent Breakouts as-is.
- [ ] `npx tsc --noEmit`; `npx next build` clean. Commit `feat(restore): actionable BUY NOW signals on momentum section`.

## Task 3: verify + finish
- [ ] (web/) `npx vitest run` (171 + actionable tests green); tsc; build clean.
- [ ] Runtime: `/strategy/momentum_edge` shows the Live Signals table with Action badges (current data = all "Watch Zone" → FORMING pills), Close, Stop ₹ at −15%, Score, etc.
- [ ] Update `streamlit_feature_restore_program.md` (slice 3 DONE; note momentum-only, other strategies' actionable signals = follow-up). Finish: merge main + **push origin**.

---

## Self-Review
Loader (T1) + component+wire (T2) + verify (T3). Additive, dense, plain-Tailwind badge colors (NOT reverted semantic tokens). Faithful Action map + 15% hard-stop ₹. Momentum-only (richest precompute); IPO/monthly/pead actionable = later. Types `ActionableSignal` consistent loader↔component. Loader → [] on error (never throws). Raw `<table>` (RSC-safe).
