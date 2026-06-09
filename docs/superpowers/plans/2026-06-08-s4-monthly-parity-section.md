# S4 Monthly Rotation Parity Section — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Monthly-Rotation-specific content block (Nifty-overlay equity + Alpha stat, full RS-ranked stock table) below the generic `/strategy/[id]` core, via a pluggable per-strategy dispatcher.

**Architecture:** A server-component dispatcher (`StrategySection`) switches on `strategy.id` and renders a per-strategy block or `null`. The Monthly block loads its data through the existing loader seam (`web/lib/data/strategies.ts`) and reuses the slice-3 `MultiLineChart`. Generic core untouched → all other strategies render nothing and stay identical.

**Tech Stack:** Next.js 16 (RSC, `force-dynamic`), TypeScript, Tailwind v4, lightweight-charts v5, Vitest. Work happens in `web/`.

---

## Context for the engineer

- All data access lives in **one** module: `web/lib/data/strategies.ts`. Add new loaders there, nowhere else. Functions are null-safe: missing file/column/rows → empty result, never throw, never invent `0`.
- `DEFAULT_DATA_DIR = process.env.DATA_DIR ?? ".."`. In `web/.env.local`, `DATA_DIR=".."` → repo root. So `getX("foo.csv")` reads `<repo-root>/foo.csv`.
- Existing helpers you will reuse (already implemented, do not rewrite):
  - `rebaseToReturn(curve: EquityPoint[]): EquityPoint[]` — maps a curve to `value/v0 - 1`; `v0 <= 0` or empty → `[]`.
  - `getEquityCurve(csv, dir?)` — dated `{time,value}[]`, resolves `Portfolio_Value|Equity|equity`.
  - `EquityPoint = { time: string; value: number }`.
  - `MultiLineChart` (`web/components/multi-line-chart.tsx`), props `{ series: { name; color; points: EquityPoint[] }[]; height? }`.
  - `pct`, `signed`, `naDash` from `web/lib/format.ts`.
- Tests use **real fixture files** in `web/tests/fixtures/` and pass the fixtures dir explicitly:
  `const FIX = path.join(import.meta.dirname, "fixtures");` then `await getX("file.csv", FIX)`.
- Data shapes (from repo root):
  - `backtest_results.csv` header: `Date,Portfolio_Value,Benchmark_Value`.
  - `live_rankings.csv` header: `Rank,Ticker,Company,Current_Price,Prev_Month_End_Price,Return_%,Benchmark_Return_%,RS_Score,Signal`. Signal values may carry a `🟢 `/`🔴 ` emoji prefix; tickers end `.NS`.
- `strategies_index.json` for `monthly_rotation` already has `equity_csv: backtest_results.csv` and `live_signals_csv: live_rankings.csv`.

## File Structure

- **Modify** `web/lib/data/strategies.ts` — add `getEquityWithBenchmark`, `annualizedReturn`, `RankingRow` type, `getRankings`.
- **Modify** `web/tests/strategies.test.ts` — add tests for the three new functions.
- **Create** `web/tests/fixtures/bench_a.csv` — equity+benchmark fixture.
- **Create** `web/tests/fixtures/ranks_a.csv` — rankings fixture (emoji + `.NS`).
- **Create** `web/components/rankings-table.tsx` — client table, top-5 highlighted.
- **Create** `web/components/strategy-sections/monthly-rotation.tsx` — server block (chart + alpha + table).
- **Create** `web/components/strategy-sections/index.tsx` — `StrategySection` dispatcher.
- **Modify** `web/app/strategy/[id]/page.tsx` — render `<StrategySection strategy={s} />` after trades.

Each task is TDD where there is logic to test (the three loaders). Components are verified by build + runtime curl, matching how prior slices were verified.

---

### Task 1: `getEquityWithBenchmark` loader

**Files:**
- Create: `web/tests/fixtures/bench_a.csv`
- Modify: `web/tests/strategies.test.ts`
- Modify: `web/lib/data/strategies.ts`

- [ ] **Step 1: Create the fixture**

Create `web/tests/fixtures/bench_a.csv`:

```
Date,Portfolio_Value,Benchmark_Value
2024-01-01,50000,210
2025-01-01,55000,231
2026-01-01,60000,235
```

