# S4 slice-1 — Next.js Local Leaderboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A local Next.js + TypeScript + Tailwind + shadcn/ui app in `web/` that renders the Strategy Leaderboard as a dense sortable ranked table, reading the existing local `strategies_index.json` + equity CSVs via a typed loader (the future-cloud seam). Streamlit untouched.

**Architecture:** `web/` is an isolated Next.js App-Router app. A typed loader (`lib/data/strategies.ts`) is the only module that touches data files. The page is a server component (reads files at request time); only the table is a client component (TanStack sort). Sparkline is inline SVG. Pure modules (loader, format) are TDD'd with Vitest; the page/components are verified by build + running the app.

**Tech Stack:** Next.js 15 (App Router), TypeScript, Tailwind, shadcn/ui, @tanstack/react-table, Vitest, Node 24/npm 11.

Spec: `docs/superpowers/specs/2026-06-05-s4-nextjs-leaderboard-design.md`.

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `web/` (scaffold) | Next.js app: package.json, tsconfig, next.config, tailwind, app/layout.tsx, app/globals.css | Create (Task 1) |
| `web/.env.local` | `DATA_DIR=".."` | Create (Task 1) |
| `web/.gitignore` | ignore node_modules/.next (create-next-app provides) | Auto |
| `web/vitest.config.ts` | Vitest node env | Create (Task 2) |
| `web/lib/format.ts` | `pct`, `signed`, `naDash` | Create (Task 2) |
| `web/lib/data/strategies.ts` | `Strategy`/`Kpis` types, `mapStrategy`, `getStrategies`, `getEquitySeries` | Create (Tasks 3–4) |
| `web/tests/format.test.ts`, `web/tests/strategies.test.ts` | Vitest unit tests + fixtures | Create (Tasks 2–4) |
| `web/components/sparkline.tsx` | inline-SVG sparkline | Create (Task 5) |
| `web/components/kpi-cell.tsx` | colored +/- KPI value; null→"—" | Create (Task 5) |
| `web/components/leaderboard-table.tsx` | client TanStack sortable table | Create (Task 6) |
| `web/app/layout.tsx`, `web/app/page.tsx`, `web/app/leaderboard/page.tsx` | root layout, redirect, RSC leaderboard page | Create (Tasks 1,7) |

**Conventions:** Run all `npm`/`npx` from inside `web/`. The Bash tool persists cwd, but prefer absolute or `cd web && ...` in one command. Commit from the repo root (`git -C ..` or cd back). Import alias `@/*` → `web/`.

**NON-DESTRUCTIVE:** Do not modify any existing Python/Streamlit file. `web/` is additive.

---

## Task 1: Scaffold the Next.js app

**Files:** Create `web/` via tooling.

- [ ] **Step 1: Scaffold with create-next-app (non-interactive)**

Run from the repo root:
```bash
npx --yes create-next-app@latest web --ts --tailwind --app --eslint --no-src-dir --import-alias "@/*" --use-npm --no-turbopack
```
Expected: creates `web/` with `app/`, `package.json`, `tsconfig.json`, `tailwind.config.ts`, `app/globals.css`. (If `--no-turbopack` is rejected by this CNA version, drop that one flag and re-run; accept the default. If it asks any prompt, the flags should prevent it — if not, accept defaults.)

- [ ] **Step 2: Install runtime + dev deps**

```bash
cd web && npm install @tanstack/react-table && npm install -D vitest
```
Expected: installs cleanly.

- [ ] **Step 3: Init shadcn/ui + add components**

```bash
cd web && npx --yes shadcn@latest init -d && npx --yes shadcn@latest add table badge
```
Expected: creates `components/ui/table.tsx`, `components/ui/badge.tsx`, `lib/utils.ts`, updates `app/globals.css` with the shadcn theme. (If `init -d` prompts, accept defaults: New York style, neutral base, CSS variables yes.)

