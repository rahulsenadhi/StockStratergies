# S4 — Trades-Table Sorting

**Date:** 2026-06-09
**Slice:** S4 frontend (slice 8)
**Status:** Design approved, ready for plan

## Goal

Make the generic `TradesTable` sortable: clicking a column header sorts rows by that
column, toggling ascending/descending. Numeric columns sort numerically, text/date
columns sort as text. Blank cells always sink to the bottom. Both consumers of
`TradesTable` — the strategy-detail **Trade History** section and the Momentum
**Recent Breakouts** section — get sorting for free.

## Background / current state

- `components/trades-table.tsx` is a static **server** component: renders
  `{ columns, rows }` where `rows: Record<string, string>[]` (all cell values are
  strings). No interactivity. Row key is the array index.
- `TradesData = { columns: string[]; rows: Record<string, string>[] }`
  (`lib/data/strategies.ts:292`). Produced by `getTrades` (≤8 cols, Trade History) and
  `getRecentBreakouts` (full cols, Momentum section). Cells are **raw CSV values**
  (e.g. `"100.5"`, `"-2.3"`, `"2024-01-05"`, `"RELIANCE"`) — there is no `%`/`pct`
  formatting in `TradesData` (that lives only in KPI/heatmap components).
- `components/leaderboard-table.tsx` already implements the canonical client-side
  TanStack sortable pattern (header `onClick={h.column.getToggleSortingHandler()}`,
  ` ↑`/` ↓` indicator, `getSortedRowModel`). This slice reuses that pattern.

## Approach

Convert `TradesTable` into a `"use client"` TanStack sortable table. No loader
changes, no page/section changes — both consumers already pass `TradesData` and will
become sortable automatically. The `TradesData` type and the `getTrades` /
`getRecentBreakouts` contracts are unchanged.

### Sort comparator (pure, exported, unit-tested)

```ts
export function compareCells(a: string, b: string): number {
  const na = Number(a);
  const nb = Number(b);
  if (Number.isFinite(na) && Number.isFinite(nb)) return na - nb; // numeric columns
  return a.localeCompare(b);                                       // text / ISO dates
}
```

- If **both** cells parse as finite numbers → numeric compare (so `"2"` sorts before
  `"10"`, and `"-2.3"` before `"0"`).
- Otherwise → `localeCompare` (tickers as text; ISO `YYYY-MM-DD` dates sort correctly
  lexically).
- `compareCells` only ever receives **non-empty** strings; empties are filtered out
  upstream by the accessor (see below), so the `Number("") === 0` pitfall never fires.

### Empty cells always last (direction-independent)

A cell is "empty" when its trimmed value is `""` or `"—"` (em dash). The column
`accessorFn` returns `undefined` for empty cells and the original string otherwise.
The column sets `sortUndefined: "last"`. TanStack then keeps `undefined` values at the
bottom for **both** ascending and descending sorts — matching the leaderboard's
null-handling intent.

### Column definitions (built from the `columns` prop)

Build `ColumnDef<Record<string, string>>[]` with `useMemo(() => …, [columns])`. For
each column name `col`:

```ts
{
  id: col,
  header: col,
  accessorFn: (row) => {
    const v = (row[col] ?? "").trim();
    return v === "" || v === "—" ? undefined : row[col];
  },
  sortUndefined: "last",
  sortingFn: (rowA, rowB, columnId) =>
    compareCells(
      rowA.getValue<string>(columnId),
      rowB.getValue<string>(columnId),
    ),
  cell: (c) => {
    const v = c.row.original[col];
    return v == null || v === "" ? "—" : v;
  },
}
```

(When the framework invokes `sortingFn`, both `getValue` results are defined
non-empty strings — `undefined` rows are ordered by `sortUndefined` and never reach
the comparator.)

### Component behavior

- `"use client"`. Uses `useReactTable` with `getCoreRowModel` + `getSortedRowModel`,
  `state: { sorting }`, `onSortingChange: setSorting`.
- Initial `sorting` state = `[]` → **unsorted**, rows render in original CSV order
  until the user clicks a header. No default sort arrow.
- Header row mirrors `leaderboard-table.tsx`: `flexRender` the header,
  `onClick={h.column.getToggleSortingHandler()}`,
  `cursor-pointer select-none` when sortable, and the
  `{ asc: " ↑", desc: " ↓" }[sorted] ?? ""` indicator.
- Body rows keyed by TanStack `row.id`; cells via `flexRender`.
- Existing empty-state guard kept: `if (!columns.length || !rows.length)` →
  `<p className="text-sm text-muted-foreground">No trades for this strategy.</p>`.
- Uses the same shadcn `@/components/ui/table` primitives it already imports.

## Files

- **Modify (rewrite):** `web/components/trades-table.tsx` — client sortable table,
  export `compareCells`. Keep the named export `TradesTable({ columns, rows })` with
  the same `TradesData` props so both call sites are untouched.
- **Modify:** `web/tests/strategies.test.ts` — add `compareCells` unit tests.

No changes to `lib/data/strategies.ts`, `app/strategy/[id]/page.tsx`, or
`components/strategy-sections/momentum-edge.tsx`.

## Testing

`compareCells` (vitest, import from `@/components/trades-table`):
- numeric ordering, not lexical: `compareCells("2", "10") < 0`,
  `compareCells("10", "2") > 0`.
- negative numbers: `compareCells("-2.3", "0") < 0`.
- equal numbers: `compareCells("100.5", "100.5") === 0`.
- text: `compareCells("RELIANCE", "TCS") < 0`, `compareCells("TCS", "RELIANCE") > 0`.
- ISO dates lexical: `compareCells("2024-01-05", "2024-02-01") < 0`.
- mixed (one non-numeric) falls back to string compare:
  `compareCells("abc", "5")` equals `"abc".localeCompare("5")`.

Runtime verification:
- `/strategy/monthly_rotation` (and another strategy) — Trade History headers are
  clickable, sort toggles asc/desc with ` ↑`/` ↓`, a numeric column orders
  numerically, blank cells sink to the bottom, initial order = CSV order.
- `/strategy/momentum_edge` — Recent Breakouts table sorts the same way.
- Leaderboard and home pages still 200 (unaffected).

## Out of scope (YAGNI)

- Pagination / virtualization (long `rebalance_log`).
- Multi-column / shift-click sort.
- Filtering or column search.
- Per-column explicit type configuration.
- Numeric right-alignment / column formatting.

## Verification

- `npm run test` green (new `compareCells` tests included).
- `npx tsc --noEmit` + `npm run build` clean (heed `web/AGENTS.md` Next-16 caution).
- Runtime checks above.
