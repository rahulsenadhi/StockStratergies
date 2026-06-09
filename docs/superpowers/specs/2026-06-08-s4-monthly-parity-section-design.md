# S4 Slice 5 — Monthly Rotation Parity Section (Design)

Date: 2026-06-08
Status: Approved (design)

## Goal

Add Monthly-Rotation-specific content to the existing `/strategy/[id]` page via a
**pluggable strategy-section dispatcher**, rendered below the generic core
(KPI strip / equity / drawdown / trades). This slice establishes the per-strategy
section pattern that later slices reuse for IPO Edge, Momentum Edge, and PEAD.

Strangler-fig, local-first. Cloud stays deferred. Read-only (no write actions).

## Parity delta over the generic core

`/strategy/[id]` already renders, generically for every strategy:
KPI strip (CAGR/Sharpe/MaxDD/WinRate/Trades), equity curve, drawdown, trades table.

The Streamlit `render_monthly` page (master_dashboard.py:5936) has additional
strategy-specific blocks. The two worth porting in this slice:

| Block | Data source | Build |
|---|---|---|
| **A. Equity vs Nifty overlay + Alpha stat** | `backtest_results.csv` (`Benchmark_Value` column) | reuse `multi-line-chart` (slice 3) with two rebased series; show "Extra vs Nifty" (Alpha) stat |
| **B. Full rankings table** — "All 50 by RS Score", top-5 highlighted | `live_rankings.csv` (`Rank, Ticker, Company, Current_Price, Return_%, RS_Score, Signal`) | new `rankings-table` component |

### Dropped (YAGNI)

- **Exit Playbook card + explainer box** — advisory overlay; separate concern owned
  by the existing exit-analyzer feature. Not part of frontend parity.
- **Specialized rebalance-log view** (bought/sold per month) — the generic
  trades-table already renders `rebalance_log.csv`. No duplicate.

## Architecture — pluggable dispatch

Goal: isolate per-strategy code so each strategy's block can be understood, built,
and tested independently, and the generic core stays untouched.

- `web/components/strategy-sections/index.tsx`
  - `StrategySection({ strategy }: { strategy: Strategy })` — **server component**
    dispatcher. `switch (strategy.id)`; returns the strategy-specific block or `null`.
  - Default case → `null` (every other strategy renders nothing → page identical to today).
- `web/components/strategy-sections/monthly-rotation.tsx`
  - **Server component**. Loads rankings + benchmark via the loader seam, renders
    blocks A and B. Best-effort: any empty data → that block is omitted, never throws.
- `web/app/strategy/[id]/page.tsx`
  - Append `<StrategySection strategy={s} />` after the existing trades `<section>`.
  - No other change to the page. Generic core unchanged.

The dispatcher keys on `strategy.id` (`"monthly_rotation"`). Adding IPO/Momentum/PEAD
later = one new file + one `case` — no edits to existing blocks.

## Loader additions (`web/lib/data/strategies.ts`)

This is the **only** module that touches data (the future-cloud swap point). All new
functions follow existing conventions: null-safe, missing file/column → empty result,
never throw, never invent zeros.

- `getEquityWithBenchmark(equityCsv: string, dataDir?: string)`
  → `{ strategy: Point[]; benchmark: Point[] }`
  - Reads `backtest_results.csv`. Resolves the strategy column via the existing
    equity-column logic (`Portfolio_Value` | `Equity` | `equity`).
  - Both series rebased to return-% via the existing `rebaseToReturn` (Nifty starts
    near 210, strategy near 50000 — raw overlay is meaningless; rebasing to a common
    base = 0% start makes the gap legible).
  - Missing `Benchmark_Value` column → `benchmark: []` (block A degrades to a single
    line, still useful). Missing file / unreadable → `{ strategy: [], benchmark: [] }`.
- `getRankings(rankingsCsv: string, dataDir?: string)` → `RankingRow[]`
  - `RankingRow = { rank: number｜null; ticker: string; company: string; price: number｜null; returnPct: number｜null; rsScore: number｜null; signal: string }`.
  - Case-insensitive column resolution (match `getLiveSignals` convention). `Ticker`
    required else the row is skipped; missing file / no rows → `[]`.
  - `company` falls back to `ticker` when absent (same as `getLiveSignals`).
  - Strips `.NS` suffix from ticker and `🟢 `/`🔴 ` emoji prefixes from signal
    (Streamlit parity — display-clean values).
  - Returns rows in file order (already rank-sorted in source); no re-sort.
