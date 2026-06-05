# S4 slice-3 — Home Overview Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the Home overview page at `/` — aggregate KPI strip + normalized combined equity chart + Top Performers + Recent Backtests + nav — reading local data via the extended loader.

**Architecture:** Pure `lib/summary.ts` for aggregates; loader gains `Strategy.lastRun` + `rebaseToReturn`. Home is a server component; `multi-line-chart` is the only new client component (lightweight-charts v5 multi-series). Pure modules TDD'd with Vitest; UI verified by build + run.

**Tech Stack:** Next.js 16 (App Router), TypeScript, Tailwind v4, shadcn/ui, lightweight-charts v5, Vitest. Builds on S4 slices 1–2.

Spec: `docs/superpowers/specs/2026-06-05-s4-home-overview-design.md`.

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `web/lib/data/strategies.ts` | + `Strategy.lastRun`; `rebaseToReturn(curve)` | Modify |
| `web/lib/summary.ts` | `Summary` type + `summarizeStrategies` | Create |
| `web/tests/strategies.test.ts` | + lastRun + rebaseToReturn tests | Modify |
| `web/tests/summary.test.ts` | summarizeStrategies tests | Create |
| `web/components/multi-line-chart.tsx` | client LWC v5 multi-series overlay | Create |
| `web/components/nav.tsx` | header nav (Home \| Leaderboard) | Create |
| `web/components/home-kpi-strip.tsx` | 4 aggregate tiles | Create |
| `web/components/top-performers.tsx` | top-3 cards (link to detail) | Create |
| `web/components/recent-backtests.tsx` | recent-5 list (link to detail) | Create |
| `web/app/page.tsx` | Home overview RSC (replaces redirect) | Modify |
| `web/app/layout.tsx` | render `<Nav/>` above children | Modify |

**Conventions:** run npm/npx from `web/`; commit from repo root. Branch created by controller. Do not touch Python/Streamlit files. lightweight-charts is **v5** → `addSeries(LineSeries, …)`.

---

## Task 1: loader — `lastRun` + `rebaseToReturn` (TDD)

**Files:** Modify `web/lib/data/strategies.ts`, `web/tests/strategies.test.ts`

- [ ] **Step 1: Append failing tests** (`web/tests/strategies.test.ts`)

```ts
import { rebaseToReturn } from "@/lib/data/strategies";

describe("rebaseToReturn", () => {
  it("normalizes to 0% at start", () => {
    const r = rebaseToReturn([
      { time: "1", value: 100 }, { time: "2", value: 110 }, { time: "3", value: 90 },
    ]);
    expect(r).toEqual([
      { time: "1", value: 0 },
      { time: "2", value: 0.1 },
      { time: "3", value: -0.1 },
    ]);
  });
  it("[] -> []", () => expect(rebaseToReturn([])).toEqual([]));
  it("v0<=0 -> []", () => {
    expect(rebaseToReturn([{ time: "1", value: 0 }, { time: "2", value: 5 }])).toEqual([]);
  });
});

describe("lastRun mapping", () => {
  it("maps raw.last_run", async () => {
    // fixture strategy "a" needs a last_run value (added in Step 3)
    const s = await getStrategy("a", FIX);
    expect(s?.lastRun).toBe("2026-06-01T12:00:00");
  });
});
```

- [ ] **Step 2: Add `last_run` to fixture strategy "a"**

In `web/tests/fixtures/strategies_index.json`, add `"last_run": "2026-06-01T12:00:00"` to strategy `"a"`.

- [ ] **Step 3: Run, verify fail** — `cd web && npm test` → FAIL (rebaseToReturn undefined / lastRun undefined).

- [ ] **Step 4: Implement** — in `web/lib/data/strategies.ts`:

Add `lastRun: string | null;` to the `Strategy` type. In `mapStrategy`, after `tradesCsv: raw.trades_csv ?? null,` add:
```ts
    lastRun: raw.last_run ?? null,
```
Append the function (near `getEquityCurve`):
```ts
export function rebaseToReturn(curve: EquityPoint[]): EquityPoint[] {
  if (curve.length === 0) return [];
  const v0 = curve[0].value;
  if (v0 <= 0) return [];
  return curve.map((p) => ({ time: p.time, value: p.value / v0 - 1 }));
}
```