(Strategy grows 50000→60000 over 2 years; benchmark 210→235. `eq_a.csv` already has a `Benchmark_Value` column too, but `bench_a.csv` gives clean multi-year numbers for the CAGR assertion.)

- [ ] **Step 2: Write the failing tests**

Add to `web/tests/strategies.test.ts`. First extend the import on line 2 to include the new symbols:

```typescript
import { getStrategies, mapStrategy, getEquitySeries, getStrategy, getEquityCurve, computeDrawdown, getTrades, rebaseToReturn, getLiveSignals, getEquityWithBenchmark, annualizedReturn, getRankings } from "@/lib/data/strategies";
```

Then append:

```typescript
describe("getEquityWithBenchmark", () => {
  it("returns rebased strategy + benchmark series and benchmark CAGR", async () => {
    const r = await getEquityWithBenchmark("bench_a.csv", FIX);
    expect(r.strategy.length).toBe(3);
    expect(r.benchmark.length).toBe(3);
    // rebased: first point is 0
    expect(r.strategy[0].value).toBeCloseTo(0, 6);
    expect(r.benchmark[0].value).toBeCloseTo(0, 6);
    // strategy last = 60000/50000 - 1 = 0.2
    expect(r.strategy[2].value).toBeCloseTo(0.2, 6);
    // benchmark CAGR over 2 years: (235/210)^(1/2) - 1
    const expected = Math.pow(235 / 210, 1 / 2) - 1;
    expect(r.benchmarkCagr).toBeCloseTo(expected, 4);
  });
  it("missing Benchmark_Value column -> empty benchmark, null cagr", async () => {
    const r = await getEquityWithBenchmark("eq_b.csv", FIX); // eq_b has Equity col, no Benchmark_Value
    expect(r.strategy.length).toBeGreaterThan(0);
    expect(r.benchmark).toEqual([]);
    expect(r.benchmarkCagr).toBeNull();
  });
  it("missing file -> empty everything", async () => {
    const r = await getEquityWithBenchmark("nope.csv", FIX);
    expect(r).toEqual({ strategy: [], benchmark: [], benchmarkCagr: null });
  });
  it("null path -> empty everything", async () => {
    const r = await getEquityWithBenchmark(null, FIX);
    expect(r).toEqual({ strategy: [], benchmark: [], benchmarkCagr: null });
  });
});
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd web && npx vitest run tests/strategies.test.ts -t "getEquityWithBenchmark"`
Expected: FAIL — `getEquityWithBenchmark is not a function` (and `annualizedReturn`/`getRankings` import undefined is fine for now; the named imports resolve to `undefined` until defined).

- [ ] **Step 4: Implement `annualizedReturn` + `getEquityWithBenchmark`**

Key design points:
- The strategy series is returned **rebased** (`rebaseToReturn`) so the overlay chart shows return-% from a common 0% start (raw Nifty ~210 vs strategy ~50000 would be unreadable).
- `benchmarkCagr` is computed from the **raw** (un-rebased) benchmark values via `annualizedReturn` — rebasing first would break the CAGR math. Strategy CAGR is NOT computed here; the component reads it from `s.kpis.cagr`.

In `web/lib/data/strategies.ts`, after `rebaseToReturn` (line ~139) add (use verbatim, all four declarations):