- [ ] **Step 4: Create `web/.env.local`**

```
DATA_DIR=..
```

- [ ] **Step 5: Verify the scaffold builds and runs**

```bash
cd web && npm run build
```
Expected: build succeeds (default starter page compiles).

- [ ] **Step 6: Commit**

```bash
cd .. && git add web .gitignore && git commit -m "feat(s4): scaffold Next.js leaderboard app (web/)"
```
(create-next-app writes `web/.gitignore` ignoring `node_modules`/`.next`; confirm those are NOT staged.)

---

## Task 2: `lib/format.ts` (TDD)

**Files:**
- Create: `web/vitest.config.ts`, `web/lib/format.ts`, `web/tests/format.test.ts`

- [ ] **Step 1: Add Vitest config + test script**

Create `web/vitest.config.ts`:
```ts
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: { environment: "node", include: ["tests/**/*.test.ts"] },
  resolve: { alias: { "@": new URL(".", import.meta.url).pathname } },
});
```
Add to `web/package.json` "scripts": `"test": "vitest run"`.

- [ ] **Step 2: Write failing tests**

Create `web/tests/format.test.ts`:
```ts
import { describe, it, expect } from "vitest";
import { pct, signed, naDash } from "@/lib/format";

describe("format", () => {
  it("pct: positive gets +, scaled to %", () => {
    expect(pct(0.261)).toBe("+26.1%");
  });
  it("pct: negative keeps -", () => {
    expect(pct(-0.114)).toBe("-11.4%");
  });
  it("pct: null -> dash", () => {
    expect(pct(null)).toBe("—");
  });
  it("signed: fixed decimals; null -> dash", () => {
    expect(signed(2.453)).toBe("2.45");
    expect(signed(null)).toBe("—");
  });
  it("naDash: passes through or dashes null", () => {
    expect(naDash(3)).toBe("3");
    expect(naDash(null)).toBe("—");
  });
});
```

- [ ] **Step 3: Run, verify fail**

Run: `cd web && npm test`
Expected: FAIL (cannot resolve `@/lib/format`).

- [ ] **Step 4: Implement `web/lib/format.ts`**

```ts
export function pct(v: number | null | undefined): string {
  if (v == null) return "—";
  return `${v >= 0 ? "+" : ""}${(v * 100).toFixed(1)}%`;
}

export function signed(v: number | null | undefined, decimals = 2): string {
  if (v == null) return "—";
  return v.toFixed(decimals);
}

export function naDash(v: number | string | null | undefined): string {
  if (v == null) return "—";
  return String(v);
}
```

- [ ] **Step 5: Run, verify pass**

Run: `cd web && npm test`
Expected: PASS (5 passed).

- [ ] **Step 6: Commit**

```bash
cd .. && git add web/vitest.config.ts web/lib/format.ts web/tests/format.test.ts web/package.json && git commit -m "feat(s4): format helpers (pct/signed/naDash) + vitest"
```

---

## Task 3: `getStrategies` loader (TDD)

**Files:**
- Create: `web/lib/data/strategies.ts`, `web/tests/strategies.test.ts`, fixture `web/tests/fixtures/strategies_index.json`

- [ ] **Step 1: Create the fixture**

Create `web/tests/fixtures/strategies_index.json`:
```json
{
  "strategies": [
    {"id": "a", "name": "Alpha", "type": "Quant", "status": "Live",
     "kpis_inline": {"cagr": 0.21, "total_return": 0.8, "volatility": 0.15, "sharpe": 1.5,
        "max_dd": -0.11, "calmar": 1.9, "win_rate": null, "num_trades": 35, "alpha": 0.14, "final_equity": 180},
     "rank": 2, "rank_score": 0.4, "equity_csv": "eq_a.csv"},
    {"id": "b", "name": "Bravo", "type": "Earnings", "status": "Paper",
     "kpis_inline": {"cagr": 0.26, "total_return": 1.0, "volatility": 0.1, "sharpe": 2.4,
        "max_dd": -0.03, "calmar": 8.4, "win_rate": 1.0, "num_trades": 12, "alpha": 0.2, "final_equity": 200},
     "rank": 1, "rank_score": 1.3, "equity_csv": "eq_b.csv"},
    {"id": "c", "name": "Charlie", "type": "Custom", "status": "Research",
     "kpis_error": "missing CSV: x", "equity_csv": "missing.csv"}
  ]
}
```