- [ ] **Step 5: Run, verify pass** — `cd web && npm test` → PASS.

- [ ] **Step 6: Commit**

```bash
cd .. && git add web/lib/data/strategies.ts web/tests/strategies.test.ts web/tests/fixtures/strategies_index.json && git commit -m "feat(s4): Strategy.lastRun + rebaseToReturn"
```

---

## Task 2: `lib/summary.ts` (TDD)

**Files:** Create `web/lib/summary.ts`, `web/tests/summary.test.ts`

- [ ] **Step 1: Write failing tests** (`web/tests/summary.test.ts`)

```ts
import { describe, it, expect } from "vitest";
import { summarizeStrategies } from "@/lib/summary";
import type { Strategy } from "@/lib/data/strategies";

function mk(over: Partial<Strategy> & { id: string }): Strategy {
  return {
    id: over.id, name: over.id, type: "Quant", status: over.status ?? "Live",
    kpis: {
      cagr: 0.2, totalReturn: 0, volatility: 0, sharpe: 1, maxDd: -0.1,
      calmar: null, winRate: 0.5, numTrades: 10, alpha: null, finalEquity: 0,
      ...(over.kpis ?? {}),
    },
    rank: null, rankScore: null, equityCsv: null, tradesCsv: null, lastRun: null,
    ...over,
  } as Strategy;
}

describe("summarizeStrategies", () => {
  it("counts, averages, ignores nulls", () => {
    const s = summarizeStrategies([
      mk({ id: "a", status: "Live", kpis: { cagr: 0.20, winRate: 0.6, numTrades: 10 } as Strategy["kpis"] }),
      mk({ id: "b", status: "Paper", kpis: { cagr: 0.10, winRate: null, numTrades: 5 } as Strategy["kpis"] }),
    ]);
    expect(s.total).toBe(2);
    expect(s.live).toBe(1);
    expect(s.paper).toBe(1);
    expect(s.avgCagr).toBeCloseTo(0.15);
    expect(s.bestCagr).toBeCloseTo(0.20);
    expect(s.avgWinRate).toBeCloseTo(0.6);   // null win-rate excluded, not counted as 0
    expect(s.totalTrades).toBe(15);
  });
  it("empty -> zeros", () => {
    expect(summarizeStrategies([])).toEqual({
      total: 0, live: 0, paper: 0, avgCagr: 0, bestCagr: 0, avgWinRate: 0, totalTrades: 0,
    });
  });
});
```
> Note: the `mk` helper spreads a partial `kpis`; the literal in each case supplies only the fields under test — the helper fills the rest with defaults. Cast as shown to satisfy TS.

- [ ] **Step 2: Run, verify fail** — `cd web && npm test` → FAIL (no module).

- [ ] **Step 3: Implement `web/lib/summary.ts`**

```ts
import type { Strategy } from "@/lib/data/strategies";

export type Summary = {
  total: number; live: number; paper: number;
  avgCagr: number; bestCagr: number; avgWinRate: number; totalTrades: number;
};

const avg = (xs: number[]): number => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : 0);
const present = (xs: (number | null)[]): number[] => xs.filter((v): v is number => v != null);

export function summarizeStrategies(strategies: Strategy[]): Summary {
  const cagrs = present(strategies.map((s) => s.kpis.cagr));
  const wins = present(strategies.map((s) => s.kpis.winRate));
  const trades = present(strategies.map((s) => s.kpis.numTrades));
  return {
    total: strategies.length,
    live: strategies.filter((s) => s.status === "Live").length,
    paper: strategies.filter((s) => s.status === "Paper").length,
    avgCagr: avg(cagrs),
    bestCagr: cagrs.length ? Math.max(...cagrs) : 0,
    avgWinRate: avg(wins),
    totalTrades: trades.reduce((a, b) => a + b, 0),
  };
}
```

