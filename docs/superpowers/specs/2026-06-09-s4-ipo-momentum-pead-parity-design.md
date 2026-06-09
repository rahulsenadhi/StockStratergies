# S4 Slice 6 — IPO / Momentum / PEAD Parity Sections (Design)

Date: 2026-06-09
Status: Approved (design)

## Goal

Add IPO-Edge-, Momentum-Edge-, and PEAD-specific content to the existing
`/strategy/[id]` page via the **pluggable strategy-section dispatcher** established
in slice 5. Each strategy renders its one signature artifact below the generic core
(KPI strip / equity / drawdown / trades). Generic core stays untouched; non-handled
strategies still render `null`.

Strangler-fig, local-first. Cloud stays deferred. Read-only (no write actions).

## Parity delta over the generic core

`/strategy/[id]` already renders generically for every strategy: KPI strip
(CAGR/Sharpe/MaxDD/WinRate/Trades), equity curve, drawdown, trades table. This slice
adds the per-strategy block each Streamlit page is known for.

| Strategy | Signature block | Data source | Build |
|---|---|---|---|
| **IPO Edge** | Equity-vs-Nifty overlay + Alpha stat | `ipo_edge_equity.csv` (`Date,Portfolio_Value,Benchmark_Value`) | **pure reuse** — `getEquityWithBenchmark` + `MultiLineChart` + Alpha, identical to monthly block A. Zero new loader. |
| **Momentum Edge** | (a) Filter Funnel + (b) Recent Breakouts watchlist | `momentum_edge_funnel.json`; `momentum_edge_recent_breakouts.csv` | new loaders `getFunnel` + `getRecentBreakouts`; funnel → new `HorizontalBars`; breakouts → existing generic `TradesTable` |
| **PEAD** | SUE Decile Spread | `pead_decile_spread.csv` (`sue_decile,fwd_60d_return`) | new loader `getDecileSpread`; rendered by `HorizontalBars`, decile 10 highlighted |

### Funnel labels (parity with `_chart_me_funnel`, master_dashboard.py:6229)

Ordered stages, key → label:

| key | label |
|---|---|
| `total` | Universe |
| `sufficient_data` | Has Data |
| `f1` | F1 Trend |
| `f2` | F2 Price > SMA50 |
| `f3` | F3 MA Align |
| `f4` | F4 vs 52W Low |
| `f5` | F5 Dip Recovered |
| `f6` | F6 Clean Chart |
| `vol_bk` | Vol + Breakout |

Missing key → `0` (never throws). Each bar shows count + % of `total` (universe).
Last bar (`vol_bk`) highlighted green.

### Dropped (YAGNI)

- **IPO promoter-quality table** (`ipo_promoter_quality.csv`) — secondary; IPO's
  signature is the equity-vs-Nifty story. Add later if wanted (new loader + table, no
  dispatcher change).
- **Signal drill-down / candle charts / ATH-only toggle / criteria panel** — Streamlit
  interactive extras; out of scope for read-only parity.
- **Monthly-returns heatmap, trades-table sorting** — separate slices.

## Architecture — reuse the dispatcher

Per-strategy code stays isolated; each block is built and tested independently. The
generic core and other strategies are unaffected.

- `web/components/strategy-sections/index.tsx`
  - `StrategySection` switch gains 3 cases: `ipo_edge`, `momentum_edge`, `pead`.
  - Default case still → `null`.
- `web/components/strategy-sections/ipo-edge.tsx`
  - **Server component**. Loads `getEquityWithBenchmark(strategy.equityCsv)`, renders the
    overlay + Alpha block (mirrors `monthly-rotation.tsx` block A). Empty series → `null`.
- `web/components/strategy-sections/momentum-edge.tsx`
  - **Server component**. Loads `getFunnel(strategy.funnelJson)` +
    `getRecentBreakouts(strategy.recentBreakoutsCsv)`. Renders funnel (`HorizontalBars`)
    and breakouts (`TradesTable`). Best-effort: each empty source omits its block; both
    empty → `null`.
- `web/components/strategy-sections/pead.tsx`
  - **Server component**. Loads `getDecileSpread(strategy.decileSpreadCsv)`, renders the
    decile bars (`HorizontalBars`, decile 10 highlighted). Empty → `null`.
- `web/app/strategy/[id]/page.tsx` — **no change** (already renders `<StrategySection>`).

## New shared component

