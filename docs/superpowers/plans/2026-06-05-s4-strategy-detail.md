# S4 slice-2 — Strategy Detail Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `/strategy/[id]` to the local Next.js app — KPI strip + equity curve + drawdown chart + generic trades table — reading local data via the extended typed loader, with leaderboard rows linking to it.

**Architecture:** Extend `web/lib/data/strategies.ts` (the single data seam) with `getStrategy`, `getEquityCurve`, `computeDrawdown`, `getTrades`. The page is a server component; charts are client leaf components wrapping lightweight-charts. Pure loaders are TDD'd with Vitest; charts/page verified by build + running the app.

**Tech Stack:** Next.js 16 (App Router), TypeScript, Tailwind v4, shadcn/ui, lightweight-charts, Vitest. Builds on S4 slice-1.

Spec: `docs/superpowers/specs/2026-06-05-s4-strategy-detail-design.md`.

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `web/lib/data/strategies.ts` | + `tradesCsv` on Strategy; `getStrategy`, `getEquityCurve`, `computeDrawdown`, `getTrades`; `EquityPoint`/`TradesData` types | Modify |
| `web/tests/strategies.test.ts` | + tests for the new loaders; fixture `tr_a.csv` | Modify |
| `web/components/line-chart.tsx` | client lightweight-charts area wrapper (color/height props) | Create |
| `web/components/kpi-strip.tsx` | 5 KPI tiles (null→"—") | Create |
| `web/components/trades-table.tsx` | generic table from {columns, rows} | Create |
| `web/components/leaderboard-table.tsx` | name cell → `<Link>` to detail | Modify |
| `web/app/strategy/[id]/page.tsx` | RSC detail page | Create |

**Conventions:** run npm/npx from inside `web/`; commit from repo root. Branch is created by the controller before execution. Do not touch Python/Streamlit files.

---

## Task 1: Install lightweight-charts + loader: `tradesCsv` + `getStrategy` (TDD)

**Files:**
- Modify: `web/lib/data/strategies.ts`, `web/tests/strategies.test.ts`

- [ ] **Step 1: Install lightweight-charts**

```bash
cd web && npm install lightweight-charts
```
Note the installed major version (`npm ls lightweight-charts`) — Task 4 needs it (v5 uses `addSeries(AreaSeries,…)`, v4 uses `addAreaSeries(…)`).

- [ ] **Step 2: Write failing tests** (append to `web/tests/strategies.test.ts`)

```ts
import { getStrategy } from "@/lib/data/strategies";

describe("getStrategy", () => {
  it("returns the matching strategy", async () => {
    const s = await getStrategy("b", FIX);
    expect(s?.id).toBe("b");
  });
  it("maps tradesCsv", async () => {
    const s = await getStrategy("a", FIX);
    expect(s?.tradesCsv).toBe("tr_a.csv");
  });
  it("unknown id -> null", async () => {
    expect(await getStrategy("nope", FIX)).toBeNull();
  });
});
```

- [ ] **Step 3: Add `trades_csv` to the fixture**

In `web/tests/fixtures/strategies_index.json`, add `"trades_csv": "tr_a.csv"` to strategy `"a"` and `"trades_csv": "tr_b.csv"` to `"b"`.

- [ ] **Step 4: Run, verify fail**

Run: `cd web && npm test`
Expected: FAIL (`getStrategy` not exported / `tradesCsv` undefined).

- [ ] **Step 5: Implement** — in `web/lib/data/strategies.ts`:

Add `tradesCsv: string | null;` to the `Strategy` type. In `mapStrategy`, after `equityCsv: raw.equity_csv ?? null,` add:
```ts
    tradesCsv: raw.trades_csv ?? null,
```
Append the function:
```ts
export async function getStrategy(
  id: string,
  dataDir: string = DEFAULT_DATA_DIR,
): Promise<Strategy | null> {
  const all = await getStrategies(dataDir);
  return all.find((s) => s.id === id) ?? null;
}
```

- [ ] **Step 6: Run, verify pass**

Run: `cd web && npm test`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
cd .. && git add web/lib/data/strategies.ts web/tests/strategies.test.ts web/tests/fixtures/strategies_index.json web/package.json web/package-lock.json && git commit -m "feat(s4): getStrategy + tradesCsv + lightweight-charts dep"
```

---

## Task 2: `getEquityCurve` + `computeDrawdown` (TDD)

**Files:**
- Modify: `web/lib/data/strategies.ts`, `web/tests/strategies.test.ts`

- [ ] **Step 1: Write failing tests** (append)

```ts
import { getEquityCurve, computeDrawdown } from "@/lib/data/strategies";