- [ ] **Step 4: Run, verify pass** — `cd web && npm test` → PASS.

- [ ] **Step 5: Commit**

```bash
cd .. && git add web/lib/summary.ts web/tests/summary.test.ts && git commit -m "feat(s4): summarizeStrategies aggregates"
```

---

## Task 3: `multi-line-chart.tsx` (LWC v5 multi-series)

**Files:** Create `web/components/multi-line-chart.tsx`

- [ ] **Step 1: Implement** (v5 `addSeries(LineSeries, …)`)

```tsx
"use client";

import { useEffect, useRef } from "react";
import { createChart, LineSeries, ColorType } from "lightweight-charts";
import type { EquityPoint } from "@/lib/data/strategies";

export type Series = { name: string; color: string; points: EquityPoint[] };

export function MultiLineChart({ series, height = 320 }: { series: Series[]; height?: number }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el || series.length === 0) return;
    const chart = createChart(el, {
      height,
      autoSize: true,
      layout: { background: { type: ColorType.Solid, color: "transparent" }, textColor: "#8b93a1" },
      grid: { vertLines: { color: "#20242c" }, horzLines: { color: "#20242c" } },
      rightPriceScale: { borderColor: "#20242c" },
      timeScale: { borderColor: "#20242c" },
    });
    for (const s of series) {
      const line = chart.addSeries(LineSeries, { color: s.color, lineWidth: 2 });
      line.setData(s.points);
    }
    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [series, height]);

  if (!series || series.length === 0) {
    return (
      <div className="flex h-[320px] items-center justify-center rounded border border-border text-sm text-muted-foreground">
        No equity data
      </div>
    );
  }
  return (
    <div>
      <div className="mb-2 flex flex-wrap gap-3 text-xs">
        {series.map((s) => (
          <span key={s.name} className="flex items-center gap-1">
            <span className="inline-block h-2 w-3 rounded" style={{ background: s.color }} />
            {s.name}
          </span>
        ))}
      </div>
      <div ref={ref} className="w-full" />
    </div>
  );
}
```

- [ ] **Step 2: Typecheck + build**