- `web/components/horizontal-bars.tsx` — **`"use client"` not required** (pure render).
  - Props: `{ data: { label: string; value: number; valueLabel?: string; highlight?: boolean }[]; }`
  - Inline-SVG / CSS bars in the existing palette (consistent with `sparkline.tsx`;
    **not** lightweight-charts — these are categorical, not time series).
  - Bar width = `value / maxValue`. Guards: empty → renders nothing usable upstream
    (caller checks length); `maxValue <= 0` → all bars zero-width (no div-by-zero).
  - `highlight` bar uses the green accent; others neutral.
  - Reused by both funnel and decile spread (DRY — avoids two near-identical charts).

## Loader changes — `web/lib/data/strategies.ts`

### `Strategy` type + index mapping

Add 3 optional fields, mapped from new snake_case `strategies_index.json` keys:

| `Strategy` field | index key | strategy |
|---|---|---|
| `funnelJson` | `funnel_json` | momentum_edge |
| `recentBreakoutsCsv` | `recent_breakouts_csv` | momentum_edge |
| `decileSpreadCsv` | `decile_spread_csv` | pead |

IPO needs no new key (uses existing `equity_csv`).

### New loaders

- `getFunnel(jsonPath: string, dataDir?: string): Promise<FunnelStage[]>`
  - `FunnelStage = { label: string; value: number }`.
  - Reads JSON, maps the fixed ordered key→label list above, `value = json[key] ?? 0`.
  - Unreadable / missing file → `[]` (best-effort, never throws).
- `getRecentBreakouts(csv: string, dataDir?: string): Promise<{ columns: string[]; rows: string[][] }>`
  - 9-column CSV exceeds the generic `getTrades` 8-col cap → dedicated loader returning
    all columns. Top-N rows (`limit` param, default `10`). Empty/missing → `{ columns: [], rows: [] }`.
- `getDecileSpread(csv: string, dataDir?: string): Promise<{ decile: number; fwdReturn: number }[]>`
  - Case-insensitive header (`sue_decile`, `fwd_60d_return`). Skips unparseable rows.
    Sorted by decile asc. Missing → `[]`.

### Deferred slice-5 cleanup (now due — 3rd+ loaders landing)

- **I2** — extract `parseCsvLines(csv, dataDir?)` helper: `readFile → split → guard empty
  → lowercase header → return { header: string[]; rows: string[][] }`. Refactor
  `getLiveSignals`, `getRankings`, `getEquityCurve`, `getRecentBreakouts`, `getDecileSpread`
  onto it. Behavior-preserving.
- **I1** — hoist `cell` / `numCell` in `rankings-table.tsx` to module scope.

## Index data — `strategies_index.json`

- `momentum_edge` gains `"funnel_json": "momentum_edge_funnel.json"`,
  `"recent_breakouts_csv": "momentum_edge_recent_breakouts.csv"`.
- `pead` gains `"decile_spread_csv": "pead_decile_spread.csv"`.

## Error handling

- Every new loader is best-effort: unreadable/missing/malformed input → empty result,
  never throws. Each section omits a block whose data is empty; a section with all
  blocks empty returns `null` (page identical to pre-slice for that strategy).
- `HorizontalBars` guards `maxValue <= 0`.

## Testing (vitest)

- `getFunnel`: full json → 9 ordered stages; missing keys → 0; unreadable → `[]`.
- `getRecentBreakouts`: header + rows; >8 cols preserved; empty/missing → empty.
- `getDecileSpread`: parses deciles 1–10; case-insensitive header; bad rows skipped;
  sorted asc; missing → `[]`.
- `parseCsvLines`: empty file, header-only, header + rows, CRLF.
- `HorizontalBars` bar-width math: normal, `maxValue=0`, single bar, highlight flag.
- Target ~+12 tests → ~63 pass. Existing 51 must stay green.

## Verification

- `tsc --noEmit` clean; `next build` clean.
- Runtime (curl on `next start`):
  - `/strategy/ipo_edge` → equity-vs-Nifty overlay + Alpha present.
  - `/strategy/momentum_edge` → funnel bars (Universe→Vol+Breakout) + recent-breakouts table.
  - `/strategy/pead` → decile-spread bars, decile 10 highlighted.
  - `/strategy/monthly_rotation` → **unchanged** (regression guard).
  - Leaderboard + Home still 200.

## Out of scope / future slices

Monthly-returns heatmap; trades-table sorting; IPO promoter-quality table; write
actions (Recompute / run-backtest sidecar); cloud serving. Each reuses the loader seam.