```typescript
export function annualizedReturn(curve: EquityPoint[]): number | null {
  if (curve.length < 2) return null;
  const first = curve[0];
  const last = curve[curve.length - 1];
  if (first.value <= 0) return null;
  const days =
    (new Date(last.time).getTime() - new Date(first.time).getTime()) / 86_400_000;
  const years = Math.max(days / 365.25, 0.01);
  return Math.pow(last.value / first.value, 1 / years) - 1;
}

const BENCHMARK_COL = "Benchmark_Value";

export type EquityWithBenchmark = {
  strategy: EquityPoint[];
  benchmark: EquityPoint[];
  benchmarkCagr: number | null;
};

export async function getEquityWithBenchmark(
  csv: string | null,
  dataDir: string = DEFAULT_DATA_DIR,
): Promise<EquityWithBenchmark> {
  const empty: EquityWithBenchmark = { strategy: [], benchmark: [], benchmarkCagr: null };
  if (!csv) return empty;
  try {
    const rawStrategy = await getEquityCurve(csv, dataDir);
    const strategy = rebaseToReturn(rawStrategy);
    const txt = await fs.readFile(path.join(dataDir, csv), "utf-8");
    const lines = txt.trim().split(/\r?\n/);
    if (lines.length < 2) return { strategy, benchmark: [], benchmarkCagr: null };
    const header = lines[0].split(",").map((h) => h.trim());
    const dateIdx = header.findIndex((h) => DATE_COLS.includes(h));
    const di = dateIdx >= 0 ? dateIdx : 0;
    const bi = header.indexOf(BENCHMARK_COL);
    if (bi < 0) return { strategy, benchmark: [], benchmarkCagr: null };
    const rawBench: EquityPoint[] = lines
      .slice(1)
      .map((l) => {
        const cells = l.split(",");
        return { time: String(cells[di] ?? "").slice(0, 10), value: Number(cells[bi]) };
      })
      .filter((p) => p.time !== "" && !Number.isNaN(p.value));
    rawBench.sort((a, b) => a.time.localeCompare(b.time));
    return {
      strategy,
      benchmark: rebaseToReturn(rawBench),
      benchmarkCagr: annualizedReturn(rawBench),
    };
  } catch {
    return empty;
  }
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd web && npx vitest run tests/strategies.test.ts -t "getEquityWithBenchmark"`
Expected: PASS (4 tests). Also run the `annualizedReturn` tests added in Task 2 are not yet present — that's fine.

- [ ] **Step 6: Commit**

```bash
git add web/lib/data/strategies.ts web/tests/strategies.test.ts web/tests/fixtures/bench_a.csv
git commit -m "feat(s4): getEquityWithBenchmark + annualizedReturn loaders"
```

---

### Task 2: `annualizedReturn` edge-case tests

**Files:**
- Modify: `web/tests/strategies.test.ts`

`annualizedReturn` was implemented in Task 1. This task locks its edge cases.

- [ ] **Step 1: Write the tests**

Append to `web/tests/strategies.test.ts`:

```typescript
describe("annualizedReturn", () => {
  it("computes CAGR from first/last point", () => {
    const r = annualizedReturn([
      { time: "2024-01-01", value: 100 },
      { time: "2026-01-01", value: 121 },
    ]);
    // ~2 years, (121/100)^(1/2)-1 ≈ 0.10
    expect(r).toBeCloseTo(Math.pow(1.21, 1 / 2) - 1, 4);
  });
  it("< 2 points -> null", () => {
    expect(annualizedReturn([])).toBeNull();
    expect(annualizedReturn([{ time: "2024-01-01", value: 100 }])).toBeNull();
  });
  it("non-positive first value -> null", () => {
    expect(annualizedReturn([
      { time: "2024-01-01", value: 0 },
      { time: "2025-01-01", value: 100 },
    ])).toBeNull();
  });
});
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `cd web && npx vitest run tests/strategies.test.ts -t "annualizedReturn"`
Expected: PASS (3 tests) — implementation already exists from Task 1.

- [ ] **Step 3: Commit**

```bash
git add web/tests/strategies.test.ts
git commit -m "test(s4): annualizedReturn edge cases"
```

---

### Task 3: `getRankings` loader

**Files:**
- Create: `web/tests/fixtures/ranks_a.csv`
- Modify: `web/tests/strategies.test.ts`
- Modify: `web/lib/data/strategies.ts`

- [ ] **Step 1: Create the fixture**

Create `web/tests/fixtures/ranks_a.csv` (mirrors `live_rankings.csv`, with `.NS` + emoji to exercise stripping, and one row missing the ticker to exercise skip):

```
Rank,Ticker,Company,Current_Price,Prev_Month_End_Price,Return_%,Benchmark_Return_%,RS_Score,Signal
1,ZEEL.NS,Zee Entertainment,104.42,93.11,12.14,-0.81,12.96,🟢 Strong BUY
2,COALINDIA.NS,Coal India,481.65,457.89,5.18,-0.81,6.00,🟢 Strong BUY
3,,Mystery Co,10.0,9.0,1.0,-0.81,0.5,🔴 SELL
```

- [ ] **Step 2: Write the failing tests**

Append to `web/tests/strategies.test.ts`:

```typescript
describe("getRankings", () => {
  it("parses rows, strips .NS and emoji, keeps nulls not zero", async () => {
    const r = await getRankings("ranks_a.csv", FIX);
    expect(r.length).toBe(2); // third row skipped (no ticker)
    expect(r[0]).toEqual({
      rank: 1,
      ticker: "ZEEL",
      company: "Zee Entertainment",
      price: 104.42,
      returnPct: 12.14,
      rsScore: 12.96,
      signal: "Strong BUY",
    });
    expect(r[1].ticker).toBe("COALINDIA");
    expect(r[1].signal).toBe("Strong BUY");
  });
  it("company falls back to ticker when column absent", async () => {
    const r = await getRankings("ranks_noco.csv", FIX);
    expect(r[0].company).toBe(r[0].ticker);
  });
  it("missing numeric cells -> null (not 0)", async () => {
    const r = await getRankings("ranks_partial.csv", FIX);
    expect(r[0].rsScore).toBeNull();
    expect(r[0].price).toBeNull();
  });
  it("missing file -> []", async () => {
    expect(await getRankings("nope.csv", FIX)).toEqual([]);
  });
  it("null path -> []", async () => {
    expect(await getRankings(null, FIX)).toEqual([]);
  });
});
```

Create supporting fixtures:

`web/tests/fixtures/ranks_noco.csv` (no Company column):

```
Rank,Ticker,Current_Price,Return_%,RS_Score,Signal
1,TCS.NS,3900.0,2.1,1.5,🟢 BUY
```

`web/tests/fixtures/ranks_partial.csv` (RS_Score + Current_Price cells empty):

```
Rank,Ticker,Company,Current_Price,Return_%,RS_Score,Signal
1,INFY.NS,Infosys,,1.0,,🟢 BUY
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd web && npx vitest run tests/strategies.test.ts -t "getRankings"`
Expected: FAIL — `getRankings is not a function`.

- [ ] **Step 4: Implement `getRankings`**

In `web/lib/data/strategies.ts`, after `getLiveSignals` (line ~201) add:

```typescript
export type RankingRow = {
  rank: number | null;
  ticker: string;
  company: string;
  price: number | null;
  returnPct: number | null;
  rsScore: number | null;
  signal: string;
};

const stripSignal = (s: string): string =>
  s.replace(/^[🟢🔴]\s*/u, "").trim();