Run: `cd web && npx tsc --noEmit && npm run build`
Expected: no errors (confirm `LineSeries` is a valid v5 export — same pattern as slice-2's `AreaSeries`).

- [ ] **Step 3: Commit**

```bash
cd .. && git add web/components/multi-line-chart.tsx && git commit -m "feat(s4): multi-line-chart (LWC v5 overlay)"
```

---

## Task 4: presentational components (nav, kpi-strip, top, recent)

**Files:** Create `web/components/nav.tsx`, `home-kpi-strip.tsx`, `top-performers.tsx`, `recent-backtests.tsx`

- [ ] **Step 1: `web/components/nav.tsx`**

```tsx
import Link from "next/link";

export function Nav() {
  return (
    <nav className="sticky top-0 z-10 border-b border-border bg-background/80 backdrop-blur">
      <div className="mx-auto flex max-w-5xl gap-4 p-4 text-sm">
        <Link href="/" className="font-semibold hover:underline">Home</Link>
        <Link href="/leaderboard" className="text-muted-foreground hover:underline">Leaderboard</Link>
      </div>
    </nav>
  );
}
```

- [ ] **Step 2: `web/components/home-kpi-strip.tsx`**

```tsx
import { pct } from "@/lib/format";
import type { Summary } from "@/lib/summary";

function Tile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-lg border border-border p-3">
      <div className="text-xs uppercase text-muted-foreground">{label}</div>
      <div className="text-lg font-semibold">{value}</div>
      {sub ? <div className="text-xs text-muted-foreground">{sub}</div> : null}
    </div>
  );
}

export function HomeKpiStrip({ summary }: { summary: Summary }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      <Tile label="Total Strategies" value={String(summary.total)} sub={`${summary.live} live · ${summary.paper} paper`} />
      <Tile label="Avg CAGR" value={pct(summary.avgCagr)} sub={`Best ${pct(summary.bestCagr)}`} />
      <Tile label="Avg Win Rate" value={pct(summary.avgWinRate)} />
      <Tile label="Total Trades" value={summary.totalTrades.toLocaleString()} />
    </div>
  );
}
```

- [ ] **Step 3: `web/components/top-performers.tsx`**

```tsx
import Link from "next/link";
import { pct, signed } from "@/lib/format";
import type { Strategy } from "@/lib/data/strategies";

export function TopPerformers({ items }: { items: Strategy[] }) {
  if (!items.length) return <p className="text-sm text-muted-foreground">No strategies.</p>;
  return (
    <div className="grid gap-3 sm:grid-cols-3">
      {items.map((s) => (
        <Link key={s.id} href={`/strategy/${s.id}`} className="rounded-lg border border-border p-3 hover:bg-muted/30">
          <div className="font-medium">{s.name}</div>
          <div className="text-xs text-muted-foreground">{s.type} · {s.status}</div>
          <div className="mt-2 text-sm">Sharpe {signed(s.kpis.sharpe)} · CAGR {pct(s.kpis.cagr)}</div>
        </Link>
      ))}
    </div>
  );
}
```

- [ ] **Step 4: `web/components/recent-backtests.tsx`**

```tsx
import Link from "next/link";
import { pct } from "@/lib/format";
import type { Strategy } from "@/lib/data/strategies";

export function RecentBacktests({ items }: { items: Strategy[] }) {
  if (!items.length) return <p className="text-sm text-muted-foreground">No strategies.</p>;
  return (
    <ul className="divide-y divide-border rounded-lg border border-border">
      {items.map((s) => (
        <li key={s.id}>
          <Link href={`/strategy/${s.id}`} className="flex items-center justify-between p-3 hover:bg-muted/30">
            <span>{s.name}</span>
            <span className="text-sm text-muted-foreground">
              {s.lastRun ? s.lastRun.slice(0, 10) : "—"} · CAGR {pct(s.kpis.cagr)}
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}
```

- [ ] **Step 5: Typecheck**

Run: `cd web && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
cd .. && git add web/components/nav.tsx web/components/home-kpi-strip.tsx web/components/top-performers.tsx web/components/recent-backtests.tsx && git commit -m "feat(s4): home nav + kpi-strip + top-performers + recent-backtests"
```

---

## Task 5: Home page + nav wiring

**Files:** Modify `web/app/page.tsx`, `web/app/layout.tsx`

- [ ] **Step 1: Replace `web/app/page.tsx`** (was `redirect("/leaderboard")`)

```tsx
import { getStrategies, getEquityCurve, rebaseToReturn } from "@/lib/data/strategies";
import { summarizeStrategies } from "@/lib/summary";
import { HomeKpiStrip } from "@/components/home-kpi-strip";
import { MultiLineChart, type Series } from "@/components/multi-line-chart";
import { TopPerformers } from "@/components/top-performers";
import { RecentBacktests } from "@/components/recent-backtests";

export const dynamic = "force-dynamic";

const PALETTE = ["#22c55e", "#3b82f6", "#f59e0b", "#ef4444", "#a855f7", "#14b8a6"];

export default async function Home() {
  const strategies = await getStrategies();
  const summary = summarizeStrategies(strategies);
  const top = [...strategies]
    .sort((a, b) => (b.kpis.sharpe ?? -Infinity) - (a.kpis.sharpe ?? -Infinity))
    .slice(0, 3);
  const recent = [...strategies]
    .sort((a, b) => (b.lastRun ?? "").localeCompare(a.lastRun ?? ""))
    .slice(0, 5);
  const series: Series[] = (
    await Promise.all(
      strategies.map(async (s, i) => ({
        name: s.name,
        color: PALETTE[i % PALETTE.length],
        points: rebaseToReturn(await getEquityCurve(s.equityCsv)),
      })),
    )
  ).filter((x) => x.points.length > 0);

  return (
    <main className="mx-auto max-w-5xl space-y-8 p-8">
      <h1 className="text-2xl font-bold">NSE Strategy Hub</h1>
      <HomeKpiStrip summary={summary} />
      <section>
        <h2 className="mb-2 text-lg font-semibold">Combined Equity (rebased to start)</h2>
        <MultiLineChart series={series} />
      </section>
      <section>
        <h2 className="mb-2 text-lg font-semibold">Top Performers</h2>
        <TopPerformers items={top} />
      </section>
      <section>
        <h2 className="mb-2 text-lg font-semibold">Recent Backtests</h2>
        <RecentBacktests items={recent} />
      </section>
    </main>
  );
}
```

- [ ] **Step 2: Add `<Nav/>` to `web/app/layout.tsx`**

Import and render `<Nav/>` directly inside `<body>`, before `{children}`:
```tsx
import { Nav } from "@/components/nav";
// ...
      <body className="bg-background text-foreground antialiased">
        <Nav />
        {children}
      </body>
```
(Keep the existing `<html className="dark">` + metadata + globals.css import.)

- [ ] **Step 3: Build**

Run: `cd web && npm run build`
Expected: succeeds; `/` is now the Home page (no longer a redirect), `/leaderboard` + `/strategy/[id]` still present.

- [ ] **Step 4: Commit**

```bash
cd .. && git add web/app/page.tsx web/app/layout.tsx && git commit -m "feat(s4): home overview page + nav wiring"
```

---

## Task 6: Verify + memory

- [ ] **Step 1: Full Vitest + typecheck + build**

```bash
cd web && npm test && npx tsc --noEmit && npm run build
```
Expected: all green (slice-1/2 tests + new rebaseToReturn/lastRun/summary tests).

- [ ] **Step 2: Run the app + verify**

```bash
cd web && npx next start -p 3007   # after build
```
Verify:
- `curl -s http://localhost:3007/ | grep -oE "NSE Strategy Hub|Total Strategies|Combined Equity|Top Performers|Recent Backtests"` → all present.
- `curl -s http://localhost:3007/ | grep -oE "/strategy/(pead|monthly_rotation|ipo_edge|momentum_edge)"` → detail links present (Top + Recent).
- Browser: `/` shows the aggregate strip (real numbers), the combined chart with multiple colored lines + legend, Top-3 + Recent-5; nav switches Home↔Leaderboard; clicking a card → detail page.
- `curl -s -o /dev/null -w "%{http_code}" http://localhost:3007/leaderboard` → 200 (still works).
Stop the server after.

> lightweight-charts renders to canvas (client JS) — curl shows headings/links, confirm chart lines visually in the browser. Report which path used.

- [ ] **Step 3: Memory (controller, not subagent)**

Update `s4_nextjs_frontend.md`: slice-3 (Home overview) done — `/` Home with aggregate strip + normalized combined equity overlay + Top/Recent + nav; `summary.ts`, `rebaseToReturn`, `Strategy.lastRun`, `multi-line-chart`. Live-signals still deferred.

---

## Self-Review

**Spec coverage:**
- §4 files (page, layout nav, summary, loader ext, 5 components) → Tasks 1–5. ✓
- §5 aggregates (summarizeStrategies null-safe) → Task 2. ✓
- §6 data flow (getStrategies→summarize, top/recent sort with null sentinels, rebased series filtered) → Tasks 1,5. ✓
- §7 charts (multi-line LWC v5 LineSeries, legend, empty placeholder) → Task 3. ✓
- §8 errors (empty→zeros/placeholder, null excluded from avg, missing equity filtered, v0<=0→[]) → Tasks 1,2,3,5. ✓
- §9 testing (summary + rebaseToReturn + lastRun Vitest, typecheck/build, run verify) → Tasks 1,2,6. ✓

**Placeholder scan:** all code complete; no TBD/TODO; the `mk` test-helper note is guidance, not a gap.

**Type consistency:** `Strategy.lastRun: string|null`; `Summary` fields match Task 2 + home-kpi-strip; `rebaseToReturn(EquityPoint[])→EquityPoint[]`; `Series {name,color,points:EquityPoint[]}` shared multi-line-chart↔page; `summarizeStrategies(Strategy[])→Summary`; sort comparators null-safe (`?? -Infinity`, `?? ""`). Consistent across tasks. ✓
