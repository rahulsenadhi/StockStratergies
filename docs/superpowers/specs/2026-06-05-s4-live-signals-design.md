# S4 slice-4 — Home Live-Signals Panel: Design Spec

**Author:** rahulsenadhi
**Date:** 2026-06-05
**Status:** Draft
**Depends on:** S4 slice-3 (Home overview, loader seam), slice-1 (`getStrategies`).

---

## 1. Goal

Add a **Live Signals** section to the Home page (`/`): for each strategy that has a live-signal CSV, show its current top picks (Ticker · Company · Signal). The deferred Home section from slice-3.

## 2. Non-Goals

- **No new signal generation** — read existing CSVs only (Python produces them).
- **No per-strategy live screeners** (filters/charts) — Home summary panel only.
- **No cloud**; Streamlit untouched.

## 3. Decisions (this session)

- Display: **focused** — Ticker · Company · Signal, top-N (default 5) per strategy.
- **Best-effort per strategy:** a panel is built only when a strategy's `liveSignalsCsv` is set AND returns rows. Today: **Monthly** (`live_rankings.csv`) + **Momentum** (`momentum_edge_signals.csv`). IPO/PEAD have no file → omitted (add the index key later, no code change).
- One small data edit: add `live_signals_csv` to the `momentum_edge` index entry (Monthly already has it).

## 4. Architecture & Files

```
web/
  lib/data/strategies.ts        EXTEND:
    Strategy gains `liveSignalsCsv: string | null` (from raw.live_signals_csv)
    export type LiveSignal = { ticker: string; company: string; signal: string }
    getLiveSignals(csv, dataDir?, limit = 5): Promise<LiveSignal[]>
  components/live-signals.tsx    NEW (server) — render panels (name + picks list)
  app/page.tsx                   EXTEND — "Live Signals" section below Recent Backtests
  strategies_index.json          EDIT — momentum_edge gets live_signals_csv = "momentum_edge_signals.csv"
  tests/strategies.test.ts       EXTEND — getLiveSignals + liveSignalsCsv mapping; fixtures
```

**Boundaries:** all data via the loader seam; `getLiveSignals` uses generic case-insensitive column resolution (like the other loaders). `live-signals.tsx` is a server component (plain lists). Best-effort: strategies without a usable file are silently omitted.

## 5. Data Contract (`lib/data/strategies.ts`)

```ts
export type LiveSignal = { ticker: string; company: string; signal: string };
getLiveSignals(csv: string | null, dataDir = DEFAULT_DATA_DIR, limit = 5): Promise<LiveSignal[]>
```
- Resolve columns case-insensitively: `Ticker`, `Company`, `Signal`. If no `Company` column, fall back to the ticker value for company. If no `Ticker` or no `Signal` column → return `[]`.
- Take the first `limit` data rows → `{ticker, company, signal}`.
- Missing/null/empty CSV → `[]`. Wrapped in try/catch.
- `Strategy.liveSignalsCsv` mapped from `raw.live_signals_csv ?? null`.

## 6. Data Flow

```
app/page.tsx (RSC) — after the existing strategies fetch:
  const panels = (await Promise.all(strategies.map(async (s) => ({
     name: s.name,
     picks: s.liveSignalsCsv ? await getLiveSignals(s.liveSignalsCsv) : [],
  })))).filter((p) => p.picks.length > 0);
  render <LiveSignals panels={panels} />   // below Recent Backtests
```
- `<LiveSignals panels={{name, picks}[]}>`: one sub-panel per entry — strategy name + a list of `ticker · company — signal`. Empty `panels` → "No live signals available."

## 7. Error Handling

- Strategy without `liveSignalsCsv` → panel not built.
- File missing/unreadable/empty → `getLiveSignals` `[]` → panel filtered out.
- CSV lacking Ticker/Signal columns → `[]` → omitted (no crash).
- No strategy has signals → section renders "No live signals available."
- Loader reads wrapped in try/catch (existing pattern).

## 8. Testing

- **Vitest (pure loader, fixtures):**
  - `getLiveSignals` on a `live_rankings`-shaped fixture (`Rank,Ticker,Company,…,Signal`) → top-N `{ticker,company,signal}`.
  - on a `momentum_edge_signals`-shaped fixture (`Ticker,Company,Signal,…`) → correct.
  - `limit` caps rows; case-insensitive column match.
  - missing file / null → `[]`; CSV without Ticker/Signal → `[]`.
  - `Strategy.liveSignalsCsv` mapped.
- **Typecheck/build:** `cd web && npx tsc --noEmit && npm run build`.
- **Run verification (slice end):** `npm run dev`; `/` shows a Live Signals section with Monthly + Momentum panels (real tickers/signals); IPO/PEAD absent; existing Home/leaderboard/detail unaffected.

## 9. Open Questions

| Question | Resolution |
|---|---|
| top-N count? | 5 (default `limit`). |
| Section placement? | Below Recent Backtests on Home. |
| Quoted commas in signal CSVs? | Both current files have no quoted-comma cells in Ticker/Company/Signal; naive split is fine (same YAGNI stance as `getTrades`). |
| IPO/PEAD live signals? | Omitted until they have a `live_signals_csv` + file; no code change needed then. |

## 10. Future (context)

Per-strategy live screeners, monthly-returns heatmap, local API for write actions, S2 portfolio, cloud — all reuse the loader seam.
