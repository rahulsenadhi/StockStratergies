# Monthly-Returns Heatmap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a years×months monthly-returns heatmap (with annual-total column) as a generic core section on `/strategy/[id]` for all 4 strategies.

**Architecture:** Extract a non-downsampled `readEquityCurveRaw` from `getEquityCurve`, add a pure `getMonthlyReturns` loader that groups the raw curve into month-end returns + annual compounds, and render a CSS-only `MonthlyHeatmap` (symmetric fixed green/red scale) wired into the existing strategy detail page. Read-only, local-first — same seam as all other S4 sections.

**Tech Stack:** Next.js 16 (RSC), TypeScript, Tailwind v4, Vitest. No chart library (CSS grid, like `horizontal-bars.tsx`).

**Spec:** `docs/superpowers/specs/2026-06-09-s4-monthly-returns-heatmap-design.md`

**Conventions observed:**
- Loader module: `web/lib/data/strategies.ts`. Tests: `web/tests/strategies.test.ts` (fixtures under `web/tests/fixtures/`, temp CSVs via `fsp.mkdtemp` + `fsp.writeFile`).
- Run tests from `web/`: `npm run test` (vitest run). Single file: `npm run test -- strategies`.
- `EquityPoint = { time: string; value: number }`, `MAX_CURVE_POINTS = 2000`, `DATE_COLS`, `EQUITY_COLS` already defined at top of `strategies.ts`.
- `pct(v)` from `@/lib/format` → null/undefined renders `"—"`, fractions ×100 with sign.
- Returns are **fractions** (e.g. `0.0412` = +4.12%).
- Pure component test convention: `barWidthPct` is exported from `horizontal-bars.tsx` and unit-tested in `strategies.test.ts` — follow the same pattern (export `cellColor`, test it there).

---

### Task 1: Extract `readEquityCurveRaw` (refactor, behavior-preserving)

**Files:**
- Modify: `web/lib/data/strategies.ts:112-162` (`getEquityCurve`)
- Test: `web/tests/strategies.test.ts` (existing `getEquityCurve` describe block stays green; add one raw test)

- [ ] **Step 1: Write a failing test for the new export**

Add to `web/tests/strategies.test.ts` (import `readEquityCurveRaw` in the top import line alongside the others):

```typescript
describe("readEquityCurveRaw", () => {
  it("returns full-resolution sorted/deduped curve (no downsample)", async () => {
    const dir = await fsp.mkdtemp(path.join(os.tmpdir(), "raw-"));
    const rows = ["Date,equity"];
    for (let i = 0; i < 5000; i++) {
      const d = new Date(Date.UTC(2010, 0, 1));
      d.setUTCDate(d.getUTCDate() + i);
      rows.push(`${d.toISOString().slice(0, 10)},${100 + i}`);
    }
    await fsp.writeFile(path.join(dir, "big.csv"), rows.join("\n"));
    const c = await readEquityCurveRaw("big.csv", dir);
    expect(c.length).toBe(5000); // NOT capped
    expect(c[0].value).toBe(100);
    expect(c[c.length - 1].value).toBe(100 + 4999);
  });
  it("missing/null -> []", async () => {
    expect(await readEquityCurveRaw("nope.csv", FIX)).toEqual([]);
    expect(await readEquityCurveRaw(null, FIX)).toEqual([]);
  });
});
```

- [ ] **Step 2: Run the test, verify it fails**

Run: `npm run test -- strategies`
Expected: FAIL — `readEquityCurveRaw is not a function` / import error.

- [ ] **Step 3: Refactor `getEquityCurve` to extract the raw reader**

In `web/lib/data/strategies.ts`, replace the current `getEquityCurve` (lines ~112-162) with:

```typescript
export async function readEquityCurveRaw(
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
    const deduped: EquityPoint[] = [];
    for (const p of pts) {
      if (deduped.length && deduped[deduped.length - 1].time === p.time) {
        deduped[deduped.length - 1] = p; // keep last value for a repeated date
      } else {
        deduped.push(p);
      }
    }
    return deduped;
  } catch {
    return [];
  }
}

export async function getEquityCurve(
  csv: string | null,
  dataDir: string = DEFAULT_DATA_DIR,
): Promise<EquityPoint[]> {
  let pts = await readEquityCurveRaw(csv, dataDir);
  if (pts.length > MAX_CURVE_POINTS) {
    const step = Math.ceil(pts.length / MAX_CURVE_POINTS);
    const sampled = pts.filter((_, i) => i % step === 0);
    const last = pts[pts.length - 1];
    if (sampled[sampled.length - 1] !== last) sampled.push(last);
    pts = sampled;
  }
  return pts;
}
```

- [ ] **Step 4: Run tests, verify all green (parity + new raw test)**

Run: `npm run test -- strategies`
Expected: PASS — existing `getEquityCurve` tests (cap ≤2000, keeps last, dedup) still pass; new `readEquityCurveRaw` tests pass.

- [ ] **Step 5: Commit**

```bash
git add web/lib/data/strategies.ts web/tests/strategies.test.ts
git commit -m "refactor(s4): extract readEquityCurveRaw from getEquityCurve"
```

---

### Task 2: `getMonthlyReturns` loader

**Files:**
- Modify: `web/lib/data/strategies.ts` (add type `MonthlyReturnsRow` + `getMonthlyReturns` after `readEquityCurveRaw`/`getEquityCurve`)
- Test: `web/tests/strategies.test.ts`

- [ ] **Step 1: Write the failing tests**

Add to `web/tests/strategies.test.ts` (add `getMonthlyReturns` and `MonthlyReturnsRow` to imports as needed — `getMonthlyReturns` to the value import line):

```typescript
describe("getMonthlyReturns", () => {
  async function write(rows: string[]): Promise<[string, string]> {
    const dir = await fsp.mkdtemp(path.join(os.tmpdir(), "mr-"));
    await fsp.writeFile(path.join(dir, "eq.csv"), ["Date,equity", ...rows].join("\n"));
    return ["eq.csv", dir];
  }

  it("month-end value wins; first month anchors on opening value", async () => {
    // opening 100; Jan ends 110 (+10%); Feb ends 121 (+10% vs 110)
    const [csv, dir] = await write([
      "2024-01-05,100",
      "2024-01-20,105",
      "2024-01-31,110",
      "2024-02-28,121",
    ]);
    const r = await getMonthlyReturns(csv, dir);
    expect(r.length).toBe(1);
    expect(r[0].year).toBe(2024);
    expect(r[0].months[0]).toBeCloseTo(0.10, 6); // Jan: 110/100 - 1
    expect(r[0].months[1]).toBeCloseTo(0.10, 6); // Feb: 121/110 - 1
    expect(r[0].months[2]).toBeNull();           // Mar absent
    expect(r[0].annual).toBeCloseTo(0.21, 6);    // (1.1*1.1)-1
  });

  it("gap month is null; next present month compounds from last month-end", async () => {
    // opening 100; Jan ends 110; (Feb missing); Mar ends 132 (+20% vs 110)
    const [csv, dir] = await write([
      "2024-01-31,100",
      "2024-01-31,110",
      "2024-03-31,132",
    ]);
    const r = await getMonthlyReturns(csv, dir);
    expect(r[0].months[0]).toBeCloseTo(0.10, 6); // Jan vs opening 100
    expect(r[0].months[1]).toBeNull();           // Feb gap
    expect(r[0].months[2]).toBeCloseTo(0.20, 6); // Mar vs Jan-end 110
  });

  it("annual compounds only displayed months across multiple years", async () => {
    const [csv, dir] = await write([
      "2023-12-29,100",
      "2024-06-28,110",
      "2024-12-31,121",
    ]);
    const r = await getMonthlyReturns(csv, dir);
    expect(r.map((x) => x.year)).toEqual([2023, 2024]);
    // 2023 has only Dec-end as the opening anchor point itself -> Dec return vs opening (100/100-1=0)
    expect(r[0].months[11]).toBeCloseTo(0, 6);
    expect(r[0].annual).toBeCloseTo(0, 6);
    // 2024: Jun 110/100-1=0.10 ; Dec 121/110-1=0.10 ; annual (1.1*1.1)-1
    expect(r[1].months[5]).toBeCloseTo(0.10, 6);
    expect(r[1].months[11]).toBeCloseTo(0.10, 6);
    expect(r[1].annual).toBeCloseTo(0.21, 6);
  });

  it("empty/missing csv -> []", async () => {
    expect(await getMonthlyReturns("nope.csv", FIX)).toEqual([]);
    expect(await getMonthlyReturns(null, FIX)).toEqual([]);
  });

  it("single data point (<2) -> []", async () => {
    const [csv, dir] = await write(["2024-01-31,100"]);
    expect(await getMonthlyReturns(csv, dir)).toEqual([]);
  });

  it("non-positive prior anchor -> null return guard", async () => {
    const [csv, dir] = await write([
      "2024-01-31,0",
      "2024-02-28,50",
    ]);
    const r = await getMonthlyReturns(csv, dir);
    // Jan vs opening 0 -> guarded null; Feb vs Jan-end 0 -> guarded null
    expect(r[0].months[0]).toBeNull();
    expect(r[0].months[1]).toBeNull();
    expect(r[0].annual).toBeNull(); // no non-null months
  });
});
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `npm run test -- strategies`
Expected: FAIL — `getMonthlyReturns is not a function`.

- [ ] **Step 3: Implement `getMonthlyReturns`**

Add to `web/lib/data/strategies.ts` immediately after `getEquityCurve`:

```typescript
export type MonthlyReturnsRow = {
  year: number;
  months: (number | null)[]; // length 12, index 0 = Jan
  annual: number | null;
};