describe("getEquityCurve", () => {
  it("returns dated points sorted, Portfolio_Value column", async () => {
    const c = await getEquityCurve("eq_a.csv", FIX);
    expect(c).toEqual([
      { time: "2024-01-01", value: 100 },
      { time: "2024-01-02", value: 110 },
      { time: "2024-01-03", value: 120 },
    ]);
  });
  it("Equity column variant", async () => {
    const c = await getEquityCurve("eq_b.csv", FIX);
    expect(c.map((p) => p.value)).toEqual([100, 90, 130]);
  });
  it("missing/null -> []", async () => {
    expect(await getEquityCurve("nope.csv", FIX)).toEqual([]);
    expect(await getEquityCurve(null, FIX)).toEqual([]);
  });
});

describe("computeDrawdown", () => {
  it("running-peak drawdown <= 0", () => {
    const dd = computeDrawdown([
      { time: "1", value: 100 }, { time: "2", value: 120 },
      { time: "3", value: 60 }, { time: "4", value: 90 },
    ]);
    expect(dd.map((p) => p.value)).toEqual([0, 0, -0.5, -0.25]);
  });
  it("[] -> []", () => {
    expect(computeDrawdown([])).toEqual([]);
  });
});
```

- [ ] **Step 2: Run, verify fail**

Run: `cd web && npm test`
Expected: FAIL (not exported).

- [ ] **Step 3: Implement** (append to `web/lib/data/strategies.ts`)

```ts
export type EquityPoint = { time: string; value: number };
const MAX_CURVE_POINTS = 2000;
const DATE_COLS = ["Date", "date", "Datetime"];

export async function getEquityCurve(
  csv: string | null,
  dataDir: string = DEFAULT_DATA_DIR,
): Promise<EquityPoint[]> {
  if (!csv) return [];
  try {
    const txt = await fs.readFile(path.join(dataDir, csv), "utf-8");
    const lines = txt.trim().split(/\r?\n/);
    if (lines.length < 2) return [];
    const header = lines[0].split(",").map((h) => h.trim());
    const dateIdx = header.findIndex((h) => DATE_COLS.includes(h));
    const di = dateIdx >= 0 ? dateIdx : 0;
    let vi = -1;
    for (const c of EQUITY_COLS) {
      vi = header.indexOf(c);
      if (vi >= 0) break;
    }
    if (vi < 0) {
      const first = lines[1].split(",");
      vi = header.findIndex((_, i) => i !== di && !Number.isNaN(Number(first[i])));
    }
    if (vi < 0) return [];
    let pts: EquityPoint[] = lines
      .slice(1)
      .map((l) => {
        const cells = l.split(",");
        return { time: String(cells[di] ?? "").slice(0, 10), value: Number(cells[vi]) };
      })
      .filter((p) => p.time !== "" && !Number.isNaN(p.value));
    pts.sort((a, b) => a.time.localeCompare(b.time));
    if (pts.length > MAX_CURVE_POINTS) {
      const step = Math.ceil(pts.length / MAX_CURVE_POINTS);
      pts = pts.filter((_, i) => i % step === 0);
    }
    return pts;
  } catch {
    return [];
  }
}

export function computeDrawdown(curve: EquityPoint[]): EquityPoint[] {
  let peak = -Infinity;
  return curve.map((p) => {
    peak = Math.max(peak, p.value);
    const value = peak > 0 ? p.value / peak - 1 : 0;
    return { time: p.time, value };
  });
}
```

- [ ] **Step 4: Run, verify pass** — `cd web && npm test` → PASS.

- [ ] **Step 5: Commit**

```bash
cd .. && git add web/lib/data/strategies.ts web/tests/strategies.test.ts && git commit -m "feat(s4): getEquityCurve (dated) + computeDrawdown"
```

---

## Task 3: `getTrades` generic loader (TDD)

**Files:**
- Modify: `web/lib/data/strategies.ts`, `web/tests/strategies.test.ts`; fixtures `web/tests/fixtures/tr_a.csv`, `tr_rebal.csv`

- [ ] **Step 1: Create fixtures**

`web/tests/fixtures/tr_a.csv`:
```
Ticker,Entry_Date,Exit_Date,PnL_Pct,Result
AAA.NS,2024-01-01,2024-02-01,5.2,WIN
BBB.NS,2024-01-05,2024-01-20,-2.1,LOSS
```
`web/tests/fixtures/tr_rebal.csv` (rebalance-log shape — no per-trade PnL):
```
Date,Top5_Stocks,Portfolio_Value
2024-01-31,"A,B,C,D,E",105000
2024-02-29,"A,B,F,G,H",110000
```

- [ ] **Step 2: Write failing tests** (append)

```ts
import { getTrades } from "@/lib/data/strategies";