- [ ] **Step 2: Write failing tests**

Create `web/tests/strategies.test.ts`:
```ts
import { describe, it, expect } from "vitest";
import { getStrategies, mapStrategy } from "@/lib/data/strategies";
import path from "path";

const FIX = path.join(import.meta.dirname, "fixtures");

describe("getStrategies", () => {
  it("maps fields and sorts by rank asc", async () => {
    const s = await getStrategies(FIX);
    expect(s.map((x) => x.id)).toEqual(["b", "a", "c"]); // b rank1, a rank2, c unranked last
    expect(s[1].kpis.cagr).toBe(0.21);
    expect(s[1].kpis.maxDd).toBe(-0.11);
  });
  it("preserves null win_rate (not 0)", async () => {
    const s = await getStrategies(FIX);
    const a = s.find((x) => x.id === "a")!;
    expect(a.kpis.winRate).toBeNull();
  });
  it("includes errored strategy with null kpis + kpisError", async () => {
    const s = await getStrategies(FIX);
    const c = s.find((x) => x.id === "c")!;
    expect(c.kpisError).toBe("missing CSV: x");
    expect(c.kpis.winRate).toBeNull();
    expect(c.rank).toBeNull();
  });
  it("missing index file -> []", async () => {
    expect(await getStrategies("/no/such/dir")).toEqual([]);
  });
});

describe("mapStrategy", () => {
  it("null kpis_inline -> numeric defaults 0, nullables null", () => {
    const m = mapStrategy({ id: "z", name: "Z" });
    expect(m.kpis.cagr).toBe(0);
    expect(m.kpis.winRate).toBeNull();
    expect(m.kpis.alpha).toBeNull();
  });
});
```

- [ ] **Step 3: Run, verify fail**

Run: `cd web && npm test`
Expected: FAIL (cannot resolve `@/lib/data/strategies`).

- [ ] **Step 4: Implement `web/lib/data/strategies.ts` (getStrategies portion)**

```ts
import { promises as fs } from "fs";
import path from "path";

const DEFAULT_DATA_DIR = process.env.DATA_DIR ?? "..";

export type Kpis = {
  cagr: number; totalReturn: number; volatility: number; sharpe: number; maxDd: number;
  calmar: number | null; winRate: number | null; numTrades: number;
  alpha: number | null; finalEquity: number;
};

export type Strategy = {
  id: string; name: string; type: string; status: string;
  kpis: Kpis; rank: number | null; rankScore: number | null;
  equityCsv: string | null; kpisError?: string;
};

const num = (v: unknown): number => (typeof v === "number" && !Number.isNaN(v) ? v : 0);
const numOrNull = (v: unknown): number | null =>
  typeof v === "number" && !Number.isNaN(v) ? v : null;

export function mapStrategy(raw: any): Strategy {
  const k = raw.kpis_inline ?? {};
  const s: Strategy = {
    id: raw.id,
    name: raw.name ?? raw.id,
    type: raw.type ?? "—",
    status: raw.status ?? "—",
    kpis: {
      cagr: num(k.cagr), totalReturn: num(k.total_return), volatility: num(k.volatility),
      sharpe: num(k.sharpe), maxDd: num(k.max_dd), calmar: numOrNull(k.calmar),
      winRate: numOrNull(k.win_rate), numTrades: num(k.num_trades),
      alpha: numOrNull(k.alpha), finalEquity: num(k.final_equity),
    },
    rank: numOrNull(raw.rank),
    rankScore: numOrNull(raw.rank_score),
    equityCsv: raw.equity_csv ?? null,
  };
  if (raw.kpis_error) s.kpisError = raw.kpis_error;
  return s;
}

export async function getStrategies(dataDir: string = DEFAULT_DATA_DIR): Promise<Strategy[]> {
  try {
    const txt = await fs.readFile(path.join(dataDir, "strategies_index.json"), "utf-8");
    const data = JSON.parse(txt);
    const list: Strategy[] = (data.strategies ?? []).map(mapStrategy);
    list.sort((a, b) => (a.rank ?? 9999) - (b.rank ?? 9999));
    return list;
  } catch {
    return [];
  }
}
```

