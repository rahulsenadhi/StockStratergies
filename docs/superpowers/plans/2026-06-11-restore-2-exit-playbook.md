# Restore Slice 2 — Exit Playbook

> Subagent-driven. Additive, dense — NO restyle. Faithful port of Streamlit `_exit_playbook_card`/`_exit_playbook_summary` reading the precomputed `exit_recommendations.json`.

**Goal:** Show, per strategy, the "how to manage the buy" plan: recommended hold days, the 3-tier scale-out target ladder (target % + book % + historical hit-rate), stop level, sample size, and a return-by-day mini-curve — directly the buying/holding guidance from :8500.

**Data:** `exit_recommendations.json` at repo root — `{ [strategyId]: { [bucket]: Recommendation } }`. Use the `"ALL"` bucket. Recommendation = `{strategy, bucket, hold_days, hold_median_return, hold_win_rate, targets:[{pct,book_pct,hit_rate}], stop_pct, sample_size, data_quality:"ohlcv"|"close", curve:[{day,median,...}]}`. All 4 strategy ids present (momentum_edge, ipo_edge, pead, monthly_rotation).

**Source of truth:** `core/exit_analyzer.py:34-52` (dataclasses), `master_dashboard.py:2417-2450` (summary + card render).

---

## Task 1: Exit Playbook loader
**Files:** Modify `web/lib/data/strategies.ts`; create `web/tests/exit-playbook.test.ts`.