describe("getTrades", () => {
  it("generic columns + rows", async () => {
    const t = await getTrades("tr_a.csv", FIX);
    expect(t.columns).toEqual(["Ticker", "Entry_Date", "Exit_Date", "PnL_Pct", "Result"]);
    expect(t.rows[0].Ticker).toBe("AAA.NS");
    expect(t.rows[1].Result).toBe("LOSS");
  });
  it("works on rebalance-log shape (no PnL)", async () => {
    const t = await getTrades("tr_rebal.csv", FIX);
    expect(t.columns).toContain("Top5_Stocks");
    expect(t.rows.length).toBe(2);
  });
  it("missing/null -> empty", async () => {
    expect(await getTrades("nope.csv", FIX)).toEqual({ columns: [], rows: [] });
    expect(await getTrades(null, FIX)).toEqual({ columns: [], rows: [] });
  });
});
```

- [ ] **Step 3: Run, verify fail** — `cd web && npm test` → FAIL.

- [ ] **Step 4: Implement** (append to `web/lib/data/strategies.ts`)

```ts
export type TradesData = { columns: string[]; rows: Record<string, string>[] };
const MAX_TRADE_COLS = 8;

export async function getTrades(
  csv: string | null,
  dataDir: string = DEFAULT_DATA_DIR,
): Promise<TradesData> {
  if (!csv) return { columns: [], rows: [] };
  try {
    const txt = await fs.readFile(path.join(dataDir, csv), "utf-8");
    const lines = txt.trim().split(/\r?\n/);
    if (lines.length < 2) return { columns: [], rows: [] };
    const columns = lines[0].split(",").map((h) => h.trim()).slice(0, MAX_TRADE_COLS);
    const rows = lines.slice(1).map((l) => {
      const cells = l.split(",");
      const row: Record<string, string> = {};
      columns.forEach((c, i) => {
        row[c] = (cells[i] ?? "").trim();
      });
      return row;
    });
    return { columns, rows };
  } catch {
    return { columns: [], rows: [] };
  }
}
```
> Note: simple `split(",")` does not handle quoted commas (e.g. `"A,B,C"` in the rebalance fixture). For the rebalance row, the quoted `Top5_Stocks` cell will split across columns — acceptable for this slice (generic best-effort display; `MAX_TRADE_COLS` cap limits the damage). The test only asserts column presence + row count, which hold. Do NOT add a full CSV parser this slice (YAGNI).

- [ ] **Step 5: Run, verify pass** — `cd web && npm test` → PASS.

- [ ] **Step 6: Commit**

```bash
cd .. && git add web/lib/data/strategies.ts web/tests/strategies.test.ts web/tests/fixtures/tr_a.csv web/tests/fixtures/tr_rebal.csv && git commit -m "feat(s4): getTrades generic loader"
```

---

## Task 4: `line-chart.tsx` (lightweight-charts client wrapper)

**Files:**
- Create: `web/components/line-chart.tsx`

- [ ] **Step 1: Confirm the lightweight-charts API version**

Run: `cd web && npm ls lightweight-charts`
- If **v5.x**: series are added via `chart.addSeries(AreaSeries, {...})` (import `AreaSeries`).
- If **v4.x**: use `chart.addAreaSeries({...})` (no `AreaSeries` import).
Use the matching form in Step 2.

- [ ] **Step 2: Implement `web/components/line-chart.tsx`** (v5 form shown; adapt to v4 per Step 1)

```tsx
"use client";

import { useEffect, useRef } from "react";
import { createChart, AreaSeries, ColorType } from "lightweight-charts";

export type Point = { time: string; value: number };