- [ ] **Step 5: Run, verify pass**

Run: `cd web && npm test`
Expected: PASS (format + strategies tests).

- [ ] **Step 6: Commit**

```bash
cd .. && git add web/lib/data/strategies.ts web/tests/strategies.test.ts web/tests/fixtures/strategies_index.json && git commit -m "feat(s4): typed strategies loader (getStrategies + mapStrategy)"
```

---

## Task 4: `getEquitySeries` (TDD)

**Files:**
- Modify: `web/lib/data/strategies.ts`
- Modify: `web/tests/strategies.test.ts`; add fixtures `web/tests/fixtures/eq_a.csv`, `eq_b.csv`

- [ ] **Step 1: Create equity fixtures**

`web/tests/fixtures/eq_a.csv`:
```
Date,Portfolio_Value,Benchmark_Value
2024-01-01,100,100
2024-01-02,110,101
2024-01-03,120,102
```
`web/tests/fixtures/eq_b.csv`:
```
Date,Equity,Cash
2024-01-01,100,5
2024-01-02,90,5
2024-01-03,130,5
```

- [ ] **Step 2: Append failing tests**

Add to `web/tests/strategies.test.ts`:
```ts
import { getEquitySeries } from "@/lib/data/strategies";

describe("getEquitySeries", () => {
  it("reads Portfolio_Value column", async () => {
    expect(await getEquitySeries("eq_a.csv", FIX)).toEqual([100, 110, 120]);
  });
  it("reads Equity column", async () => {
    expect(await getEquitySeries("eq_b.csv", FIX)).toEqual([100, 90, 130]);
  });
  it("missing file -> []", async () => {
    expect(await getEquitySeries("nope.csv", FIX)).toEqual([]);
  });
  it("null path -> []", async () => {
    expect(await getEquitySeries(null, FIX)).toEqual([]);
  });
});
```

- [ ] **Step 3: Run, verify fail**

Run: `cd web && npm test`
Expected: FAIL (`getEquitySeries` not exported).

- [ ] **Step 4: Implement (append to `web/lib/data/strategies.ts`)**

```ts
const EQUITY_COLS = ["Portfolio_Value", "Equity", "equity"];
const MAX_POINTS = 80;

export async function getEquitySeries(
  csv: string | null,
  dataDir: string = DEFAULT_DATA_DIR,
): Promise<number[]> {
  if (!csv) return [];
  try {
    const txt = await fs.readFile(path.join(dataDir, csv), "utf-8");
    const lines = txt.trim().split(/\r?\n/);
    if (lines.length < 2) return [];
    const header = lines[0].split(",");
    let idx = -1;
    for (const c of EQUITY_COLS) {
      idx = header.indexOf(c);
      if (idx >= 0) break;
    }
    if (idx < 0) {
      const first = lines[1].split(",");
      idx = header.findIndex((_, i) => i > 0 && !Number.isNaN(Number(first[i])));
    }
    if (idx < 0) return [];
    const vals = lines
      .slice(1)
      .map((l) => Number(l.split(",")[idx]))
      .filter((v) => !Number.isNaN(v));
    const step = Math.max(1, Math.floor(vals.length / MAX_POINTS));
    return vals.filter((_, i) => i % step === 0);
  } catch {
    return [];
  }
}
```

