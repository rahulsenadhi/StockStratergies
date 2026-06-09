# Trades-Table Sorting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the generic `TradesTable` sortable by column (numeric-aware, empties last) so both the Trade History and Momentum Recent Breakouts sections sort on header click.

**Architecture:** Convert `components/trades-table.tsx` from a static server component into a `"use client"` TanStack sortable table (same pattern as `leaderboard-table.tsx`), driven by a pure exported `compareCells` comparator. No loader, page, or section changes — both consumers already pass `TradesData`.

**Tech Stack:** Next.js 16 (client component), TypeScript, @tanstack/react-table (already a dep), shadcn `@/components/ui/table`, Vitest.

**Spec:** `docs/superpowers/specs/2026-06-09-s4-trades-table-sorting-design.md`

**Grounding facts:**
- `TradesData = { columns: string[]; rows: Record<string, string>[] }` (`lib/data/strategies.ts:292`). Cells are raw CSV strings.
- Run tests from `web/`: `npm run test` (full) or `npm run test -- strategies` (single file). Test file: `web/tests/strategies.test.ts`; fixtures via `fsp.mkdtemp`; component pure-helpers tested there (e.g. `barWidthPct`, `cellColor`).
- `leaderboard-table.tsx` is the reference for the TanStack client pattern: `useReactTable` + `getCoreRowModel` + `getSortedRowModel`, header `onClick={h.column.getToggleSortingHandler()}`, indicator `{({ asc: " ↑", desc: " ↓" } as Record<string,string>)[h.column.getIsSorted() as string] ?? ""}`.
- Current `trades-table.tsx` keeps an empty-state guard: `if (!columns.length || !rows.length) return <p className="text-sm text-muted-foreground">No trades for this strategy.</p>;`
- Consumers (unchanged): `app/strategy/[id]/page.tsx` (`<TradesTable {...trades} />`) and `components/strategy-sections/momentum-edge.tsx` (Recent Breakouts).

---

### Task 1: `compareCells` comparator

**Files:**
- Create: `web/components/trades-table.tsx` (temporary minimal export — fully rewritten in Task 2; this task adds ONLY the `compareCells` function so its test can run). NOTE: the file already exists as a server component. For this task, ADD the `compareCells` export to the existing file WITHOUT removing the current `TradesTable` (Task 2 rewrites the whole file).
- Test: `web/tests/strategies.test.ts`

- [ ] **Step 1: Write the failing test**

Add `import { compareCells } from "@/components/trades-table";` near the other component imports at the top of `web/tests/strategies.test.ts` (e.g. beside `import { cellColor } from "@/components/monthly-heatmap";`). Then add this describe block:

```typescript
describe("compareCells", () => {
  it("numeric, not lexical: 2 before 10", () => {
    expect(compareCells("2", "10")).toBeLessThan(0);
    expect(compareCells("10", "2")).toBeGreaterThan(0);
  });
  it("handles negative numbers", () => {
    expect(compareCells("-2.3", "0")).toBeLessThan(0);
  });
  it("equal numbers -> 0", () => {
    expect(compareCells("100.5", "100.5")).toBe(0);
  });
  it("text compares lexically", () => {
    expect(compareCells("RELIANCE", "TCS")).toBeLessThan(0);
    expect(compareCells("TCS", "RELIANCE")).toBeGreaterThan(0);
  });
  it("ISO dates sort lexically (chronological)", () => {
    expect(compareCells("2024-01-05", "2024-02-01")).toBeLessThan(0);
  });
  it("mixed numeric/non-numeric falls back to string compare", () => {
    expect(compareCells("abc", "5")).toBe("abc".localeCompare("5"));
  });
});
```

- [ ] **Step 2: Run the test, verify it fails**

Run: `npm run test -- strategies`
Expected: FAIL — `compareCells` is not exported / not a function.

- [ ] **Step 3: Add `compareCells` to `web/components/trades-table.tsx`**

Add this exported function to the existing file (above the current `TradesTable` function is fine; do NOT delete `TradesTable` in this task):

```typescript
export function compareCells(a: string, b: string): number {
  const na = Number(a);
  const nb = Number(b);
  if (Number.isFinite(na) && Number.isFinite(nb)) return na - nb;
  return a.localeCompare(b);
}
```

- [ ] **Step 4: Run the test, verify it passes**

Run: `npm run test -- strategies`
Expected: PASS — all 6 `compareCells` cases green. (The existing `TradesTable` still compiles unchanged.)

- [ ] **Step 5: Commit**

```bash
git add web/components/trades-table.tsx web/tests/strategies.test.ts
git commit -m "feat(s4): compareCells numeric-aware comparator for trades table"
```

---

### Task 2: Sortable `TradesTable` (client component)

**Files:**
- Modify (full rewrite): `web/components/trades-table.tsx`

- [ ] **Step 1: Rewrite `web/components/trades-table.tsx`**

Replace the ENTIRE file contents with the following. This keeps the `compareCells` export from Task 1, keeps the same `TradesTable({ columns, rows }: TradesData)` signature (so both call sites are untouched), and adds TanStack client-side sorting:

```tsx
"use client";

import { useMemo, useState } from "react";
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  flexRender,
  type ColumnDef,
  type SortingState,
} from "@tanstack/react-table";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import type { TradesData } from "@/lib/data/strategies";

type TradeRow = Record<string, string>;

export function compareCells(a: string, b: string): number {
  const na = Number(a);
  const nb = Number(b);
  if (Number.isFinite(na) && Number.isFinite(nb)) return na - nb;
  return a.localeCompare(b);
}

function isEmptyCell(v: string | undefined): boolean {
  const t = (v ?? "").trim();
  return t === "" || t === "—";
}

export function TradesTable({ columns, rows }: TradesData) {
  const columnDefs = useMemo<ColumnDef<TradeRow>[]>(
    () =>
      columns.map((col) => ({
        id: col,
        header: col,
        accessorFn: (row) => (isEmptyCell(row[col]) ? undefined : row[col]),
        sortUndefined: "last",
        sortingFn: (rowA, rowB, columnId) =>
          compareCells(
            rowA.getValue<string>(columnId),
            rowB.getValue<string>(columnId),
          ),
        cell: (c) => {
          const v = c.row.original[col];
          return isEmptyCell(v) ? "—" : v;
        },
      })),
    [columns],
  );

  const [sorting, setSorting] = useState<SortingState>([]);

  const table = useReactTable({
    data: rows,
    columns: columnDefs,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  if (!columns.length || !rows.length) {
    return <p className="text-sm text-muted-foreground">No trades for this strategy.</p>;
  }

  return (
    <Table>
      <TableHeader>
        {table.getHeaderGroups().map((hg) => (
          <TableRow key={hg.id}>
            {hg.headers.map((h) => (
              <TableHead
                key={h.id}
                onClick={h.column.getToggleSortingHandler()}
                className={h.column.getCanSort() ? "cursor-pointer select-none" : ""}
              >
                {flexRender(h.column.columnDef.header, h.getContext())}
                {({ asc: " ↑", desc: " ↓" } as Record<string, string>)[
                  h.column.getIsSorted() as string
                ] ?? ""}
              </TableHead>
            ))}
          </TableRow>
        ))}
      </TableHeader>
      <TableBody>
        {table.getRowModel().rows.map((r) => (
          <TableRow key={r.id}>
            {r.getVisibleCells().map((cell) => (
              <TableCell key={cell.id}>
                {flexRender(cell.column.columnDef.cell, cell.getContext())}
              </TableCell>
            ))}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
```

Notes for the implementer:
- The empty-state guard is intentionally placed AFTER the hooks (`useMemo`/`useState`/`useReactTable`) so hooks run unconditionally — React rules-of-hooks. This matches `leaderboard-table.tsx`, which also calls hooks before its empty guard.
- `compareCells` is still exported (Task 1's test keeps importing it from this file).
- Do NOT change the import sites in `page.tsx` or `momentum-edge.tsx`.

- [ ] **Step 2: Verify the comparator test still passes**

Run: `npm run test -- strategies`
Expected: PASS — `compareCells` tests unchanged and still green.

- [ ] **Step 3: Typecheck + build**

Run: `npx tsc --noEmit` then `npm run build`
Expected: both clean. If the build flags a Next-16 / TanStack API, consult `web/AGENTS.md` and `node_modules/next/dist/docs/`. A `"use client"` component imported by a server component is valid.

- [ ] **Step 4: Runtime verify both consumers**

Build and start the prod server on a free port, then verify. Background the server (use the Bash tool's `run_in_background`), wait for boot, then:

```bash
# Trade History (strategy detail) renders the table with sortable headers:
curl -s localhost:3010/strategy/monthly_rotation | grep -c "cursor-pointer"
# Momentum Recent Breakouts also renders a sortable table:
curl -s localhost:3010/strategy/momentum_edge | grep -c "cursor-pointer"
# Unaffected pages still serve:
curl -s -o /dev/null -w "%{http_code}\n" localhost:3010/leaderboard
curl -s -o /dev/null -w "%{http_code}\n" localhost:3010/
```

Expected: the two `grep -c` counts are ≥ 1 (sortable headers present — `cursor-pointer` class appears once per sortable header). `/leaderboard` and `/` return `200`. Note: client-side sort reordering itself is interactive (JS), so curl only confirms the sortable markup renders; that is sufficient evidence for this slice. Stop the server when done — do not leave it running.

- [ ] **Step 5: Run the full test suite**

Run: `npm run test`
Expected: PASS — all tests (prior 85 + 6 new `compareCells` = 91).

- [ ] **Step 6: Commit**

```bash
git add web/components/trades-table.tsx
git commit -m "feat(s4): sortable TradesTable (numeric-aware, empties last)"
```

---

## Self-Review

**Spec coverage:**
- Convert `TradesTable` to client TanStack sortable, same props → Task 2. ✓
- `compareCells` numeric-aware + string fallback, exported & tested → Task 1. ✓
- Empties → `undefined` via accessor + `sortUndefined: "last"` (direction-independent) → Task 2. ✓
- Dynamic column defs from `columns` prop via `useMemo` → Task 2. ✓
- Initial `sorting = []` (unsorted CSV order), header click + ↑/↓ indicator, leaderboard markup → Task 2. ✓
- Empty-state guard preserved → Task 2. ✓
- No loader/page/section changes; both consumers untouched → Task 2 notes. ✓
- `compareCells` test cases (numeric not lexical, negatives, equal, text, ISO dates, mixed fallback) → Task 1. ✓
- Verification: tsc/build/runtime/other pages 200 → Task 2 steps 3-5. ✓

**Placeholder scan:** No TBD/TODO; every code step shows full code. Task 1 deliberately adds `compareCells` to the existing file and Task 2 fully rewrites it (including re-declaring `compareCells`) — consistent, not a placeholder.

**Type consistency:** `compareCells(a: string, b: string): number` identical in Task 1 and Task 2. `TradesData`/`Record<string,string>` props unchanged from the existing contract (`lib/data/strategies.ts:292`). `TradeRow` alias defined and used consistently in Task 2. TanStack imports match those proven in `leaderboard-table.tsx`. ✓
