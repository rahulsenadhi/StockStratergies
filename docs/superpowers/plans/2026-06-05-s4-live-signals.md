# S4 slice-4 — Home Live-Signals Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Live Signals section to the Home page — per strategy with a live-signal CSV, show top-5 current picks (Ticker · Company · Signal).

**Architecture:** Extend the typed loader with `Strategy.liveSignalsCsv` + `getLiveSignals` (generic case-insensitive column resolution). A server component `live-signals.tsx` renders best-effort panels; Home builds panels only for strategies with rows. One small index edit adds Momentum's signal file.

**Tech Stack:** Next.js 16, TypeScript, Tailwind v4, Vitest. Builds on S4 slice-3.

Spec: `docs/superpowers/specs/2026-06-05-s4-live-signals-design.md`.

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `web/lib/data/strategies.ts` | + `Strategy.liveSignalsCsv`; `LiveSignal` type; `getLiveSignals` | Modify |
| `web/tests/strategies.test.ts` | + getLiveSignals + liveSignalsCsv tests; fixtures | Modify |
| `web/components/live-signals.tsx` | server panel component | Create |
| `web/app/page.tsx` | + Live Signals section | Modify |
| `strategies_index.json` | momentum_edge gets `live_signals_csv` | Modify |

**Conventions:** npm/npx from `web/`; commit from repo root. Branch by controller. No Python/Streamlit changes (the index JSON edit is data, allowed).

---

## Task 1: loader — `liveSignalsCsv` + `getLiveSignals` (TDD)

**Files:** Modify `web/lib/data/strategies.ts`, `web/tests/strategies.test.ts`; fixtures `web/tests/fixtures/live_rank.csv`, `live_mom.csv`

- [ ] **Step 1: Create fixtures**

`web/tests/fixtures/live_rank.csv` (live_rankings shape):
```
Rank,Ticker,Company,Current_Price,Return_%,RS_Score,Signal
1,ZEEL.NS,Zee Entertainment,104.4,12.1,12.9,Strong BUY
2,SBIN.NS,State Bank,820.0,4.2,6.1,BUY
```
`web/tests/fixtures/live_mom.csv` (momentum_edge_signals shape):
```
Ticker,Company,Signal,Close,Score
HINDZINC,Hindustan Zinc,Watch Zone,610.55,51.1
TATASTEEL,Tata Steel,Breakout,150.2,70.0
```

- [ ] **Step 2: Add `live_signals_csv` to fixture strategy "a"**

In `web/tests/fixtures/strategies_index.json`, add `"live_signals_csv": "live_rank.csv"` to strategy `"a"`.

- [ ] **Step 3: Write failing tests** (append to `web/tests/strategies.test.ts`)

```ts
import { getLiveSignals, getStrategy } from "@/lib/data/strategies";

describe("getLiveSignals", () => {
  it("reads live_rankings shape -> ticker/company/signal", async () => {
    const r = await getLiveSignals("live_rank.csv", FIX);
    expect(r[0]).toEqual({ ticker: "ZEEL.NS", company: "Zee Entertainment", signal: "Strong BUY" });
    expect(r.length).toBe(2);
  });
  it("reads momentum shape", async () => {
    const r = await getLiveSignals("live_mom.csv", FIX);
    expect(r[1]).toEqual({ ticker: "TATASTEEL", company: "Tata Steel", signal: "Breakout" });
  });
  it("limit caps rows", async () => {
    expect((await getLiveSignals("live_rank.csv", FIX, 1)).length).toBe(1);
  });
  it("missing/null -> []", async () => {
    expect(await getLiveSignals("nope.csv", FIX)).toEqual([]);
    expect(await getLiveSignals(null, FIX)).toEqual([]);
  });
  it("liveSignalsCsv mapped on Strategy", async () => {
    const s = await getStrategy("a", FIX);
    expect(s?.liveSignalsCsv).toBe("live_rank.csv");
  });
});
```

- [ ] **Step 4: Run, verify fail** — `cd web && npm test` → FAIL.

- [ ] **Step 5: Implement** — in `web/lib/data/strategies.ts`:

Add `liveSignalsCsv: string | null;` to the `Strategy` type. In `mapStrategy`, after `lastRun: raw.last_run ?? null,` add:
```ts
    liveSignalsCsv: raw.live_signals_csv ?? null,
```
Append:
```ts
export type LiveSignal = { ticker: string; company: string; signal: string };
const LIVE_LIMIT = 5;

export async function getLiveSignals(
  csv: string | null,
  dataDir: string = DEFAULT_DATA_DIR,
  limit: number = LIVE_LIMIT,
): Promise<LiveSignal[]> {
  if (!csv) return [];
  try {
    const txt = await fs.readFile(path.join(dataDir, csv), "utf-8");
    const lines = txt.trim().split(/\r?\n/);
    if (lines.length < 2) return [];
    const header = lines[0].split(",").map((h) => h.trim().toLowerCase());
    const ti = header.indexOf("ticker");
    const ci = header.indexOf("company");
    const si = header.indexOf("signal");
    if (ti < 0 || si < 0) return [];
    return lines
      .slice(1, 1 + limit)
      .map((l) => {
        const cells = l.split(",");
        const ticker = (cells[ti] ?? "").trim();
        return {
          ticker,
          company: ci >= 0 ? (cells[ci] ?? "").trim() : ticker,
          signal: (cells[si] ?? "").trim(),
        };
      })
      .filter((r) => r.ticker !== "");
  } catch {
    return [];
  }
}
```

