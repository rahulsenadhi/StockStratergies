# S4 Slice 6 — IPO / Momentum / PEAD Parity Sections Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render each of IPO Edge, Momentum Edge, and PEAD their one signature artifact on `/strategy/[id]`, via the existing pluggable strategy-section dispatcher.

**Architecture:** New per-strategy server components plug into `components/strategy-sections/index.tsx` (3 new `switch` cases). They read through the `lib/data/strategies.ts` loader seam (3 new loaders + a shared `parseCsvLines` helper). One new shared `HorizontalBars` component renders both the Momentum funnel and the PEAD decile spread. The generic core (`page.tsx`, KPI/equity/drawdown/trades) and all other strategies are untouched.

**Tech Stack:** Next.js 16 (RSC, `await params`), TypeScript, Tailwind v4, shadcn/ui Table, lightweight-charts v5 (reused only for the IPO overlay), Vitest. Read-only, local-first.

**Spec:** `docs/superpowers/specs/2026-06-09-s4-ipo-momentum-pead-parity-design.md`

**Branch:** create `feat/s4-ipo-momentum-pead-parity` off `main` before Task 1.

**Working dir for all commands:** `web/` (the Next.js app). Tests: `npm test` (vitest run). All loaders live in `web/lib/data/strategies.ts`; tests in `web/tests/strategies.test.ts`; fixtures in `web/tests/fixtures/`.

---

## File Structure

- `web/lib/data/strategies.ts` — MODIFY: add `parseCsvLines` helper; hoist `cell`/`numCell` to module scope; refactor `getLiveSignals` + `getRankings` onto the helper; add `getFunnel`, `getRecentBreakouts`, `getDecileSpread`; add 3 `Strategy` fields + mapping.
- `web/components/horizontal-bars.tsx` — CREATE: shared labeled-bar viz + pure `barWidthPct` helper.
- `web/components/strategy-sections/ipo-edge.tsx` — CREATE.
- `web/components/strategy-sections/momentum-edge.tsx` — CREATE.
- `web/components/strategy-sections/pead.tsx` — CREATE.
- `web/components/strategy-sections/index.tsx` — MODIFY: 3 new cases.
- `web/tests/strategies.test.ts` — MODIFY: tests for new loaders + helper + mapping.
- `web/tests/fixtures/` — CREATE: `funnel.json`, `breakouts.csv`, `decile.csv`; MODIFY `strategies_index.json` (add keys to strategy `a`).
- `strategies_index.json` (repo root) — MODIFY: real keys for momentum_edge + pead.

---

### Task 0: Branch

- [ ] **Step 1: Create the feature branch**

Run (repo root):
```bash
git checkout -b feat/s4-ipo-momentum-pead-parity
```

---

### Task 1: Cleanup — `parseCsvLines` helper + hoist `cell`/`numCell` (slice-5 I1/I2)

Behavior-preserving refactor. Existing 51 tests are the regression guard. The new helper is used by Tasks 3 & 4.

**Files:**
- Modify: `web/lib/data/strategies.ts`
- Test: `web/tests/strategies.test.ts`

- [ ] **Step 1: Write failing tests for `parseCsvLines` and module-scope `numCell`**

Add to the imports at the top of `web/tests/strategies.test.ts` (extend the existing destructured import from `@/lib/data/strategies`): add `parseCsvLines`.

Append this block to `web/tests/strategies.test.ts`:
```ts
describe("parseCsvLines", () => {
  it("splits header + rows, trims header", async () => {
    const r = await parseCsvLines("ranks_a.csv", FIX);
    expect(r.header[0]).toBe("Rank");
    expect(r.rows.length).toBeGreaterThan(0);
    expect(Array.isArray(r.rows[0])).toBe(true);
  });
  it("lowercaseHeader flag lowercases the header", async () => {
    const r = await parseCsvLines("ranks_a.csv", FIX, true);
    expect(r.header).toContain("ticker");
  });
  it("missing file -> empty", async () => {
    expect(await parseCsvLines("nope.csv", FIX)).toEqual({ header: [], rows: [] });
  });
  it("null path -> empty", async () => {
    expect(await parseCsvLines(null, FIX)).toEqual({ header: [], rows: [] });
  });
  it("header-only file -> empty", async () => {
    const dir = await fsp.mkdtemp(path.join(os.tmpdir(), "pcl-"));
    await fsp.writeFile(path.join(dir, "h.csv"), "a,b,c");
    expect(await parseCsvLines("h.csv", dir)).toEqual({ header: [], rows: [] });
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm test`
Expected: FAIL — `parseCsvLines is not a function` (not exported yet).