export async function getMonthlyReturns(
  csv: string | null,
  dataDir: string = DEFAULT_DATA_DIR,
): Promise<MonthlyReturnsRow[]> {
  const curve = await readEquityCurveRaw(csv, dataDir);
  if (curve.length < 2) return [];

  // Month-end value per YYYY-MM, in chronological order (curve already sorted asc).
  const monthEnds = new Map<string, number>(); // "YYYY-MM" -> last value that month
  for (const p of curve) {
    monthEnds.set(p.time.slice(0, 7), p.value); // later points overwrite -> last wins
  }

  const anchor = curve[0].value; // series opening value
  let prev = anchor;

  // Build per-year rows. Keys sorted ascending => chronological walk.
  const byYear = new Map<number, MonthlyReturnsRow>();
  for (const key of [...monthEnds.keys()].sort()) {
    const year = Number(key.slice(0, 4));
    const monthIdx = Number(key.slice(5, 7)) - 1; // 0-11
    const monthEnd = monthEnds.get(key)!;
    const r = prev > 0 ? monthEnd / prev - 1 : null;
    prev = monthEnd; // advance anchor to this month-end regardless

    let row = byYear.get(year);
    if (!row) {
      row = { year, months: Array(12).fill(null), annual: null };
      byYear.set(year, row);
    }
    row.months[monthIdx] = r;
  }

  // Annual = compound of displayed (non-null) months for that year.
  const rows = [...byYear.values()].sort((a, b) => a.year - b.year);
  for (const row of rows) {
    const present = row.months.filter((m): m is number => m != null);
    row.annual = present.length
      ? present.reduce((acc, m) => acc * (1 + m), 1) - 1
      : null;
  }
  return rows;
}
```

- [ ] **Step 4: Run tests, verify they pass**

Run: `npm run test -- strategies`
Expected: PASS — all `getMonthlyReturns` cases green.

- [ ] **Step 5: Commit**

```bash
git add web/lib/data/strategies.ts web/tests/strategies.test.ts
git commit -m "feat(s4): getMonthlyReturns loader (month-end returns + annual)"
```

---

### Task 3: `MonthlyHeatmap` component + `cellColor`

**Files:**
- Create: `web/components/monthly-heatmap.tsx`
- Test: `web/tests/strategies.test.ts` (unit-test `cellColor`, same place `barWidthPct` is tested)

- [ ] **Step 1: Write the failing `cellColor` test**

Add to `web/tests/strategies.test.ts` (import `cellColor` from `@/components/monthly-heatmap`):

```typescript
describe("cellColor", () => {
  it("null -> transparent (muted blank)", () => {
    expect(cellColor(null)).toBe("transparent");
  });
  it("zero -> green with zero intensity", () => {
    expect(cellColor(0)).toBe("rgba(34,197,94,0)");
  });
  it("positive scales intensity to +10% full saturation", () => {
    expect(cellColor(0.05)).toBe("rgba(34,197,94,0.5)");
    expect(cellColor(0.10)).toBe("rgba(34,197,94,1)");
  });
  it("positive beyond +10% clamps to full", () => {
    expect(cellColor(0.25)).toBe("rgba(34,197,94,1)");
  });
  it("negative uses red, magnitude scaled and clamped", () => {
    expect(cellColor(-0.05)).toBe("rgba(239,68,68,0.5)");
    expect(cellColor(-0.10)).toBe("rgba(239,68,68,1)");
    expect(cellColor(-0.25)).toBe("rgba(239,68,68,1)");
  });
});
```

- [ ] **Step 2: Run test, verify it fails**

Run: `npm run test -- strategies`
Expected: FAIL — cannot resolve `@/components/monthly-heatmap` / `cellColor`.

- [ ] **Step 3: Create the component**

Create `web/components/monthly-heatmap.tsx`:

```tsx
import type { ReactNode } from "react";
import type { MonthlyReturnsRow } from "@/lib/data/strategies";
import { pct } from "@/lib/format";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const FULL_SATURATION = 0.1; // ±10% monthly return = full color