export async function getRankings(
  csv: string | null,
  dataDir: string = DEFAULT_DATA_DIR,
): Promise<RankingRow[]> {
  if (!csv) return [];
  try {
    const txt = await fs.readFile(path.join(dataDir, csv), "utf-8");
    const lines = txt.trim().split(/\r?\n/);
    if (lines.length < 2) return [];
    const header = lines[0].split(",").map((h) => h.trim().toLowerCase());
    const idx = (name: string) => header.indexOf(name);
    const ti = idx("ticker");
    const si = idx("signal");
    if (ti < 0) return [];
    const ri = idx("rank");
    const ci = idx("company");
    const pi = idx("current_price");
    const reti = idx("return_%");
    const rsi = idx("rs_score");
    const cell = (cells: string[], i: number): string =>
      i >= 0 ? (cells[i] ?? "").trim() : "";
    const numCell = (cells: string[], i: number): number | null => {
      const v = cell(cells, i);
      if (v === "") return null;
      const n = Number(v);
      return Number.isNaN(n) ? null : n;
    };
    return lines
      .slice(1)
      .map((l) => {
        const cells = l.split(",");
        const ticker = cell(cells, ti).replace(/\.NS$/, "");
        const company = ci >= 0 && cell(cells, ci) !== "" ? cell(cells, ci) : ticker;
        return {
          rank: numCell(cells, ri),
          ticker,
          company,
          price: numCell(cells, pi),
          returnPct: numCell(cells, reti),
          rsScore: numCell(cells, rsi),
          signal: si >= 0 ? stripSignal(cell(cells, si)) : "",
        };
      })
      .filter((r) => r.ticker !== "");
  } catch {
    return [];
  }
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd web && npx vitest run tests/strategies.test.ts -t "getRankings"`
Expected: PASS (5 tests).

- [ ] **Step 6: Run the full suite**

Run: `cd web && npx vitest run`
Expected: all green (39 prior + new). If green, continue.

- [ ] **Step 7: Commit**

```bash
git add web/lib/data/strategies.ts web/tests/strategies.test.ts web/tests/fixtures/ranks_a.csv web/tests/fixtures/ranks_noco.csv web/tests/fixtures/ranks_partial.csv
git commit -m "feat(s4): getRankings loader + RankingRow"
```

---

### Task 4: `RankingsTable` component

**Files:**
- Create: `web/components/rankings-table.tsx`

Static table (no sorting this slice). Top-5 rows (`rank != null && rank <= 5`) get an accent left border. Null numeric cells render "—".

- [ ] **Step 1: Create the component**

Create `web/components/rankings-table.tsx`:

```tsx
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { RankingRow } from "@/lib/data/strategies";

const fmtPrice = (v: number | null): string =>
  v == null ? "—" : `₹${v.toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
const fmtPctNum = (v: number | null): string =>
  v == null ? "—" : `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;

export function RankingsTable({ rows }: { rows: RankingRow[] }) {
  if (rows.length === 0) {
    return <p className="text-sm text-muted-foreground">No rankings available.</p>;
  }
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-10">#</TableHead>
          <TableHead>Ticker</TableHead>
          <TableHead>Company</TableHead>
          <TableHead className="text-right">Price</TableHead>
          <TableHead className="text-right">Return</TableHead>
          <TableHead className="text-right">RS Score</TableHead>
          <TableHead>Signal</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((r) => {
          const held = r.rank != null && r.rank <= 5;
          return (
            <TableRow
              key={`${r.rank}-${r.ticker}`}
              className={held ? "border-l-2 border-l-green-500 bg-green-500/5" : ""}
            >
              <TableCell className="font-bold text-green-500">{r.rank ?? "—"}</TableCell>
              <TableCell className="font-medium">{r.ticker}</TableCell>
              <TableCell className="text-xs text-muted-foreground">{r.company}</TableCell>
              <TableCell className="text-right">{fmtPrice(r.price)}</TableCell>
              <TableCell className="text-right">{fmtPctNum(r.returnPct)}</TableCell>
              <TableCell className="text-right">{fmtPctNum(r.rsScore)}</TableCell>
              <TableCell className="text-xs">{r.signal}</TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}
```

- [ ] **Step 2: Verify it type-checks**

Run: `cd web && npx tsc --noEmit`
Expected: no errors. (Confirms `@/components/ui/table` exports the named members — they are used identically in `leaderboard-table.tsx`.)

- [ ] **Step 3: Commit**

```bash
git add web/components/rankings-table.tsx
git commit -m "feat(s4): RankingsTable component"
```

---

### Task 5: `MonthlyRotationSection` block

**Files:**
- Create: `web/components/strategy-sections/monthly-rotation.tsx`

Server component. Loads benchmark-overlay + rankings, renders: overlay chart (strategy + Nifty), Alpha stat, rankings table. Empty datasets → that sub-block omitted.

- [ ] **Step 1: Create the component**

Create `web/components/strategy-sections/monthly-rotation.tsx`:

```tsx
import { getEquityWithBenchmark, getRankings } from "@/lib/data/strategies";
import type { Strategy } from "@/lib/data/strategies";
import { MultiLineChart } from "@/components/multi-line-chart";
import { RankingsTable } from "@/components/rankings-table";
import { pct } from "@/lib/format";

export async function MonthlyRotationSection({ strategy }: { strategy: Strategy }) {
  const eq = await getEquityWithBenchmark(strategy.equityCsv);
  const rankings = await getRankings(strategy.liveSignalsCsv);

  const series = [
    { name: "Monthly Rotation", color: "#22c55e", points: eq.strategy },
    { name: "Nifty", color: "#f59e0b", points: eq.benchmark },
  ].filter((s) => s.points.length > 0);

  const alpha =
    strategy.kpis.cagr != null && eq.benchmarkCagr != null
      ? strategy.kpis.cagr - eq.benchmarkCagr
      : null;

  const hasOverlay = series.length > 0;
  const hasRankings = rankings.length > 0;
  if (!hasOverlay && !hasRankings) return null;

  return (
    <>
      {hasOverlay && (
        <section>
          <div className="mb-2 flex items-baseline justify-between">
            <h2 className="text-lg font-semibold">Growth vs Nifty</h2>
            <span className="text-sm text-muted-foreground">
              Extra vs Nifty (Alpha):{" "}
              <span className={alpha != null && alpha >= 0 ? "text-green-500" : "text-red-500"}>
                {pct(alpha)}
              </span>
            </span>
          </div>
          <MultiLineChart series={series} />
        </section>
      )}
      {hasRankings && (
        <section>
          <h2 className="mb-2 text-lg font-semibold">
            All Stocks — Ranked by Strength (Top 5 held)
          </h2>
          <RankingsTable rows={rankings} />
        </section>
      )}
    </>
  );
}
```

- [ ] **Step 2: Verify it type-checks**

Run: `cd web && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add web/components/strategy-sections/monthly-rotation.tsx
git commit -m "feat(s4): MonthlyRotationSection block"
```

---

### Task 6: `StrategySection` dispatcher + page wiring

**Files:**
- Create: `web/components/strategy-sections/index.tsx`
- Modify: `web/app/strategy/[id]/page.tsx`

- [ ] **Step 1: Create the dispatcher**

Create `web/components/strategy-sections/index.tsx`:

```tsx
import type { Strategy } from "@/lib/data/strategies";
import { MonthlyRotationSection } from "@/components/strategy-sections/monthly-rotation";

export function StrategySection({ strategy }: { strategy: Strategy }) {
  switch (strategy.id) {
    case "monthly_rotation":
      return <MonthlyRotationSection strategy={strategy} />;
    default:
      return null;
  }
}
```

Note: `MonthlyRotationSection` is async; returning it from a sync component is valid in RSC (the returned element is awaited by React on the server).

- [ ] **Step 2: Wire it into the page**

In `web/app/strategy/[id]/page.tsx`, add the import after the existing component imports:

```tsx
import { StrategySection } from "@/components/strategy-sections";
```

Then add the dispatcher render immediately after the closing `</section>` of the Trade History block and before the closing `</main>`:

```tsx
      <StrategySection strategy={s} />
    </main>
```

- [ ] **Step 3: Type-check + build**

Run: `cd web && npx tsc --noEmit && npx next build`
Expected: both succeed, no type errors.

- [ ] **Step 4: Runtime-verify the Monthly page**

Run (from `web/`): `npx next start -p 3014 &` then:
`curl -s http://localhost:3014/strategy/monthly_rotation | grep -o "Growth vs Nifty\|Ranked by Strength\|Alpha"`
Expected: matches `Growth vs Nifty`, `Ranked by Strength`, and `Alpha` (section rendered). Then stop the server.

- [ ] **Step 5: Runtime-verify a non-Monthly page is unchanged**

`curl -s http://localhost:3014/strategy/ipo_edge | grep -c "Ranked by Strength"`
Expected: `0` (dispatcher returns null for non-monthly). Confirm the page still returns HTTP 200 and shows the generic core (Equity Curve / Drawdown / Trade History present).

- [ ] **Step 6: Full suite + commit**

Run: `cd web && npx vitest run`
Expected: all green.

```bash
git add web/components/strategy-sections/index.tsx web/app/strategy/[id]/page.tsx
git commit -m "feat(s4): StrategySection dispatcher + monthly page wiring"
```

---

## Self-Review notes (resolved)

- **Spec coverage:** Block A (overlay + alpha) → Tasks 1,5; Block B (rankings table) → Tasks 3,4,5; dispatcher → Task 6; loader null-safety → Tasks 1,3; tests → Tasks 1,2,3; runtime verify → Task 6. Exit-playbook/explainer and specialized rebalance-log were dropped in the spec (YAGNI) — intentionally no tasks.
- **Type consistency:** `EquityWithBenchmark { strategy; benchmark; benchmarkCagr }`, `RankingRow { rank; ticker; company; price; returnPct; rsScore; signal }`, and `MultiLineChart` `Series { name; color; points }` are used identically across loader, tests, and components.
- **Rankings source:** read from `strategy.liveSignalsCsv` (`live_rankings.csv`), NOT `tradesCsv` — consistent in Task 5.
- **No placeholders:** all steps carry full code/commands.
```