- [ ] Step 1 — failing test (temp-dir fixture like `tests/strategy-create.test.ts`):
```typescript
import { describe, it, expect } from "vitest";
import path from "node:path";
import os from "node:os";
import { promises as fsp } from "node:fs";
import { getExitPlaybook } from "@/lib/data/strategies";

async function seed(): Promise<string> {
  const dir = await fsp.mkdtemp(path.join(os.tmpdir(), "exit-"));
  await fsp.writeFile(path.join(dir, "exit_recommendations.json"), JSON.stringify({
    momentum_edge: { ALL: {
      strategy: "momentum_edge", bucket: "ALL", hold_days: 79,
      hold_median_return: 57.17, hold_win_rate: 0.94,
      targets: [{ pct: 41.6, book_pct: 40, hit_rate: 0.59 }, { pct: 75.5, book_pct: 35, hit_rate: 0.34 }, { pct: 161.7, book_pct: 25, hit_rate: 0.16 }],
      stop_pct: -8.4, sample_size: 32, data_quality: "ohlcv",
      curve: [{ day: 1, median: 2.1 }, { day: 2, median: 3.4 }],
    } },
  }));
  return dir;
}

describe("getExitPlaybook", () => {
  it("returns the ALL bucket recommendation, camelCased", async () => {
    const dir = await seed();
    const r = await getExitPlaybook("momentum_edge", dir);
    expect(r).not.toBeNull();
    expect(r!.holdDays).toBe(79);
    expect(r!.holdWinRate).toBeCloseTo(0.94);
    expect(r!.targets).toHaveLength(3);
    expect(r!.targets[0]).toEqual({ pct: 41.6, bookPct: 40, hitRate: 0.59 });
    expect(r!.stopPct).toBeCloseTo(-8.4);
    expect(r!.sampleSize).toBe(32);
    expect(r!.dataQuality).toBe("ohlcv");
    expect(r!.curve.map((c) => c.median)).toEqual([2.1, 3.4]);
  });
  it("returns null for an unknown strategy", async () => {
    const dir = await seed();
    expect(await getExitPlaybook("nope", dir)).toBeNull();
  });
  it("returns null when the file is missing", async () => {
    const dir = await fsp.mkdtemp(path.join(os.tmpdir(), "exit-empty-"));
    expect(await getExitPlaybook("momentum_edge", dir)).toBeNull();
  });
});
```
- [ ] Step 2 — run → fail.
- [ ] Step 3 — implement in `web/lib/data/strategies.ts` (follow the file's existing loader + `DATA_DIR` resolution conventions — read how other loaders resolve `dataDir`/read files):
```typescript
export interface ExitTarget { pct: number; bookPct: number; hitRate: number; }
export interface ExitPlaybook {
  holdDays: number; holdMedianReturn: number; holdWinRate: number;
  targets: ExitTarget[]; stopPct: number; sampleSize: number;
  dataQuality: "ohlcv" | "close"; curve: { day: number; median: number }[];
}
export async function getExitPlaybook(id: string, dataDir?: string): Promise<ExitPlaybook | null> {
  // resolve <dataDir|DATA_DIR|..>/exit_recommendations.json, read+parse (try/catch → null)
  // pick obj[id]?.ALL ; if absent → null ; else map snake_case → camelCase incl targets[] + curve[]
}
```
Match the module's existing read pattern (e.g. how `getStrategySpec`/`parseCsvLines` resolve the data dir). Missing file / parse error / missing id / missing ALL → return null (never throw).
- [ ] Step 4 — run → pass.
- [ ] Step 5 — commit: `feat(restore): getExitPlaybook loader (exit_recommendations.json)`

## Task 2: ExitPlaybook component + wire into detail page
**Files:** Create `web/components/exit-playbook.tsx`; modify `web/app/strategy/[id]/page.tsx`.

- [ ] `exit-playbook.tsx` — async server component `<ExitPlaybook id={id} />`:
  - `const rec = await getExitPlaybook(id);` — null → render a muted note: "Exit Playbook: insufficient trade history yet." (small text), then return.
  - **One-line summary** (port `_exit_playbook_summary`): `Hold ~{holdDays}d · T1/T2/T3 +{t0.pct|0}/+{t1.pct|0}/+{t2.pct|0}% · Stop {stopPct|0}%` (round to whole numbers; guard <3 targets → "targets n/a").
  - **3 compact stats** (inline, dense — small `text-sm`, NOT big StatTiles): Recommended hold `{holdDays} days`, Median return at hold `{holdMedianReturn.toFixed(1)}%`, Win rate at hold `{(holdWinRate*100).toFixed(0)}%`.
  - **Target ladder table** (reuse existing compact table style, e.g. `components/ui/table` or plain `<table>` matching the app): columns Tier (T1/T2/T3) · Profit target (`+{pct.toFixed(1)}%`) · Book (`{bookPct}%`) · Hit rate (hist.) (`{(hitRate*100).toFixed(0)}%`).
  - **Caption**: `Stop {stopPct.toFixed(1)}% · sample {sampleSize} trades · data {dataQuality==="ohlcv" ? "intraday OHLCV" : "close-only (approx.)"}`.
  - **Return-by-day mini-curve**: reuse `components/sparkline.tsx` (it takes a numeric array) fed `curve.map(c=>c.median)` — small inline sparkline labeled "median return by day". If sparkline's prop signature doesn't fit cleanly, omit the curve (note it) — the ladder+stats are the core.
  - Heading: a compact `#### Exit Playbook` equivalent (`<h3 className="text-sm font-semibold">Exit Playbook</h3>`).
- [ ] Detail page: import + render `<ExitPlaybook id={s.id} />` after `<StrategyExplainer>` (before equity section). It's an async server component — `await` is fine in the RSC page (or render directly; Next supports async server components as children).
- [ ] `npx tsc --noEmit` clean; `npx next build` clean. Commit: `feat(restore): Exit Playbook block on strategy detail`

## Task 3: verify + finish
- [ ] (web/) `npx vitest run` (168 + exit-playbook tests green); `npx tsc --noEmit`; `npx next build` clean.
- [ ] Runtime: `/strategy/momentum_edge` shows Exit Playbook (hold ~79d, 3-tier ladder +41.6/+75.5/+161.7%, stop −8.4%, sample 32); a strategy with no rec shows the muted note.
- [ ] Update `streamlit_feature_restore_program.md` (slice 2 DONE). Finish branch: merge main + **push origin** (push-each-slice cadence).

---

## Self-Review
Covers loader (T1) + component+page (T2) + verify (T3). Additive, dense (no big cards). Data fully precomputed in exit_recommendations.json (no engine re-derivation). Faithful to `_exit_playbook_card` render. `ExitPlaybook`/`ExitTarget` types consistent loader↔component. Curve via existing Sparkline (numeric array) or omitted. Loader never throws (→ null).