- [ ] **Step 6: Run, verify pass** — `cd web && npm test` → PASS.

- [ ] **Step 7: Commit**

```bash
cd .. && git add web/lib/data/strategies.ts web/tests/strategies.test.ts web/tests/fixtures/live_rank.csv web/tests/fixtures/live_mom.csv web/tests/fixtures/strategies_index.json && git commit -m "feat(s4): getLiveSignals + Strategy.liveSignalsCsv"
```

---

## Task 2: component + Home wiring + index edit

**Files:** Create `web/components/live-signals.tsx`; Modify `web/app/page.tsx`, `strategies_index.json`

- [ ] **Step 1: Implement `web/components/live-signals.tsx`**

```tsx
import type { LiveSignal } from "@/lib/data/strategies";

export type LivePanel = { name: string; picks: LiveSignal[] };

export function LiveSignals({ panels }: { panels: LivePanel[] }) {
  if (!panels.length) {
    return <p className="text-sm text-muted-foreground">No live signals available.</p>;
  }
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {panels.map((p) => (
        <div key={p.name} className="rounded-lg border border-border p-3">
          <div className="mb-2 font-medium">{p.name}</div>
          <ul className="space-y-1 text-sm">
            {p.picks.map((s, i) => (
              <li key={i} className="flex items-center justify-between gap-2">
                <span>
                  <span className="font-mono">{s.ticker}</span>{" "}
                  <span className="text-muted-foreground">{s.company}</span>
                </span>
                <span className="text-muted-foreground">{s.signal}</span>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Add the section to `web/app/page.tsx`**

Add imports at the top:
```tsx
import { getLiveSignals } from "@/lib/data/strategies";
import { LiveSignals, type LivePanel } from "@/components/live-signals";
```
(Extend the existing `from "@/lib/data/strategies"` import to include `getLiveSignals` if combined.)

After the `recent` computation (before the `return`), add:
```tsx
  const panels: LivePanel[] = (
    await Promise.all(
      strategies.map(async (s) => ({
        name: s.name,
        picks: s.liveSignalsCsv ? await getLiveSignals(s.liveSignalsCsv) : [],
      })),
    )
  ).filter((p) => p.picks.length > 0);
```
In the JSX, add a section below the Recent Backtests `<section>`:
```tsx
      <section>
        <h2 className="mb-2 text-lg font-semibold">Live Signals</h2>
        <LiveSignals panels={panels} />
      </section>
```

- [ ] **Step 3: Add Momentum's signal file to the real index**

In `strategies_index.json`, add to the `momentum_edge` entry (alongside its other keys):
```json
      "live_signals_csv": "momentum_edge_signals.csv",
```
(Monthly already has `"live_signals_csv": "live_rankings.csv"`.)

- [ ] **Step 4: Typecheck + build**

Run: `cd web && npx tsc --noEmit && npm run build`
Expected: no errors; `/` still builds.

- [ ] **Step 5: Commit**

```bash
cd .. && git add web/components/live-signals.tsx web/app/page.tsx strategies_index.json && git commit -m "feat(s4): home Live Signals section + momentum signals index key"
```

---

## Task 3: Verify + memory

- [ ] **Step 1: Full Vitest + typecheck + build**

```bash
cd web && npm test && npx tsc --noEmit && npm run build
```
Expected: all green (new getLiveSignals tests included).

- [ ] **Step 2: Run + verify**

```bash
cd web && npx next start -p 3007   # after build
```
- `curl -s http://localhost:3007/ | grep -oE "Live Signals|Monthly Rotation|Momentum Edge"` → "Live Signals" present.
- Browser `/`: a Live Signals section shows a Monthly panel (tickers from live_rankings) + a Momentum panel (from momentum_edge_signals), each ticker · company — signal; IPO/PEAD absent. Existing Home sections + leaderboard/detail unaffected.
Stop the server.

> Real signal files (`live_rankings.csv`, `momentum_edge_signals.csv`) exist at repo root; the running app reads them via `DATA_DIR=..`. If a file is empty at run time, that panel is omitted (expected). Report which path used.

- [ ] **Step 3: Memory (controller, not subagent)**

Update `s4_nextjs_frontend.md`: slice-4 (Home Live Signals) done — `getLiveSignals` + `Strategy.liveSignalsCsv`, `live-signals.tsx`, Home section, momentum index key. Monthly+Momentum panels; IPO/PEAD omitted until they have signal files.

---

## Self-Review

**Spec coverage:**
- §4 files (loader ext, live-signals component, page section, index edit) → Tasks 1–2. ✓
- §5 contract (`LiveSignal`, `getLiveSignals` case-insensitive cols, Ticker/Signal required else [], company fallback, limit) → Task 1. ✓
- §6 data flow (panels built per strategy, filtered non-empty, section render) → Task 2. ✓
- §7 errors (no csv→skip, missing→[], no Ticker/Signal→[], empty panels→message) → Tasks 1,2. ✓
- §8 testing (both shapes, limit, missing/null, mapping; build; run) → Tasks 1,3. ✓

**Placeholder scan:** all code complete; no TBD/TODO.

**Type consistency:** `Strategy.liveSignalsCsv: string|null`; `LiveSignal {ticker,company,signal}`; `getLiveSignals(csv|null,dir?,limit?)→LiveSignal[]`; `LivePanel {name,picks:LiveSignal[]}` shared component↔page. Consistent across tasks. ✓
