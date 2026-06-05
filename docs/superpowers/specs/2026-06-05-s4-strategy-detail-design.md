# S4 slice-2 — Next.js Strategy Detail Page: Design Spec

**Author:** rahulsenadhi
**Date:** 2026-06-05
**Status:** Draft
**Depends on:** S4 slice-1 (`web/` Next.js app, typed loader `lib/data/strategies.ts`, leaderboard), S1 (`strategies_index.json`).

---

## 1. Goal

Add the **Strategy Detail page** to the local Next.js app — the second strangler-fig slice. Clicking a leaderboard row opens `/strategy/[id]` showing the strategy's KPI strip, equity curve, drawdown chart, and trade history, reading the existing local data via the extended typed loader. Charts use **TradingView lightweight-charts**.

## 2. Non-Goals

- **No monthly-returns heatmap** this slice (deferred follow-up).
- **No cloud** — local only; Streamlit untouched (strangler-fig).
- **No write actions** (no re-run backtest from UI).
- **No per-strategy trade-schema special-casing** — the trades table is generic.

## 3. Decisions (this session)

- Charting library: **lightweight-charts** (client-only; equity + drawdown as area series).
- Sections: **core 4** — KPI strip + equity curve + drawdown + trades table. Heatmap deferred.
- Trades table: **generic** (dynamic columns from the CSV header) — handles IPO/momentum/Monthly-rebalance schemas without hardcoding.
- Navigation: leaderboard row/name links to `/strategy/[id]`.

## 4. Architecture & Files

```
web/
  app/strategy/[id]/page.tsx      NEW — RSC: getStrategy(id) → sections; notFound() if missing
  lib/data/strategies.ts          EXTEND:
    (Strategy gains tradesCsv: string | null)
    getStrategy(id, dataDir?)         → Strategy | null  (reuses getStrategies)
    getEquityCurve(csv, dataDir?)     → { time: string; value: number }[]  (dated, sorted)
    computeDrawdown(curve)            → { time: string; value: number }[]  (pure; value ≤ 0)
    getTrades(csv, dataDir?)          → { columns: string[]; rows: Record<string,string>[] }
  components/
    line-chart.tsx                  NEW — client lightweight-charts wrapper (area/line, dark, color prop)
    kpi-strip.tsx                   NEW — 5 KPI tiles (reuses format; null → "—")
    trades-table.tsx                NEW — generic table from { columns, rows }
    leaderboard-table.tsx           EXTEND — name cell wrapped in <Link href={`/strategy/${id}`}>
  tests/strategies.test.ts          EXTEND — getStrategy, getEquityCurve, computeDrawdown, getTrades
```

**Boundaries:**
- All data flows through the typed loader (`lib/data/strategies.ts`) — extended, not bypassed. Chart/table components receive plain arrays/objects.
- The page is a **server component**; charts are **leaf client components** (`"use client"`) because lightweight-charts is browser-only. Server reads data, passes it down.
- `getEquityCurve` returns **dated** points (LWC requires `time`); slice-1's `getEquitySeries(): number[]` stays for the sparkline.
- Trades loader is **generic** (dynamic columns) — no per-strategy schema branching.

## 5. Data Flow

```
GET /strategy/[id]
 → app/strategy/[id]/page.tsx (RSC):
     const s = await getStrategy(id);            // null → notFound()
     const curve  = await getEquityCurve(s.equityCsv);
     const dd     = computeDrawdown(curve);
     const trades = await getTrades(s.tradesCsv);
 → <KpiStrip kpis={s.kpis}/> · <LineChart data={curve} kind="area" color="#22c55e"/>
   · <LineChart data={dd} kind="area" color="#ef4444"/> · <TradesTable {...trades}/>
   · back-link → /leaderboard
```