- [ ] **Step 5: Run, verify pass**

Run: `cd web && npm test`
Expected: PASS (all loader + format tests).

- [ ] **Step 6: Commit**

```bash
cd .. && git add web/lib/data/strategies.ts web/tests/strategies.test.ts web/tests/fixtures/ && git commit -m "feat(s4): getEquitySeries (column resolution + downsample)"
```

---

## Task 5: presentational components (sparkline + kpi-cell)

**Files:**
- Create: `web/components/sparkline.tsx`, `web/components/kpi-cell.tsx`

- [ ] **Step 1: Implement `web/components/sparkline.tsx`**

```tsx
export function Sparkline({
  points, width = 72, height = 20,
}: { points: number[]; width?: number; height?: number }) {
  if (!points || points.length < 2) {
    return <svg width={width} height={height} aria-hidden />;
  }
  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = max - min || 1;
  const step = width / (points.length - 1);
  const d = points
    .map((p, i) => {
      const x = (i * step).toFixed(1);
      const y = (height - ((p - min) / range) * height).toFixed(1);
      return `${i === 0 ? "M" : "L"}${x},${y}`;
    })
    .join(" ");
  const up = points[points.length - 1] >= points[0];
  return (
    <svg width={width} height={height} aria-hidden>
      <path d={d} fill="none" stroke={up ? "#22c55e" : "#ef4444"} strokeWidth={1.5} />
    </svg>
  );
}
```

- [ ] **Step 2: Implement `web/components/kpi-cell.tsx`**

```tsx
import { pct, signed } from "@/lib/format";

export function KpiCell({
  value, kind = "pct",
}: { value: number | null; kind?: "pct" | "num" }) {
  if (value == null) return <span className="text-muted-foreground">—</span>;
  const cls = value >= 0 ? "text-green-500" : "text-red-500";
  return <span className={cls}>{kind === "pct" ? pct(value) : signed(value)}</span>;
}
```

- [ ] **Step 3: Typecheck**

Run: `cd web && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
cd .. && git add web/components/sparkline.tsx web/components/kpi-cell.tsx && git commit -m "feat(s4): sparkline + kpi-cell components"
```

---

## Task 6: `leaderboard-table.tsx` (client, sortable)

**Files:**
- Create: `web/components/leaderboard-table.tsx`

- [ ] **Step 1: Define the row type + implement the client table**