- [ ] **Step 3: Add `parseCsvLines` + hoist `cell`/`numCell` to module scope**

In `web/lib/data/strategies.ts`, immediately after the `numOrNull` const (line ~19), add:
```ts
export type ParsedCsv = { header: string[]; rows: string[][] };

/** Read a CSV: trim, split on newlines, require >=1 data row, return header + raw row cells.
 *  Missing/unreadable/header-only -> { header: [], rows: [] }. Best-effort, never throws. */
export async function parseCsvLines(
  csv: string | null,
  dataDir: string = DEFAULT_DATA_DIR,
  lowercaseHeader = false,
): Promise<ParsedCsv> {
  if (!csv) return { header: [], rows: [] };
  try {
    const txt = await fs.readFile(path.join(dataDir, csv), "utf-8");
    const lines = txt.trim().split(/\r?\n/);
    if (lines.length < 2) return { header: [], rows: [] };
    const header = lines[0].split(",").map((h) => {
      const t = h.trim();
      return lowercaseHeader ? t.toLowerCase() : t;
    });
    const rows = lines.slice(1).map((l) => l.split(","));
    return { header, rows };
  } catch {
    return { header: [], rows: [] };
  }
}

const cell = (cells: string[], i: number): string =>
  i >= 0 ? (cells[i] ?? "").trim() : "";

const numCell = (cells: string[], i: number): number | null => {
  const v = cell(cells, i);
  if (v === "") return null;
  const n = Number(v);
  return Number.isNaN(n) ? null : n;
};
```

- [ ] **Step 4: Refactor `getRankings` to use the helper + module-scope `cell`/`numCell`**

Replace the entire `getRankings` function body (currently lines ~306-353) with:
```ts
export async function getRankings(
  csv: string | null,
  dataDir: string = DEFAULT_DATA_DIR,
): Promise<RankingRow[]> {
  const { header, rows } = await parseCsvLines(csv, dataDir, true);
  if (header.length === 0) return [];
  const idx = (name: string) => header.indexOf(name);
  const ti = idx("ticker");
  if (ti < 0) return [];
  const si = idx("signal");
  const ri = idx("rank");
  const ci = idx("company");
  const pi = idx("current_price");
  const reti = idx("return_%");
  const rsi = idx("rs_score");
  return rows
    .map((cells) => {
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
}
```
(Delete the now-duplicate local `cell`/`numCell` definitions that were inside the old function.)

- [ ] **Step 5: Refactor `getLiveSignals` to use the helper**

Replace the entire `getLiveSignals` function body (currently lines ~228-258) with:
```ts
export async function getLiveSignals(
  csv: string | null,
  dataDir: string = DEFAULT_DATA_DIR,
  limit: number = LIVE_LIMIT,
): Promise<LiveSignal[]> {
  const { header, rows } = await parseCsvLines(csv, dataDir, true);
  if (header.length === 0) return [];
  const ti = header.indexOf("ticker");
  const ci = header.indexOf("company");
  const si = header.indexOf("signal");
  if (ti < 0 || si < 0) return [];
  return rows
    .slice(0, limit)
    .map((cells) => {
      const ticker = cell(cells, ti);
      return {
        ticker,
        company: ci >= 0 && cell(cells, ci) !== "" ? cell(cells, ci) : ticker,
        signal: cell(cells, si),
      };
    })
    .filter((r) => r.ticker !== "");
}
```

- [ ] **Step 6: Run full suite to verify green (no regressions)**

Run: `npm test`
Expected: PASS — all prior 51 tests + 5 new `parseCsvLines` tests = 56 pass.

- [ ] **Step 7: Commit**

```bash
git add web/lib/data/strategies.ts web/tests/strategies.test.ts
git commit -m "refactor(s4): extract parseCsvLines + hoist cell/numCell (slice-5 I1/I2)"
```

---

### Task 2: `getFunnel` loader

**Files:**
- Modify: `web/lib/data/strategies.ts`
- Create: `web/tests/fixtures/funnel.json`
- Test: `web/tests/strategies.test.ts`

- [ ] **Step 1: Create the fixture**

