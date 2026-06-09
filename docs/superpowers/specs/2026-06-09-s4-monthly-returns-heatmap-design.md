# S4 — Monthly-Returns Heatmap (core section)

**Date:** 2026-06-09
**Slice:** S4 frontend, deferred core section (originally noted in slice 2)
**Status:** Design approved, ready for plan

## Goal

Add a monthly-returns calendar heatmap as a **core** section on the strategy detail
page (`/strategy/[id]`), rendered for **all 4 strategies** that have a dated equity
curve. This is the standard quant-tearsheet "years × months" grid: at a glance the
user sees which months/years a strategy made or lost money, and how much.

This is a generic, read-only, local-first section — same architecture as existing
core sections (KPI strip, equity curve, drawdown, trades). It is NOT a per-strategy
dispatcher block; it lives in the generic page body.

## Placement

- Rendered in `app/strategy/[id]/page.tsx`, **after the drawdown chart** and before
  (or alongside) the trades table — exact order: KPI → equity → drawdown →
  **monthly heatmap** → trades → `<StrategySection/>`.
- Added once, generically. No `strategy.id` switch.
- The section renders `null` (hidden entirely) when the strategy has fewer than 2
  months of data, so strategies with thin/empty equity curves simply don't show it.

## Data layer (`web/lib/data/strategies.ts`)

### Refactor: extract `readEquityCurveRaw`

`getEquityCurve` currently downsamples to `MAX_CURVE_POINTS` (≤2000) keeping the last
point. That downsampling can drop true month-end values, so the heatmap must NOT use
it. Extract the full-resolution portion into a shared helper:

```
async function readEquityCurveRaw(csv, dataDir): Promise<EquityPoint[]>
```

- Contains the existing logic of `getEquityCurve` lines that: read file, split lines,
  detect date column (`DATE_COLS`) and equity column (`EQUITY_COLS` with numeric
  fallback), map to `{time, value}`, filter NaN/empty, sort by time ascending, and
  dedup repeated dates keeping the last value.
- Does **not** downsample.
- Returns `[]` on any error / missing csv / <2 data lines (same as today).

`getEquityCurve` becomes: `readEquityCurveRaw(...)` then apply the existing
`MAX_CURVE_POINTS` downsample. Behavior of `getEquityCurve` is unchanged (verified by
a parity test).

### New loader: `getMonthlyReturns`

```
type MonthlyReturnsRow = { year: number; months: (number | null)[]; annual: number | null };
async function getMonthlyReturns(csv, dataDir?): Promise<MonthlyReturnsRow[]>
```

Algorithm:

1. `curve = await readEquityCurveRaw(csv, dataDir)`. If `curve.length < 2` → return `[]`.
2. `anchor = curve[0].value` (series opening value).
3. Group points by `YYYY-MM` (slice of the `time` string). For each present month, the
   **month-end value** = the last point in that month (curve is already sorted asc).
4. Walk months in chronological order. For each present month `m`:
   - `prev` = the previous **present** month's month-end value, or `anchor` for the
     first present month.
   - `monthlyReturn = monthEnd / prev - 1` (a fraction). Guard `prev <= 0` → `null`.
5. Build rows keyed by calendar year, ascending. `months` is a length-12 array
   (index 0 = Jan … 11 = Dec); months with no data → `null`.
6. **Annual total** for a year = compound of that year's *displayed* monthly returns:
   `∏(1 + r) - 1` over non-null months. If a year has zero non-null months → `null`.
   (Decision: annual reconciles with the cells shown, even when months have gaps.)

Notes:
- Months with no data are blank (`null`), not zero.
- Gap handling: if a calendar month is missing, the next present month compounds from
  the last available month-end (acceptable; logged behavior, not a silent cap).
- Returns are fractions (e.g. `0.0412` = +4.12%), consistent with `kpis.cagr` etc.

## Component (`web/components/monthly-heatmap.tsx`)

Pure presentational component (no `lightweight-charts`; CSS-only, like
`horizontal-bars.tsx`). `"use client"` not required — static render is fine as a
server component, matching other pure section components.

```
interface MonthlyHeatmapProps { rows: MonthlyReturnsRow[]; }
export function MonthlyHeatmap({ rows }: MonthlyHeatmapProps): ReactNode
```

- Layout: a table/grid. Header row = `Year | Jan | Feb | … | Dec | Annual`.
- One body row per `MonthlyReturnsRow`: year label, 12 month cells, annual cell.
- Cell background = `cellColor(r)`; cell text = `pct(r)` from `lib/format` (null → "—").
- Annual column reuses the same color scale and `pct`.
- Empty `rows` → render nothing (the page-level guard already hides the section, but
  the component is defensive too).

### Color helper: `cellColor`

```
export function cellColor(r: number | null): string
```

- `null` → muted/transparent background (blank cell, e.g. `transparent` or a faint
  border-only style).
- `r >= 0` → green; `r < 0` → red.
- **Symmetric fixed scale:** intensity `= Math.min(Math.abs(r) / 0.10, 1)` — ±10% per
  month = full saturation, clamp beyond. Comparable across strategies.
- Returned as an `rgba()`/`hsl()` string with alpha driven by intensity (e.g.
  green `rgba(34,197,94,intensity)`, red `rgba(239,68,68,intensity)` — match the
  existing `#22c55e` / `#ef4444` palette used elsewhere).
- Pure function, no DOM — unit-testable.

## Page wiring (`web/app/strategy/[id]/page.tsx`)

- Add `const monthly = await getMonthlyReturns(strategy.equityCsv);` alongside the
  other loads.
- Render `{monthly.length >= 2 ? <section>…<MonthlyHeatmap rows={monthly}/></section> : null}`
  in the core section order described above. Heading: **"Monthly Returns"**.
- No change to the loader seam contract; reads `strategy.equityCsv` which already
  exists for all 4 strategies.

## Testing (vitest, TDD)

`lib/data/strategies.test.ts` (or sibling):
- `readEquityCurveRaw`: returns full-res sorted/deduped curve; `[]` on empty/missing.
- `getEquityCurve` **parity**: still downsamples ≤ `MAX_CURVE_POINTS`, last point kept
  (existing behavior unchanged).
- `getMonthlyReturns`:
  - month-end selection (last point of each month wins),
  - first-month anchor (return computed vs opening value),
  - gap handling (missing calendar month → null cell, next month compounds correctly),
  - annual compounding `∏(1+r)-1` over displayed months,
  - year with all-null months → `annual: null`,
  - empty/missing csv → `[]`,
  - `prev <= 0` guard → null.

`components/monthly-heatmap` (or a `cellColor` unit test):
- `cellColor` boundaries: `0`, `+0.05`, `+0.10`, `+0.25` (clamped), `-0.05`, `-0.10`,
  `-0.25` (clamped), `null` (muted).

## Out of scope (YAGNI)

- Tooltips / hover detail, click-through to month detail.
- Benchmark or alpha heatmap (only strategy returns).
- CSV export / download.
- Sorting / interactivity (static grid).
- Per-strategy customization (it's generic).

## Verification

- `npm run test` (vitest) green, new tests included.
- `npx tsc --noEmit` + `npm run build` clean (heed `web/AGENTS.md` Next-16 caution).
- Runtime: `next start` + load `/strategy/monthly_rotation`, `/strategy/ipo_edge`,
  `/strategy/momentum_edge`, `/strategy/pead` — confirm heatmap renders with real
  colored cells and the annual column; confirm a thin/empty strategy hides the section.
- Existing pages (leaderboard, home, other sections) still 200, unchanged.