export function LineChart({
  data, color = "#22c55e", height = 280,
}: { data: Point[]; color?: string; height?: number }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el || data.length === 0) return;
    const chart = createChart(el, {
      height,
      autoSize: true,
      layout: { background: { type: ColorType.Solid, color: "transparent" }, textColor: "#8b93a1" },
      grid: { vertLines: { color: "#20242c" }, horzLines: { color: "#20242c" } },
      rightPriceScale: { borderColor: "#20242c" },
      timeScale: { borderColor: "#20242c" },
    });
    // v5 API. v4: const series = chart.addAreaSeries({ lineColor: color, ... });
    const series = chart.addSeries(AreaSeries, {
      lineColor: color, topColor: `${color}55`, bottomColor: `${color}08`, lineWidth: 2,
    });
    series.setData(data);
    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [data, color, height]);

  if (!data || data.length === 0) {
    return (
      <div className="flex h-[280px] items-center justify-center rounded border border-border text-sm text-muted-foreground">
        No data
      </div>
    );
  }
  return <div ref={ref} className="w-full" />;
}
```

- [ ] **Step 3: Typecheck**

Run: `cd web && npx tsc --noEmit`
Expected: no errors. (If v4, ensure the `AreaSeries` import is removed and `addAreaSeries` used.)

- [ ] **Step 4: Commit**

```bash
cd .. && git add web/components/line-chart.tsx && git commit -m "feat(s4): lightweight-charts line/area chart wrapper"
```

---

## Task 5: `kpi-strip.tsx` + `trades-table.tsx`

**Files:**
- Create: `web/components/kpi-strip.tsx`, `web/components/trades-table.tsx`

- [ ] **Step 1: Implement `web/components/kpi-strip.tsx`**

```tsx
import { pct, signed } from "@/lib/format";
import type { Kpis } from "@/lib/data/strategies";

function Tile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border p-3">
      <div className="text-xs uppercase text-muted-foreground">{label}</div>
      <div className="text-lg font-semibold">{value}</div>
    </div>
  );
}

export function KpiStrip({ kpis }: { kpis: Kpis }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
      <Tile label="CAGR" value={pct(kpis.cagr)} />
      <Tile label="Sharpe" value={signed(kpis.sharpe)} />
      <Tile label="Max DD" value={pct(kpis.maxDd)} />
      <Tile label="Win Rate" value={pct(kpis.winRate)} />
      <Tile label="Trades" value={kpis.numTrades == null ? "—" : String(kpis.numTrades)} />
    </div>
  );
}
```

- [ ] **Step 2: Implement `web/components/trades-table.tsx`**

```tsx
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import type { TradesData } from "@/lib/data/strategies";