Create `web/tests/fixtures/funnel.json`:
```json
{"total": 100, "sufficient_data": 100, "f1": 50, "f2": 40, "f3": 30, "f4": 20, "f5": 15, "f6": 12, "vol_bk": 8, "final": 8}
```

- [ ] **Step 2: Write the failing tests**

Add `getFunnel` to the destructured import in `web/tests/strategies.test.ts`. Append:
```ts
describe("getFunnel", () => {
  it("maps fixed keys to ordered labelled stages", async () => {
    const f = await getFunnel("funnel.json", FIX);
    expect(f.length).toBe(9);
    expect(f[0]).toEqual({ label: "Universe", value: 100 });
    expect(f[2]).toEqual({ label: "F1 Trend", value: 50 });
    expect(f[8]).toEqual({ label: "Vol + Breakout", value: 8 });
  });
  it("missing key -> 0", async () => {
    const dir = await fsp.mkdtemp(path.join(os.tmpdir(), "fun-"));
    await fsp.writeFile(path.join(dir, "p.json"), JSON.stringify({ total: 5 }));
    const f = await getFunnel("p.json", dir);
    expect(f[0].value).toBe(5);
    expect(f[1].value).toBe(0);
    expect(f[8].value).toBe(0);
  });
  it("missing/null/bad file -> []", async () => {
    expect(await getFunnel("nope.json", FIX)).toEqual([]);
    expect(await getFunnel(null, FIX)).toEqual([]);
    const dir = await fsp.mkdtemp(path.join(os.tmpdir(), "fun2-"));
    await fsp.writeFile(path.join(dir, "bad.json"), "{not json");
    expect(await getFunnel("bad.json", dir)).toEqual([]);
  });
});
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `npm test`
Expected: FAIL — `getFunnel is not a function`.

- [ ] **Step 4: Implement `getFunnel`**

In `web/lib/data/strategies.ts`, append:
```ts
export type FunnelStage = { label: string; value: number };

const FUNNEL_STAGES: { key: string; label: string }[] = [
  { key: "total", label: "Universe" },
  { key: "sufficient_data", label: "Has Data" },
  { key: "f1", label: "F1 Trend" },
  { key: "f2", label: "F2 Price > SMA50" },
  { key: "f3", label: "F3 MA Align" },
  { key: "f4", label: "F4 vs 52W Low" },
  { key: "f5", label: "F5 Dip Recovered" },
  { key: "f6", label: "F6 Clean Chart" },
  { key: "vol_bk", label: "Vol + Breakout" },
];