- `annualizedReturn(curve: Point[]): number｜null` — pure helper.
  - CAGR from first/last point of a dated curve:
    `(last/first)^(1/years) − 1`, `years = days/365.25`, `max(years, 0.01)` guard.
  - `< 2` points or non-positive first value → `null`.

### Alpha stat

`alpha = s.kpis.cagr − benchmarkCagr`, where `benchmarkCagr = annualizedReturn(rawBenchmarkCurve)`.
Computed in the monthly-rotation block. If either input is `null` → render Alpha as
"—" (the `naDash` helper). Strategy CAGR comes from `s.kpis.cagr` (already loaded);
benchmark CAGR is derived from the raw (un-rebased) benchmark curve so the annualized
math is correct.

Note: `getEquityWithBenchmark` returns *rebased* series for the overlay chart. The
Alpha calc needs the *raw* benchmark endpoints. To avoid a second file read, the
function also returns the raw first/last benchmark values, or the block reads the
benchmark CAGR from a single combined return. **Decision:** extend the return shape to
`{ strategy: Point[]; benchmark: Point[]; benchmarkCagr: number｜null }` — the loader
computes `benchmarkCagr` from the raw benchmark column before rebasing, so the block
gets everything from one call and stays free of raw-vs-rebased confusion.

## Components

- `web/components/rankings-table.tsx` — **client** component (sortable later; this
  slice renders static, top-5 rows visually highlighted). Columns: Rank, Ticker,
  Company, Price (₹), Return %, RS Score, Signal. Null cells → "—" via `naDash`.
  Top-5 highlight = rows where `rank <= 5` get an accent border/background.
- Reuse `multi-line-chart.tsx` (slice 3, LWC v5 LineSeries + legend) for block A:
  series = `[{ name: "Monthly Rotation", data: strategy }, { name: "Nifty", data: benchmark }]`,
  benchmark series filtered out when empty.
- Reuse `lib/format.ts` (`pct`, `signed`, `naDash`).

## Data flow

1. `page.tsx` (RSC, `force-dynamic`) loads `getStrategy(id)` → `s`.
2. `<StrategySection strategy={s} />` dispatches on `s.id`.
3. For `monthly_rotation`, the block calls `getEquityWithBenchmark(s.equityCsv)` and
   `getRankings(s.liveSignalsCsv)` at request time.
   - Note: rankings come from `live_rankings.csv` = `s.liveSignalsCsv` (already in the
     index for monthly_rotation), NOT `tradesCsv`.
4. Renders overlay chart + Alpha stat (block A) and rankings-table (block B).
5. Any empty dataset → that block omitted; section never throws.

## Error handling

- Every loader: missing file, missing column, empty rows → empty result, no throw.
- Block component: guards each dataset; renders only the blocks with data.
- Dispatcher default case → `null`.
- Matches the best-effort pattern from slice 4 live-signals.

## Testing

- Vitest on the 3 new loader functions, matching the existing loader-test file pattern:
  - `getEquityWithBenchmark`: normal (both series + benchmarkCagr), missing
    `Benchmark_Value` (benchmark `[]`, benchmarkCagr `null`), missing file (`[]`/`[]`/`null`).
  - `getRankings`: normal rows, `.NS`/emoji stripping, missing `Ticker` (row skipped),
    company fallback, missing file (`[]`), missing numeric cols (`null` not `0`).
  - `annualizedReturn`: known curve, `< 2` points → `null`, non-positive first value → `null`.
- Components (RSC dispatcher, server block, client rankings-table): runtime-verified
  via `next start` + curl on `/strategy/monthly_rotation`, same as prior slices.
  Assert: overlay has 2 lines, Alpha stat present, rankings table has rows with top-5
  highlighted, and `/strategy/ipo_edge` (and others) render identically to today (no
  section).
- Gate: `tsc --noEmit` + `next build` clean; full vitest green.

## Out of scope (future slices)

IPO / Momentum / PEAD section blocks (one slice each, same dispatcher pattern);
rankings-table sorting; monthly-returns heatmap; write-action sidecar.
See [[s4-nextjs-frontend]], [[platform-v2-roadmap]].