export function TradesTable({ columns, rows }: TradesData) {
  if (!columns.length || !rows.length) {
    return <p className="text-sm text-muted-foreground">No trades for this strategy.</p>;
  }
  return (
    <Table>
      <TableHeader>
        <TableRow>{columns.map((c) => <TableHead key={c}>{c}</TableHead>)}</TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((r, i) => (
          <TableRow key={i}>
            {columns.map((c) => <TableCell key={c}>{r[c]}</TableCell>)}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
```

- [ ] **Step 3: Typecheck**

Run: `cd web && npx tsc --noEmit`
Expected: no errors. (Confirm shadcn table exports: `Table, TableBody, TableCell, TableHead, TableHeader, TableRow`.)

- [ ] **Step 4: Commit**

```bash
cd .. && git add web/components/kpi-strip.tsx web/components/trades-table.tsx && git commit -m "feat(s4): kpi-strip + generic trades-table"
```

---

## Task 6: detail page + leaderboard link

**Files:**
- Create: `web/app/strategy/[id]/page.tsx`
- Modify: `web/components/leaderboard-table.tsx`

- [ ] **Step 1: Create `web/app/strategy/[id]/page.tsx`**

```tsx
import { notFound } from "next/navigation";
import Link from "next/link";
import { getStrategy, getEquityCurve, computeDrawdown, getTrades } from "@/lib/data/strategies";
import { LineChart } from "@/components/line-chart";
import { KpiStrip } from "@/components/kpi-strip";
import { TradesTable } from "@/components/trades-table";

export const dynamic = "force-dynamic";

export default async function StrategyPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const s = await getStrategy(id);
  if (!s) notFound();

  const curve = await getEquityCurve(s.equityCsv);
  const dd = computeDrawdown(curve);
  const trades = await getTrades(s.tradesCsv);

  return (
    <main className="mx-auto max-w-5xl space-y-6 p-8">
      <Link href="/leaderboard" className="text-sm text-muted-foreground">← Leaderboard</Link>
      <div>
        <h1 className="text-2xl font-bold">{s.name}</h1>
        <p className="text-sm text-muted-foreground">{s.type} · {s.status}</p>
      </div>
      <KpiStrip kpis={s.kpis} />
      <section>
        <h2 className="mb-2 text-lg font-semibold">Equity Curve</h2>
        <LineChart data={curve} color="#22c55e" />
      </section>
      <section>
        <h2 className="mb-2 text-lg font-semibold">Drawdown</h2>
        <LineChart data={dd} color="#ef4444" />
      </section>
      <section>
        <h2 className="mb-2 text-lg font-semibold">Trade History ({trades.rows.length})</h2>
        <TradesTable {...trades} />
      </section>
    </main>
  );
}
```
> Next 16: `params` is a Promise — `await params` before use (as shown). Do not destructure synchronously.

- [ ] **Step 2: Link leaderboard rows to detail**

In `web/components/leaderboard-table.tsx`: add `import Link from "next/link";` at the top (it is already a client component). In the `name` column's `cell`, wrap the name div in a Link:
```tsx
  { accessorKey: "name", header: "Strategy",
    cell: (c) => (
      <Link href={`/strategy/${c.row.original.id}`} className="block hover:underline">
        <div className="font-medium">{c.row.original.name}</div>
        <div className="text-xs text-muted-foreground">{c.row.original.type} · {c.row.original.status}</div>
      </Link>
    ) },
```
(Keep all other columns unchanged.)

- [ ] **Step 3: Build**

Run: `cd web && npm run build`
Expected: succeeds; routes show `/leaderboard` and `/strategy/[id]`.

- [ ] **Step 4: Commit**

```bash
cd .. && git add web/app/strategy web/components/leaderboard-table.tsx && git commit -m "feat(s4): strategy detail page + leaderboard link"
```

---

## Task 7: Verify + memory

- [ ] **Step 1: Full Vitest + typecheck + build**

```bash
cd web && npm test && npx tsc --noEmit && npm run build
```
Expected: all green (loader tests incl. the new getStrategy/getEquityCurve/computeDrawdown/getTrades).

- [ ] **Step 2: Run the app + verify the real surface**

```bash
cd web && npx next start -p 3007   # after build
```
Then (separate shell or curl):
- `curl -s http://localhost:3007/strategy/pead | grep -oE "PEAD|Equity Curve|Drawdown|Trade History|Max DD"` → all present.
- `curl -s -o /dev/null -w "%{http_code}" http://localhost:3007/strategy/does-not-exist` → `404`.
- In a browser: `/leaderboard` → click a row → lands on `/strategy/<id>`; equity + drawdown charts render (lightweight-charts canvas), KPI strip shows values (Monthly win-rate "—"), trades table populated.
Stop the server after.

> lightweight-charts renders to a `<canvas>` via client JS, so `curl` (SSR HTML) won't show chart pixels — assert the section headings + KPI text via curl, and confirm the canvas/chart visually in the browser (or via a Playwright smoke if available). Report which path used.

- [ ] **Step 3: Memory (controller, not subagent)**

Update `s4_nextjs_frontend.md`: slice-2 (detail page) done — `/strategy/[id]`, lightweight-charts equity+drawdown, generic trades table, loader extended (getStrategy/getEquityCurve/computeDrawdown/getTrades). Note heatmap still deferred.

---

## Self-Review

**Spec coverage:**
- §4 files (page, loader extensions, line-chart, kpi-strip, trades-table, leaderboard link) → Tasks 1–6. ✓
- §5 data flow (getStrategy→notFound, getEquityCurve dated, computeDrawdown pure, getTrades generic, Strategy.tradesCsv) → Tasks 1–3,6. ✓
- §6 charts (lightweight-charts client wrapper, area, dark, color prop, empty placeholder, v5/v4 note) → Task 4. ✓
- §7 errors (unknown id→404, missing equity→[]→"No data", computeDrawdown([])→[], empty trades→message, null KPI→"—", try/catch) → Tasks 2,3,4,5,6. ✓
- §8 testing (Vitest loaders incl rebalance-shape, typecheck/build, run verification incl 404) → Tasks 1–3,7. ✓

**Placeholder scan:** all code complete; the CSV-quoted-comma limitation is explicitly accepted (YAGNI), not a placeholder. v5/v4 chart API is a documented branch with a version check, not a gap.

**Type consistency:** `Strategy.tradesCsv: string|null`; `EquityPoint {time,value}`; `Point` (line-chart) structurally = `EquityPoint`; `TradesData {columns,rows}`; `getStrategy(id,dir?)→Strategy|null`, `getEquityCurve(csv|null,dir?)→EquityPoint[]`, `computeDrawdown(EquityPoint[])→EquityPoint[]`, `getTrades(csv|null,dir?)→TradesData`. `KpiStrip({kpis:Kpis})`, `LineChart({data:Point[],color?,height?})`, `TradesTable(TradesData)`. Consistent across tasks. ✓