- `getStrategy(id)`: `getStrategies(dir)` then `find(s => s.id === id)` → `Strategy | null`.
- `Strategy` gains `tradesCsv` (mapped from `raw.trades_csv`).
- `getEquityCurve(csv)`: read CSV; resolve date col (`Date` | `date` | first col) + value col (`Portfolio_Value` | `Equity` | `equity` | first numeric); return `{time, value}[]` sorted by date, capped at ~2000 points (downsample if longer). Missing/null → `[]`.
- `computeDrawdown(curve)`: pure — running peak; `value = v/peak − 1` (≤0). `[]` → `[]`.
- `getTrades(csv)`: read; split header; first ≤8 columns; rows as `Record<string,string>`. Missing/empty → `{columns:[], rows:[]}`.

## 6. Charts (lightweight-charts)

- `line-chart.tsx` (`"use client"`): `useRef` container + `useEffect`: `createChart(el, {height:280, dark theme, transparent bg, grid #20242c})`, add area/line series (color from prop), `series.setData(data)`, `timeScale().fitContent()`; `ResizeObserver` to resize on width change; cleanup `chart.remove()` on unmount. Empty `data` → render the container with a "No data" overlay, no crash.
- Drawdown reuses `line-chart` with `color="#ef4444"` (DRY) — one wrapper, props for color/kind.
- Dark theme matches slice 1 (green `#22c55e`, red `#ef4444`).
- lightweight-charts added via `npm i lightweight-charts` in `web/`.

## 7. Error Handling

- Unknown `id` → `getStrategy` returns null → `notFound()` (Next 404). No crash.
- Missing/unreadable equity CSV → `getEquityCurve` `[]` → chart shows "No equity data" placeholder.
- `computeDrawdown([])` → `[]`.
- Missing/empty trades (or Monthly's `rebalance_log.csv` which has no PnL) → generic render of whatever columns exist; truly empty → "No trades for this strategy."
- Null KPIs (Monthly win-rate) → "—" via `KpiStrip` (reuses `format`).
- All loader file reads wrapped in try/catch (slice-1 pattern) — one bad file never 500s the page.

## 8. Testing

- **Vitest (pure loaders, fixtures):**
  - `getStrategy("b")` → that strategy; `getStrategy("nope")` → null; `tradesCsv` mapped.
  - `getEquityCurve` → dated `{time,value}[]` sorted; value-col resolution (`Portfolio_Value` vs `equity`); missing → `[]`; cap ≤2000.
  - `computeDrawdown` on a known curve → correct ≤0 values (hand-computed peak tracking); `[]` → `[]`.
  - `getTrades` → generic columns (≤8) + rows; missing/empty → `{columns:[],rows:[]}`; works on a rebalance-log-shaped fixture (no PnL col).
- **Typecheck/build:** `cd web && npx tsc --noEmit && npm run build`.
- **Run-the-app verification (slice end):** `npm run dev`; from `/leaderboard` click a row → `/strategy/pead`; confirm KPI strip, equity + drawdown charts render (lightweight-charts canvas present), trades table populated, null win-rate "—"; unknown id → 404.

## 9. Open Questions

| Question | Resolution |
|---|---|
| lightweight-charts SSR? | Browser-only; isolate in `"use client"` leaf component using `useEffect` (runs client-side only). No `dynamic(ssr:false)` needed if effect-guarded. Confirm during build. |
| Equity-curve point cap? | ~2000 (LWC handles it; downsample longer series). Detail charts want more fidelity than the 80-pt sparkline. |
| Trades table sortable? | Generic static table this slice (parity-lite). Sorting is a nice-to-have; defer to keep the generic-columns code simple. |
| Date format from CSVs into LWC `time`? | Pass `YYYY-MM-DD` strings (LWC accepts business-day string). Coerce/validate in `getEquityCurve`. |

## 10. Future Slices (context)

Monthly-returns heatmap; Home + Monthly/IPO/Momentum/PEAD pages; trades-table sorting/filtering; local API/sidecar for write actions; cloud only if remote wanted. All reuse the typed-loader seam.