/** Momentum filter funnel: fixed key->label map. Missing key -> 0. Unreadable/bad JSON -> []. */
export async function getFunnel(
  jsonPath: string | null,
  dataDir: string = DEFAULT_DATA_DIR,
): Promise<FunnelStage[]> {
  if (!jsonPath) return [];
  try {
    const txt = await fs.readFile(path.join(dataDir, jsonPath), "utf-8");
    const data = JSON.parse(txt);
    return FUNNEL_STAGES.map(({ key, label }) => ({
      label,
      value:
        typeof data?.[key] === "number" && !Number.isNaN(data[key]) ? data[key] : 0,
    }));
  } catch {
    return [];
  }
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `npm test`
Expected: PASS — 56 + 3 = 59.

- [ ] **Step 6: Commit**

```bash
git add web/lib/data/strategies.ts web/tests/strategies.test.ts web/tests/fixtures/funnel.json
git commit -m "feat(s4): getFunnel loader + FunnelStage"
```

---

### Task 3: `getRecentBreakouts` loader

Returns the existing `TradesData` shape (so the generic `TradesTable` renders it), but with NO 8-column cap — the breakouts CSV has 9 columns.

**Files:**
- Modify: `web/lib/data/strategies.ts`
- Create: `web/tests/fixtures/breakouts.csv`
- Test: `web/tests/strategies.test.ts`

- [ ] **Step 1: Create the fixture (9 columns)**

Create `web/tests/fixtures/breakouts.csv`:
```
Ticker,Days Ago,Bk Date,Bk Price (₹),Close (₹),% Off Bk,220 EMA (₹),Vol Ratio,Stop (₹)
APOLLOHOSP,0,2026-06-09,8506.0,8506.0,0.0,7518.18,0.91,7230.1
ASTERDM,0,2026-06-09,794.7,794.7,0.0,641.8,2.12,675.5
BIOCON,1,2026-06-08,401.2,398.0,-0.8,360.0,1.4,355.0
```

- [ ] **Step 2: Write the failing tests**

Add `getRecentBreakouts` to the destructured import. Append:
```ts
describe("getRecentBreakouts", () => {
  it("returns all 9 columns + rows (no 8-col cap)", async () => {
    const r = await getRecentBreakouts("breakouts.csv", FIX);
    expect(r.columns.length).toBe(9);
    expect(r.columns[8]).toBe("Stop (₹)");
    expect(r.rows.length).toBe(3);
    expect(r.rows[0]["Ticker"]).toBe("APOLLOHOSP");
    expect(r.rows[0]["Stop (₹)"]).toBe("7230.1");
  });
  it("limit caps rows", async () => {
    const r = await getRecentBreakouts("breakouts.csv", FIX, 2);
    expect(r.rows.length).toBe(2);
  });
  it("missing/null -> empty", async () => {
    expect(await getRecentBreakouts("nope.csv", FIX)).toEqual({ columns: [], rows: [] });
    expect(await getRecentBreakouts(null, FIX)).toEqual({ columns: [], rows: [] });
  });
});
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `npm test`
Expected: FAIL — `getRecentBreakouts is not a function`.

- [ ] **Step 4: Implement `getRecentBreakouts`**

In `web/lib/data/strategies.ts`, append:
```ts
const BREAKOUTS_LIMIT = 10;

/** Live breakout watchlist. Full column set (TradesData shape, no col cap). Top-N rows. */
export async function getRecentBreakouts(
  csv: string | null,
  dataDir: string = DEFAULT_DATA_DIR,
  limit: number = BREAKOUTS_LIMIT,
): Promise<TradesData> {
  const { header, rows } = await parseCsvLines(csv, dataDir);
  if (header.length === 0) return { columns: [], rows: [] };
  const out = rows.slice(0, limit).map((cells) => {
    const row: Record<string, string> = {};
    header.forEach((c, i) => {
      row[c] = (cells[i] ?? "").trim();
    });
    return row;
  });
  return { columns: header, rows: out };
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `npm test`
Expected: PASS — 59 + 3 = 62.

- [ ] **Step 6: Commit**

```bash
git add web/lib/data/strategies.ts web/tests/strategies.test.ts web/tests/fixtures/breakouts.csv
git commit -m "feat(s4): getRecentBreakouts loader"
```

---

### Task 4: `getDecileSpread` loader

**Files:**
- Modify: `web/lib/data/strategies.ts`
- Create: `web/tests/fixtures/decile.csv`
- Test: `web/tests/strategies.test.ts`

- [ ] **Step 1: Create the fixture (includes an unsorted + a bad row)**

Create `web/tests/fixtures/decile.csv`:
```
sue_decile,fwd_60d_return
2.0,2.08
1.0,4.12
10.0,2.83
bad,9.9
3.0,
```

- [ ] **Step 2: Write the failing tests**

Add `getDecileSpread` to the destructured import. Append:
```ts
describe("getDecileSpread", () => {
  it("parses, drops bad/empty rows, sorts by decile asc", async () => {
    const r = await getDecileSpread("decile.csv", FIX);
    expect(r.map((p) => p.decile)).toEqual([1, 2, 10]); // 'bad' and empty fwd dropped
    expect(r[0]).toEqual({ decile: 1, fwdReturn: 4.12 });
    expect(r[2]).toEqual({ decile: 10, fwdReturn: 2.83 });
  });
  it("missing required column -> []", async () => {
    const dir = await fsp.mkdtemp(path.join(os.tmpdir(), "dec-"));
    await fsp.writeFile(path.join(dir, "x.csv"), "foo,bar\n1,2");
    expect(await getDecileSpread("x.csv", dir)).toEqual([]);
  });
  it("missing/null -> []", async () => {
    expect(await getDecileSpread("nope.csv", FIX)).toEqual([]);
    expect(await getDecileSpread(null, FIX)).toEqual([]);
  });
});
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `npm test`
Expected: FAIL — `getDecileSpread is not a function`.

- [ ] **Step 4: Implement `getDecileSpread`**

In `web/lib/data/strategies.ts`, append:
```ts
export type DecilePoint = { decile: number; fwdReturn: number };

/** PEAD SUE-decile -> forward 60d return. Case-insensitive header, bad rows skipped, sorted by decile asc. */
export async function getDecileSpread(
  csv: string | null,
  dataDir: string = DEFAULT_DATA_DIR,
): Promise<DecilePoint[]> {
  const { header, rows } = await parseCsvLines(csv, dataDir, true);
  if (header.length === 0) return [];
  const di = header.indexOf("sue_decile");
  const fi = header.indexOf("fwd_60d_return");
  if (di < 0 || fi < 0) return [];
  const out: DecilePoint[] = [];
  for (const cells of rows) {
    const decile = numCell(cells, di);
    const fwdReturn = numCell(cells, fi);
    if (decile == null || fwdReturn == null) continue;
    out.push({ decile, fwdReturn });
  }
  out.sort((a, b) => a.decile - b.decile);
  return out;
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `npm test`
Expected: PASS — 62 + 3 = 65.

- [ ] **Step 6: Commit**

```bash
git add web/lib/data/strategies.ts web/tests/strategies.test.ts web/tests/fixtures/decile.csv
git commit -m "feat(s4): getDecileSpread loader + DecilePoint"
```

---

### Task 5: `Strategy` type fields + index mapping

**Files:**
- Modify: `web/lib/data/strategies.ts`
- Modify: `web/tests/fixtures/strategies_index.json`
- Test: `web/tests/strategies.test.ts`

- [ ] **Step 1: Add the new keys to the test fixture index**

In `web/tests/fixtures/strategies_index.json`, on the strategy object with `"id": "a"`, add these three keys (alongside its existing keys):
```json
      "funnel_json": "funnel.json",
      "recent_breakouts_csv": "breakouts.csv",
      "decile_spread_csv": "decile.csv",
```

- [ ] **Step 2: Write the failing test**

Append to `web/tests/strategies.test.ts`:
```ts
describe("parity field mapping", () => {
  it("maps funnelJson / recentBreakoutsCsv / decileSpreadCsv", async () => {
    const s = await getStrategy("a", FIX);
    expect(s?.funnelJson).toBe("funnel.json");
    expect(s?.recentBreakoutsCsv).toBe("breakouts.csv");
    expect(s?.decileSpreadCsv).toBe("decile.csv");
  });
  it("defaults missing parity keys to null", () => {
    const m = mapStrategy({ id: "z", name: "Z" });
    expect(m.funnelJson).toBeNull();
    expect(m.recentBreakoutsCsv).toBeNull();
    expect(m.decileSpreadCsv).toBeNull();
  });
});
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `npm test`
Expected: FAIL — `funnelJson` does not exist on type `Strategy` (tsc/vitest error) or value `undefined`.

- [ ] **Step 4: Extend the `Strategy` type**

In `web/lib/data/strategies.ts`, replace the last line of the `Strategy` type:
```ts
  equityCsv: string | null; tradesCsv: string | null; lastRun: string | null; liveSignalsCsv: string | null; kpisError?: string;
```
with:
```ts
  equityCsv: string | null; tradesCsv: string | null; lastRun: string | null; liveSignalsCsv: string | null;
  funnelJson: string | null; recentBreakoutsCsv: string | null; decileSpreadCsv: string | null; kpisError?: string;
```

- [ ] **Step 5: Extend the mapping in `mapStrategy`**

In `mapStrategy`, after the `liveSignalsCsv: raw.live_signals_csv ?? null,` line, add:
```ts
    funnelJson: raw.funnel_json ?? null,
    recentBreakoutsCsv: raw.recent_breakouts_csv ?? null,
    decileSpreadCsv: raw.decile_spread_csv ?? null,
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `npm test`
Expected: PASS — 65 + 2 = 67.

- [ ] **Step 7: Commit**

```bash
git add web/lib/data/strategies.ts web/tests/strategies.test.ts web/tests/fixtures/strategies_index.json
git commit -m "feat(s4): Strategy parity fields (funnelJson/recentBreakoutsCsv/decileSpreadCsv)"
```

---

### Task 6: `HorizontalBars` shared component

Pure render + a unit-testable `barWidthPct` helper. The component itself is not rendered in tests (consistent with `sparkline.tsx`); only the math helper is tested.

**Files:**
- Create: `web/components/horizontal-bars.tsx`
- Test: `web/tests/strategies.test.ts` (math helper only)

- [ ] **Step 1: Write the failing test for `barWidthPct`**

Add a new import line near the top of `web/tests/strategies.test.ts`:
```ts
import { barWidthPct } from "@/components/horizontal-bars";
```
Append:
```ts
describe("barWidthPct", () => {
  it("scales value against max", () => {
    expect(barWidthPct(50, 100)).toBe(50);
    expect(barWidthPct(100, 100)).toBe(100);
  });
  it("maxValue <= 0 -> 0 (no div-by-zero)", () => {
    expect(barWidthPct(5, 0)).toBe(0);
    expect(barWidthPct(5, -3)).toBe(0);
  });
  it("clamps to [0, 100]", () => {
    expect(barWidthPct(-2, 100)).toBe(0);
    expect(barWidthPct(150, 100)).toBe(100);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm test`
Expected: FAIL — cannot resolve `@/components/horizontal-bars`.

- [ ] **Step 3: Implement the component**

Create `web/components/horizontal-bars.tsx`:
```tsx
export function barWidthPct(value: number, maxValue: number): number {
  if (maxValue <= 0) return 0;
  return Math.max(0, Math.min(100, (value / maxValue) * 100));
}

export type Bar = {
  label: string;
  value: number;
  valueLabel?: string;
  highlight?: boolean;
};

export function HorizontalBars({ data }: { data: Bar[] }) {
  if (data.length === 0) return null;
  const max = Math.max(...data.map((d) => d.value), 0);
  return (
    <div className="flex flex-col gap-1.5">
      {data.map((d, i) => (
        <div key={i} className="flex items-center gap-2 text-xs">
          <span className="w-36 shrink-0 text-muted-foreground">{d.label}</span>
          <div className="relative h-5 flex-1 rounded bg-muted/30">
            <div
              className={`h-full rounded ${d.highlight ? "bg-green-500" : "bg-sky-500/70"}`}
              style={{ width: `${barWidthPct(d.value, max)}%` }}
            />
          </div>
          <span className="w-24 shrink-0 text-right tabular-nums">
            {d.valueLabel ?? d.value}
          </span>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test`
Expected: PASS — 67 + 3 = 70.

- [ ] **Step 5: Commit**

```bash
git add web/components/horizontal-bars.tsx web/tests/strategies.test.ts
git commit -m "feat(s4): HorizontalBars shared bar viz + barWidthPct"
```

---

### Task 7: IPO Edge section + dispatcher case

**Files:**
- Create: `web/components/strategy-sections/ipo-edge.tsx`
- Modify: `web/components/strategy-sections/index.tsx`

- [ ] **Step 1: Create the IPO Edge section**

Create `web/components/strategy-sections/ipo-edge.tsx`:
```tsx
import { getEquityWithBenchmark } from "@/lib/data/strategies";
import type { Strategy } from "@/lib/data/strategies";
import { MultiLineChart } from "@/components/multi-line-chart";
import { pct } from "@/lib/format";

interface IpoEdgeSectionProps {
  strategy: Strategy;
}

export async function IpoEdgeSection({ strategy }: IpoEdgeSectionProps) {
  const eq = await getEquityWithBenchmark(strategy.equityCsv);
  const series = [
    { name: "IPO Edge", color: "#22c55e", points: eq.strategy },
    { name: "Nifty", color: "#f59e0b", points: eq.benchmark },
  ].filter((s) => s.points.length > 0);
  if (series.length === 0) return null;

  const alpha =
    strategy.kpis.cagr != null && eq.benchmarkCagr != null
      ? strategy.kpis.cagr - eq.benchmarkCagr
      : null;

  return (
    <section>
      <div className="mb-2 flex items-baseline justify-between">
        <h2 className="text-lg font-semibold">Growth vs Nifty</h2>
        <span className="text-sm text-muted-foreground">
          Extra vs Nifty (Alpha):{" "}
          <span
            className={
              alpha == null
                ? "text-muted-foreground"
                : alpha >= 0
                  ? "text-green-500"
                  : "text-red-500"
            }
          >
            {pct(alpha)}
          </span>
        </span>
      </div>
      <MultiLineChart series={series} />
    </section>
  );
}
```

- [ ] **Step 2: Wire the dispatcher case**

In `web/components/strategy-sections/index.tsx`, add the import after the `MonthlyRotationSection` import:
```tsx
import { IpoEdgeSection } from "@/components/strategy-sections/ipo-edge";
```
And add this case to the `switch`, before `default`:
```tsx
    case "ipo_edge":
      return <IpoEdgeSection strategy={strategy} />;
```

- [ ] **Step 3: Verify type-check + tests still pass**

Run: `npx tsc --noEmit` then `npm test`
Expected: tsc clean; tests 70 pass (unchanged).

- [ ] **Step 4: Commit**

```bash
git add web/components/strategy-sections/ipo-edge.tsx web/components/strategy-sections/index.tsx
git commit -m "feat(s4): IPO Edge parity section (equity-vs-Nifty + alpha)"
```

---

### Task 8: Momentum Edge section + dispatcher case

**Files:**
- Create: `web/components/strategy-sections/momentum-edge.tsx`
- Modify: `web/components/strategy-sections/index.tsx`

- [ ] **Step 1: Create the Momentum Edge section**

Create `web/components/strategy-sections/momentum-edge.tsx`:
```tsx
import { getFunnel, getRecentBreakouts } from "@/lib/data/strategies";
import type { Strategy } from "@/lib/data/strategies";
import { HorizontalBars } from "@/components/horizontal-bars";
import { TradesTable } from "@/components/trades-table";

interface MomentumEdgeSectionProps {
  strategy: Strategy;
}

export async function MomentumEdgeSection({ strategy }: MomentumEdgeSectionProps) {
  const funnel = await getFunnel(strategy.funnelJson);
  const breakouts = await getRecentBreakouts(strategy.recentBreakoutsCsv);

  const universe = funnel[0]?.value ?? 0;
  const bars = funnel.map((s, i) => ({
    label: s.label,
    value: s.value,
    valueLabel:
      universe > 0
        ? `${s.value} (${((s.value / universe) * 100).toFixed(0)}%)`
        : String(s.value),
    highlight: i === funnel.length - 1,
  }));

  const hasFunnel = funnel.length > 0;
  const hasBreakouts = breakouts.columns.length > 0 && breakouts.rows.length > 0;
  if (!hasFunnel && !hasBreakouts) return null;

  return (
    <>
      {hasFunnel && (
        <section>
          <h2 className="mb-1 text-lg font-semibold">Filter Funnel</h2>
          <p className="mb-2 text-sm text-muted-foreground">
            How the universe narrows to today&apos;s signals. Each bar is a gate; the
            drop to the next is how many stocks failed it.
          </p>
          <HorizontalBars data={bars} />
        </section>
      )}
      {hasBreakouts && (
        <section>
          <h2 className="mb-2 text-lg font-semibold">Recent Breakouts</h2>
          <TradesTable columns={breakouts.columns} rows={breakouts.rows} />
        </section>
      )}
    </>
  );
}
```

- [ ] **Step 2: Wire the dispatcher case**

In `web/components/strategy-sections/index.tsx`, add the import:
```tsx
import { MomentumEdgeSection } from "@/components/strategy-sections/momentum-edge";
```
And add the case before `default`:
```tsx
    case "momentum_edge":
      return <MomentumEdgeSection strategy={strategy} />;
```

- [ ] **Step 3: Verify type-check + tests**

Run: `npx tsc --noEmit` then `npm test`
Expected: tsc clean; tests 70 pass.

- [ ] **Step 4: Commit**

```bash
git add web/components/strategy-sections/momentum-edge.tsx web/components/strategy-sections/index.tsx
git commit -m "feat(s4): Momentum Edge parity section (filter funnel + recent breakouts)"
```

---

### Task 9: PEAD section + dispatcher case

**Files:**
- Create: `web/components/strategy-sections/pead.tsx`
- Modify: `web/components/strategy-sections/index.tsx`

- [ ] **Step 1: Create the PEAD section**

Create `web/components/strategy-sections/pead.tsx`:
```tsx
import { getDecileSpread } from "@/lib/data/strategies";
import type { Strategy } from "@/lib/data/strategies";
import { HorizontalBars } from "@/components/horizontal-bars";

interface PeadSectionProps {
  strategy: Strategy;
}

export async function PeadSection({ strategy }: PeadSectionProps) {
  const spread = await getDecileSpread(strategy.decileSpreadCsv);
  if (spread.length === 0) return null;

  const bars = spread.map((p) => ({
    label: `Decile ${p.decile}`,
    value: p.fwdReturn,
    valueLabel: `${p.fwdReturn.toFixed(2)}%`,
    highlight: p.decile === 10,
  }));

  return (
    <section>
      <h2 className="mb-1 text-lg font-semibold">SUE Decile Spread</h2>
      <p className="mb-2 text-sm text-muted-foreground">
        Average forward 60-day return by earnings-surprise (SUE) decile. The strategy
        buys decile 10 (highlighted).
      </p>
      <HorizontalBars data={bars} />
    </section>
  );
}
```

- [ ] **Step 2: Wire the dispatcher case**

In `web/components/strategy-sections/index.tsx`, add the import:
```tsx
import { PeadSection } from "@/components/strategy-sections/pead";
```
And add the case before `default`:
```tsx
    case "pead":
      return <PeadSection strategy={strategy} />;
```

- [ ] **Step 3: Verify type-check + tests**

Run: `npx tsc --noEmit` then `npm test`
Expected: tsc clean; tests 70 pass.

- [ ] **Step 4: Commit**

```bash
git add web/components/strategy-sections/pead.tsx web/components/strategy-sections/index.tsx
git commit -m "feat(s4): PEAD parity section (SUE decile spread)"
```

---

### Task 10: Wire real index keys + full verification

**Files:**
- Modify: `strategies_index.json` (repo root)

- [ ] **Step 1: Add real data keys to the root index**

In `strategies_index.json` (repo root), on the `momentum_edge` strategy object, add (alongside its existing `live_signals_csv`):
```json
      "funnel_json": "momentum_edge_funnel.json",
      "recent_breakouts_csv": "momentum_edge_recent_breakouts.csv",
```
On the `pead` strategy object, add (alongside its existing `kpis_csv`):
```json
      "decile_spread_csv": "pead_decile_spread.csv",
```

- [ ] **Step 2: Build**

Run (in `web/`): `npm run build`
Expected: build completes with no type errors.

- [ ] **Step 3: Runtime verification**

Run (in `web/`): `npx next start -p 3011 &` then curl each route (wait for "Ready"):
```bash
curl -s localhost:3011/strategy/ipo_edge      | grep -c "Growth vs Nifty"
curl -s localhost:3011/strategy/momentum_edge | grep -c "Filter Funnel"
curl -s localhost:3011/strategy/momentum_edge | grep -c "Recent Breakouts"
curl -s localhost:3011/strategy/pead          | grep -c "SUE Decile Spread"
curl -s localhost:3011/strategy/monthly_rotation | grep -c "Growth vs Nifty"
curl -s -o /dev/null -w "%{http_code}" localhost:3011/leaderboard
```
Expected: each `grep -c` ≥ 1; monthly_rotation still shows its "Growth vs Nifty" (unchanged); leaderboard → `200`. Stop the server afterward.

(Windows note: if `&` backgrounding misbehaves in the shell, start `next start` in a separate background process and poll the port; see [[s4-nextjs-frontend]] gotchas.)

- [ ] **Step 4: Full test suite**

Run (in `web/`): `npm test`
Expected: 70 pass.

- [ ] **Step 5: Commit**

```bash
git add strategies_index.json
git commit -m "feat(s4): wire funnel/breakouts/decile index keys for parity sections"
```

---

## Self-Review notes (already reconciled)

- **Spec I1 location correction:** the spec said `cell`/`numCell` live in `rankings-table.tsx`; they actually live inside `getRankings` in `strategies.ts`. Task 1 hoists them there (and they get reused by `getDecileSpread`). The `rankings-table.tsx` `fmtPrice`/`fmtPctNum` are already module-scope — no change needed.
- **PEAD value unit:** decile `fwd_60d_return` rendered as `%` (values ~0.14–4.12 are percent forward returns, matching the Streamlit decile-spread chart).
- **No new chart lib:** funnel + decile use CSS/SVG bars (`HorizontalBars`), not lightweight-charts. The IPO overlay reuses the existing `MultiLineChart`.
- **Test count:** 51 → 70 (+19). Existing tests must stay green after the Task 1 refactor.

## Done when

All 10 tasks committed on `feat/s4-ipo-momentum-pead-parity`; `npm test` 70 pass; `npm run build` clean; the 4 runtime curls confirm each section renders and `/strategy/monthly_rotation` + `/leaderboard` are unchanged. Then use superpowers:finishing-a-development-branch to merge + push.
