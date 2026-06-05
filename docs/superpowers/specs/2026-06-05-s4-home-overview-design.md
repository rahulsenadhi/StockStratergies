# S4 slice-3 — Next.js Home Overview Page: Design Spec

**Author:** rahulsenadhi
**Date:** 2026-06-05
**Status:** Draft
**Depends on:** S4 slice-1 (leaderboard, typed loader), slice-2 (detail page, lightweight-charts, `getEquityCurve`), S1 (`strategies_index.json`).

---

## 1. Goal

Add the **Home overview page** at `/` — the third strangler-fig slice. An at-a-glance dashboard: aggregate KPI strip, combined (normalized) equity overlay of all strategies, Top Performers, and Recent Backtests — reading local data via the loader. Plus minimal nav (Home ↔ Leaderboard).

## 2. Non-Goals

- **No live-signals section** (current per-strategy picks) — deferred (needs new live-signal CSV loaders).
- **No cloud**; Streamlit untouched (strangler-fig).
- **No write actions.**

## 3. Decisions (this session)

- Sections: **Overview** — aggregate KPI strip + combined equity chart + Top Performers + Recent Backtests. Live-signals deferred.
- Combined chart is **normalized** (each strategy rebased to 0% cumulative return at start) for cross-strategy comparability on one axis.
- `/` becomes Home (was a redirect to `/leaderboard`); add a minimal top nav.

## 4. Architecture & Files

```
web/
  app/page.tsx                    CHANGE — render Home overview (RSC, force-dynamic); was redirect
  app/layout.tsx                  EXTEND — render <Nav/> above children
  lib/summary.ts                  NEW (pure) — summarizeStrategies(strategies) → aggregates
  lib/data/strategies.ts          EXTEND:
    Strategy gains `lastRun: string | null` (from raw.last_run)
    rebaseToReturn(curve)             → EquityPoint[] normalized to start=0
  components/
    nav.tsx                       NEW — header nav (Home | Leaderboard)
    home-kpi-strip.tsx            NEW — 4 aggregate tiles
    multi-line-chart.tsx          NEW — client LWC multi-series overlay
    top-performers.tsx            NEW — top-3-by-Sharpe cards (link to detail)
    recent-backtests.tsx          NEW — top-5-by-lastRun list (link to detail)
  tests/summary.test.ts           NEW — summarizeStrategies + rebaseToReturn
```

**Boundaries:**
- Aggregates in a **pure `lib/summary.ts`** (feed `Strategy[]`, get strip numbers) — null-safe, testable.
- All data via the **loader seam**; Home RSC reads index + per-strategy equity curves, passes plain data down.
- `multi-line-chart` is the only new client component; strip/cards/lists/nav are server components.
- `Strategy` gains `lastRun` for the Recent sort.

## 5. Aggregates (`lib/summary.ts`)

```ts
type Summary = {
  total: number; live: number; paper: number;
  avgCagr: number; bestCagr: number; avgWinRate: number; totalTrades: number;
};
summarizeStrategies(strategies: Strategy[]): Summary
```
- `total` = count; `live`/`paper` = count by `status`.
- `avgCagr`/`bestCagr` over **non-null** `kpis.cagr` (ignore null); empty → 0.
- `avgWinRate` over **non-null** `kpis.winRate` only (a null-win-rate strategy does NOT count as 0 — matches Streamlit). Empty → 0.
- `totalTrades` = sum of non-null `kpis.numTrades`.

## 6. Data Flow

```
GET /  (RSC, force-dynamic):
  strategies = await getStrategies();
  summary    = summarizeStrategies(strategies);
  top        = [...strategies].sort(bySharpeDesc).slice(0, 3);     // null sharpe last
  recent     = [...strategies].sort(byLastRunDesc).slice(0, 5);    // null lastRun last
  series     = (await Promise.all(strategies.map(async (s) => ({
                 name: s.name, color: colorFor(index),
                 points: rebaseToReturn(await getEquityCurve(s.equityCsv)),
               })))).filter((x) => x.points.length > 0);
render: <HomeKpiStrip summary/> · <MultiLineChart series/> ·
        <TopPerformers items={top}/> · <RecentBacktests items={recent}/>
```
- `rebaseToReturn(curve)`: `[]`→`[]`; else map `{time, value: v / v0 - 1}` (first point 0). `v0<=0` guard → returns `[]`.
- `colorFor(i)`: fixed palette cycled by index (deterministic; no Math.random).
- `lastRun` from `raw.last_run`; sort desc by ISO string; missing → last.

## 7. Charts (`multi-line-chart.tsx`, lightweight-charts v5)

- `"use client"`; props `series: { name: string; color: string; points: EquityPoint[] }[]`.
- `useEffect`: `createChart` (dark theme, autoSize, height 320); for each series `chart.addSeries(LineSeries, { color, lineWidth: 2 })` + `setData(points)`; `timeScale().fitContent()`; cleanup `chart.remove()`.
- Legend: name + color swatch row above the chart.
- Empty `series` (or all empty) → "No equity data" placeholder, no crash.

## 8. Error Handling

- Empty index → `[]` → strip zeros, lists "No strategies", chart placeholder. No crash.
- Null-KPI strategy → excluded from the relevant average (not 0); still listed/charted.
- Missing equity CSV → that series filtered out of the overlay; others render.
- `summarizeStrategies([])` → all zeros; `rebaseToReturn([])`/`v0<=0` → `[]`.
- Loader reads wrapped in try/catch (existing pattern).

## 9. Testing

- **Vitest (pure):**
  - `summarizeStrategies`: counts (total/live/paper); `avgCagr`/`bestCagr` ignore null; `avgWinRate` over present only (null win-rate not counted as 0); `totalTrades` sum; `[]` → zeros.
  - `rebaseToReturn`: known curve → first 0, later `v/v0−1`; `[]`→`[]`; `v0<=0`→`[]`.
  - `Strategy.lastRun` mapped.
- **Typecheck/build:** `cd web && npx tsc --noEmit && npm run build`.
- **Run verification (slice end):** `npm run dev`; `/` shows aggregate strip (real numbers), combined chart overlaying multiple rebased lines + legend, Top-3 + Recent-5 lists with working detail links; nav Home↔Leaderboard; existing leaderboard/detail unaffected.

## 10. Open Questions

| Question | Resolution |
|---|---|
| LineSeries import (v5)? | v5: `import { LineSeries } from "lightweight-charts"` + `addSeries(LineSeries, …)` (same pattern as slice-2 AreaSeries). |
| Combined chart: rebase to 0% vs index-100? | Rebase to **0% return** (`v/v0−1`); axis reads as % cumulative return. |
| Nav placement? | Simple sticky top bar in `layout.tsx` via `<Nav/>` (Home, Leaderboard links). |
| Recent/Top tie-breaks? | Recent by `lastRun` desc; Top by `sharpe` desc. Nulls sort last via sentinel. |

## 11. Future Slices (context)

Live-signals (current picks), Monthly/IPO/Momentum/PEAD dedicated pages, monthly-returns heatmap, trades sorting, local API for write actions, cloud deploy — all reuse the loader seam.