```tsx
"use client";

import { useState } from "react";
import {
  useReactTable, getCoreRowModel, getSortedRowModel,
  flexRender, type ColumnDef, type SortingState,
} from "@tanstack/react-table";
import {
  Table, TableБody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Sparkline } from "@/components/sparkline";
import { KpiCell } from "@/components/kpi-cell";
import type { Strategy } from "@/lib/data/strategies";

export type Row = Strategy & { series: number[] };

const columns: ColumnDef<Row>[] = [
  { accessorKey: "rank", header: "#", cell: (c) => <span className="font-bold text-green-500">{c.getValue<number | null>() ?? "—"}</span> },
  { accessorKey: "name", header: "Strategy",
    cell: (c) => (
      <div>
        <div className="font-medium">{c.row.original.name}</div>
        <div className="text-xs text-muted-foreground">{c.row.original.type} · {c.row.original.status}</div>
      </div>
    ) },
  { id: "cagr", accessorFn: (r) => r.kpis.cagr, header: "CAGR", cell: (c) => <KpiCell value={c.row.original.kpis.cagr} /> },
  { id: "sharpe", accessorFn: (r) => r.kpis.sharpe, header: "Sharpe", cell: (c) => <KpiCell value={c.row.original.kpis.sharpe} kind="num" /> },
  { id: "maxDd", accessorFn: (r) => r.kpis.maxDd, header: "Max DD", cell: (c) => <KpiCell value={c.row.original.kpis.maxDd} /> },
  { id: "winRate", accessorFn: (r) => r.kpis.winRate ?? -1, header: "Win", cell: (c) => <KpiCell value={c.row.original.kpis.winRate} /> },
  { id: "alpha", accessorFn: (r) => r.kpis.alpha ?? 0, header: "Alpha", cell: (c) => <KpiCell value={c.row.original.kpis.alpha} /> },
  { id: "rankScore", accessorFn: (r) => r.rankScore ?? -999, header: "Score", cell: (c) => <KpiCell value={c.row.original.rankScore} kind="num" /> },
  { id: "trend", header: "Trend", enableSorting: false, cell: (c) => <Sparkline points={c.row.original.series} /> },
];

export function LeaderboardTable({ rows }: { rows: Row[] }) {
  const [sorting, setSorting] = useState<SortingState>([{ id: "rank", desc: false }]);
  const table = useReactTable({
    data: rows, columns, state: { sorting }, onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(), getSortedRowModel: getSortedRowModel(),
  });
  if (!rows.length) {
    return <p className="text-muted-foreground">No strategies — run a backtest.</p>;
  }
  return (
    <Table>
      <TableHeader>
        {table.getHeaderGroups().map((hg) => (
          <TableRow key={hg.id}>
            {hg.headers.map((h) => (
              <TableHead key={h.id} onClick={h.column.getToggleSortingHandler()}
                className={h.column.getCanSort() ? "cursor-pointer select-none" : ""}>
                {flexRender(h.column.columnDef.header, h.getContext())}
                {{ asc: " ↑", desc: " ↓" }[h.column.getIsSorted() as string] ?? ""}
              </TableHead>
            ))}
          </TableRow>
        ))}
      </TableHeader>
      <TableBody>
        {table.getRowModel().rows.map((r) => (
          <TableRow key={r.id}>
            {r.getVisibleCells().map((cell) => (
              <TableCell key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</TableCell>
            ))}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
```
> IMPORTANT: the import line above intentionally shows `TableБody` with a typo to force you to read it — write the correct shadcn import: `Table, TableBody, TableCell, TableHead, TableHeader, TableRow` from `@/components/ui/table`. Verify the exact exports in the generated `web/components/ui/table.tsx` before finalizing.

- [ ] **Step 2: Typecheck**

Run: `cd web && npx tsc --noEmit`
Expected: no errors (fix the import typo flagged above; confirm `@tanstack/react-table` types resolve).

- [ ] **Step 3: Commit**

```bash
cd .. && git add web/components/leaderboard-table.tsx && git commit -m "feat(s4): sortable leaderboard table (TanStack)"
```

---

## Task 7: pages wiring (layout, redirect, RSC leaderboard)

**Files:**
- Modify: `web/app/layout.tsx` (from scaffold), `web/app/page.tsx`
- Create: `web/app/leaderboard/page.tsx`

- [ ] **Step 1: Root layout — dark theme**

Replace `web/app/layout.tsx` body to apply the `dark` class:
```tsx
import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = { title: "Strategy Leaderboard", description: "NSE strategy hub" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="bg-background text-foreground antialiased">{children}</body>
    </html>
  );
}
```

- [ ] **Step 2: Home redirect**

Replace `web/app/page.tsx`:
```tsx
import { redirect } from "next/navigation";
export default function Home() { redirect("/leaderboard"); }
```

- [ ] **Step 3: Leaderboard RSC page**