/** Symmetric fixed scale: green positive, red negative, alpha = |r|/10% clamped to 1. null -> transparent. */
export function cellColor(r: number | null): string {
  if (r == null) return "transparent";
  const intensity = Math.min(Math.abs(r) / FULL_SATURATION, 1);
  const rgb = r >= 0 ? "34,197,94" : "239,68,68"; // green / red
  return `rgba(${rgb},${intensity})`;
}

interface MonthlyHeatmapProps {
  rows: MonthlyReturnsRow[];
}

export function MonthlyHeatmap({ rows }: MonthlyHeatmapProps): ReactNode {
  if (rows.length === 0) return null;
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-center text-xs">
        <thead>
          <tr className="text-muted-foreground">
            <th className="px-2 py-1 text-left font-medium">Year</th>
            {MONTHS.map((m) => (
              <th key={m} className="px-2 py-1 font-medium">{m}</th>
            ))}
            <th className="px-2 py-1 font-semibold">Annual</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.year}>
              <td className="px-2 py-1 text-left font-medium">{row.year}</td>
              {row.months.map((r, i) => (
                <td
                  key={i}
                  className="px-2 py-1 tabular-nums"
                  style={{ backgroundColor: cellColor(r) }}
                >
                  {r == null ? "—" : pct(r)}
                </td>
              ))}
              <td
                className="px-2 py-1 font-semibold tabular-nums"
                style={{ backgroundColor: cellColor(row.annual) }}
              >
                {row.annual == null ? "—" : pct(row.annual)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 4: Run test, verify it passes**

Run: `npm run test -- strategies`
Expected: PASS — all `cellColor` cases green.

- [ ] **Step 5: Commit**

```bash
git add web/components/monthly-heatmap.tsx web/tests/strategies.test.ts
git commit -m "feat(s4): MonthlyHeatmap component + cellColor scale"
```

---

### Task 4: Wire into strategy detail page

**Files:**
- Modify: `web/app/strategy/[id]/page.tsx`

- [ ] **Step 1: Update imports**

In `web/app/strategy/[id]/page.tsx`, change the data import line (line 3) to add `getMonthlyReturns`, and add the component import:

```tsx
import { getStrategy, getEquityCurve, computeDrawdown, getTrades, getMonthlyReturns } from "@/lib/data/strategies";
import { LineChart } from "@/components/line-chart";
import { KpiStrip } from "@/components/kpi-strip";
import { TradesTable } from "@/components/trades-table";
import { MonthlyHeatmap } from "@/components/monthly-heatmap";
import { StrategySection } from "@/components/strategy-sections";
```

- [ ] **Step 2: Load monthly returns**

After the `const trades = await getTrades(s.tradesCsv);` line, add:

```tsx
  const monthly = await getMonthlyReturns(s.equityCsv);
```

- [ ] **Step 3: Render the section after Drawdown, before Trade History**

Between the Drawdown `</section>` and the Trade History `<section>`, insert this exact block. `getMonthlyReturns` already returns `[]` for curves with <2 points, so any non-empty result is worth showing — guard on `monthly.length > 0`:

```tsx
      {monthly.length > 0 && (
        <section>
          <h2 className="mb-2 text-lg font-semibold">Monthly Returns</h2>
          <MonthlyHeatmap rows={monthly} />
        </section>
      )}
```

- [ ] **Step 4: Typecheck + build**

Run: `npx tsc --noEmit` then `npm run build`
Expected: both clean (no type errors; build succeeds). Heed `web/AGENTS.md` Next-16 notes if build complains.

- [ ] **Step 5: Runtime verify all 4 strategies**

Run: `npm run build && npx next start -p 3009` (background), then in another shell:
```bash
curl -s localhost:3009/strategy/monthly_rotation | grep -c "Monthly Returns"
curl -s localhost:3009/strategy/ipo_edge | grep -c "Monthly Returns"
curl -s localhost:3009/strategy/momentum_edge | grep -c "Monthly Returns"
curl -s localhost:3009/strategy/pead | grep -c "Monthly Returns"
```
Expected: each returns `1` (section present) for strategies with equity curves; confirm visually that cells are colored (green/red) and the Annual column renders. Confirm leaderboard (`/leaderboard`) and home (`/`) still 200. Stop the server when done.

- [ ] **Step 6: Run full test suite**

Run: `npm run test`
Expected: PASS — all prior tests + new ones (count increased from 72).

- [ ] **Step 7: Commit**

```bash
git add web/app/strategy/[id]/page.tsx
git commit -m "feat(s4): render Monthly Returns heatmap on strategy detail page"
```

---

## Self-Review

**Spec coverage:**
- Placement (core section, after drawdown, all 4, hidden when no data) → Task 4. ✓
- `readEquityCurveRaw` extraction + `getEquityCurve` parity → Task 1. ✓
- `getMonthlyReturns` (anchor, month-end, gap, annual compound, fractions, empty→[], prev≤0 guard) → Task 2. ✓
- `MonthlyHeatmap` CSS-only + symmetric fixed `cellColor` + `pct` cells → Task 3. ✓
- Tests: raw parity, monthly cases, cellColor boundaries → Tasks 1–3. ✓
- Verification (tsc/build/runtime/other pages 200) → Task 4 steps 4-6. ✓

**Placeholder scan:** No TBD/TODO; every code step shows full code. Task 4 Step 3 contains an explicit correction note resolving the guard to `monthly.length > 0` — final code block is unambiguous.

**Type consistency:** `MonthlyReturnsRow` defined in Task 2, imported in Tasks 3 & 4. `cellColor`/`MonthlyHeatmap` exported in Task 3, imported in Task 4. `readEquityCurveRaw` exported in Task 1, used in Task 2. `EquityPoint`, `MAX_CURVE_POINTS`, `DATE_COLS`, `EQUITY_COLS` pre-existing. `pct` signature matches `lib/format.ts`. ✓