Create `web/app/leaderboard/page.tsx`:
```tsx
import { getStrategies, getEquitySeries } from "@/lib/data/strategies";
import { LeaderboardTable, type Row } from "@/components/leaderboard-table";

export const dynamic = "force-dynamic"; // read files at request time

export default async function LeaderboardPage() {
  const strategies = await getStrategies();
  const rows: Row[] = await Promise.all(
    strategies.map(async (s) => ({ ...s, series: await getEquitySeries(s.equityCsv) })),
  );
  return (
    <main className="mx-auto max-w-5xl p-8">
      <h1 className="mb-1 text-2xl font-bold">Strategy Leaderboard</h1>
      <p className="mb-6 text-sm text-muted-foreground">
        Ranked by composite score · {rows.length} strategies
      </p>
      <LeaderboardTable rows={rows} />
    </main>
  );
}
```

- [ ] **Step 4: Build**

Run: `cd web && npm run build`
Expected: build succeeds; `/leaderboard` compiled.

- [ ] **Step 5: Commit**

```bash
cd .. && git add web/app && git commit -m "feat(s4): layout + leaderboard RSC page wiring"
```

---

## Task 8: Verification + memory

**Files:** none (verify + memory).

- [ ] **Step 1: Full Vitest + typecheck + build**

```bash
cd web && npm test && npx tsc --noEmit && npm run build
```
Expected: all green.

- [ ] **Step 2: Run the app + verify the real surface**

```bash
cd web && npm run dev
```
Then load `http://localhost:3000/leaderboard` in a browser. Confirm:
- 4 strategies render, default-sorted by rank with **PEAD #1**, Monthly #2, IPO #3, Momentum #4.
- Clicking the **CAGR**/**Sharpe**/**Score** headers re-sorts (arrow indicator toggles).
- Sparklines draw for each row.
- Monthly's **Win** cell shows **"—"** (null win_rate), not "0%" or a crash.
Stop the dev server after (Ctrl-C).

> If `npm run dev` can't be driven interactively in your environment, use the `verify` skill / AppTest-equivalent: build, then `npx next start` and curl `/leaderboard`, OR render-check via a Playwright smoke. Report which path used. The data-correctness (PEAD #1, null win-rate) is the key assertion.

- [ ] **Step 3: Update memory (controller does this — not a subagent)**

Add `s4_nextjs_frontend.md` (slice-1 done: web/ Next.js app, leaderboard, typed loader seam, local-only, Streamlit coexists) + `MEMORY.md` index line. Note S4 is now in-progress (slice 1 of N).

---

## Self-Review

**Spec coverage:**
- §4 file structure (web/ scaffold, lib/data, components, app pages) → Tasks 1,5,6,7. ✓
- §5 typed data contract (Kpis/Strategy, getStrategies null-preserving + sorted, getEquitySeries column-resolution+downsample, DATA_DIR) → Tasks 3,4. ✓
- §6 data flow (RSC reads files, passes series, client TanStack sort, format) → Tasks 6,7. ✓
- §7 error handling (missing index → [], kpis_error row renders "—", missing equity → [], null winRate → "—", per-file try/catch) → Tasks 3,4,5,6 (empty-state in table; null cells in KpiCell). ✓
- §8 testing (Vitest loader+format, typecheck/build, run-the-app verification) → Tasks 2,3,4,8. ✓
- §9 open Qs (port 3000, shadcn dark default, equity path via DATA_DIR, read-only, gitignore node_modules/.next) → Tasks 1,7,8. ✓

**Placeholder scan:** every code step is complete. The one deliberate `TableБody` typo is a read-the-code gate with an explicit instruction to correct it (not a placeholder). No TBD/TODO.

**Type consistency:** `Strategy`/`Kpis` field names (cagr, maxDd, winRate|null, alpha|null, calmar|null, numTrades, rankScore) are identical across loader (Task 3), components (Task 5), table (Task 6), page (Task 7). `getStrategies(dataDir?)`, `getEquitySeries(csv|null, dataDir?)`, `mapStrategy(raw)`, `Row = Strategy & {series}`, `LeaderboardTable({rows})`, `Sparkline({points})`, `KpiCell({value, kind})` — consistent. ✓
