# Run-Backtest Write-API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A per-strategy "Run Backtest" button on `/strategy/[id]` re-runs the strategy's backtest script (regenerating CSVs), chains a recompute, and live-refreshes — reusing the slice-9 subprocess mechanism.

**Architecture:** Declarative `backtest` argv per strategy in `strategies_index.json` → loader exposes `Strategy.backtest` → pure `resolveBacktest` validates+resolves it → shared `job-lock` serializes heavy jobs → `POST /api/backtest {id}` spawns the backtest then chains `python -m core.leaderboard` via the existing generic `runRecompute` → `"use client"` `BacktestButton` POSTs and `router.refresh()`s.

**Tech Stack:** Next.js 16 Route Handler + client component, TypeScript, `node:child_process`, Vitest.

**Spec:** `docs/superpowers/specs/2026-06-09-s4-write-api-run-backtest-design.md`

**Grounding facts:**
- Slice 9 left `web/lib/recompute.ts` with `resolveRecompute`, the generic `runRecompute(spawnFn, {bin,args,cwd,timeoutMs}) -> Promise<{status,body}>`, and types `RecomputeResult`/`SpawnedChild`/`SpawnFn`. Reuse `runRecompute` verbatim (command comes from `opts.args`).
- `web/app/api/recompute/route.ts` currently holds its own `let running` lock (full current source reproduced in Task 2).
- Loader `web/lib/data/strategies.ts`: `Strategy` type (~lines 12-17), `mapStrategy(raw)` (lines 57-84, reproduced in Task 1), `getStrategy(id, dataDir?)`. `DATA_DIR=".."` → repo root.
- Strategy-detail page `web/app/strategy/[id]/page.tsx` header (current):
  ```tsx
      <div>
        <h1 className="text-2xl font-bold">{s.name}</h1>
        <p className="text-sm text-muted-foreground">{s.type} · {s.status}</p>
      </div>
  ```
- `recompute-button.tsx` (slice 9) is the pattern to mirror for the new button.
- Tests: `web/tests/` (vitest, `npm run test` from `web/`). `web/tests/recompute.test.ts` exists. Loader tests in `web/tests/strategies.test.ts` use `mapStrategy` directly.
- Repo root has built-in scripts `momentum_edge_backtest.py`, `ipo_edge_backtest.py` (both run with no args).

**File structure:**
- `web/lib/data/strategies.ts` — `Strategy.backtest` + `mapStrategy` (Task 1).
- `strategies_index.json` (repo root) — add `backtest` to momentum_edge + ipo_edge (Task 1).
- `web/lib/job-lock.ts` — NEW shared lock (Task 2).
- `web/app/api/recompute/route.ts` — refactor to shared lock (Task 2).
- `web/lib/recompute.ts` — add `resolveBacktest` (Task 3).
- `web/app/api/backtest/route.ts` — NEW route (Task 4).
- `web/components/backtest-button.tsx` — NEW client button (Task 5).
- `web/app/strategy/[id]/page.tsx` — wire button (Task 5).
- Tests: `web/tests/strategies.test.ts` (Task 1), `web/tests/backtest.test.ts` NEW (Tasks 2-3).

---

### Task 1: Loader `backtest` field + index data

**Files:**
- Modify: `web/lib/data/strategies.ts` (`Strategy` type + `mapStrategy`)
- Modify: `strategies_index.json` (repo root)
- Test: `web/tests/strategies.test.ts`

- [ ] **Step 1: Write the failing test**

Add to `web/tests/strategies.test.ts` (in the `mapStrategy` describe block, or a new one):

```typescript
describe("mapStrategy backtest field", () => {
  it("maps a backtest argv array", () => {
    const m = mapStrategy({ id: "x", backtest: ["momentum_edge_backtest.py"] });
    expect(m.backtest).toEqual(["momentum_edge_backtest.py"]);
  });
  it("defaults to null when absent or not an array", () => {
    expect(mapStrategy({ id: "y" }).backtest).toBeNull();
    expect(mapStrategy({ id: "z", backtest: "nope" }).backtest).toBeNull();
  });
});
```

- [ ] **Step 2: Run, verify it fails**

Run: `cd web && npm run test -- strategies`
Expected: FAIL — `m.backtest` is `undefined` / property missing on type.

- [ ] **Step 3: Add the field to the type + mapper**

In `web/lib/data/strategies.ts`, in the `Strategy` type add `backtest: string[] | null;` (put it next to `decileSpreadCsv`). The type block becomes:

```typescript
export type Strategy = {
  id: string; name: string; type: string; status: string;
  kpis: Kpis; rank: number | null; rankScore: number | null;
  equityCsv: string | null; tradesCsv: string | null; lastRun: string | null; liveSignalsCsv: string | null;
  funnelJson: string | null; recentBreakoutsCsv: string | null; decileSpreadCsv: string | null;
  backtest: string[] | null; kpisError?: string;
};
```

In `mapStrategy`, add the field to the constructed object (right after `decileSpreadCsv: raw.decile_spread_csv ?? null,`):

```typescript
    decileSpreadCsv: raw.decile_spread_csv ?? null,
    backtest: Array.isArray(raw.backtest) ? raw.backtest : null,
```

- [ ] **Step 4: Run, verify it passes**

Run: `cd web && npm run test -- strategies`
Expected: PASS — both new cases green; existing strategies tests still pass.

- [ ] **Step 5: Add the `backtest` argv to the two built-in strategies in the index**

The repo-root `strategies_index.json` is `indent=2` JSON. Add the field deterministically with this one-liner from the **repo root** (NOT `web/`) so formatting matches `refresh_all`'s writer:

```bash
python -c "import json,io; p='strategies_index.json'; d=json.load(open(p)); m={'momentum_edge':['momentum_edge_backtest.py'],'ipo_edge':['ipo_edge_backtest.py']}; [s.__setitem__('backtest', m[s['id']]) for s in d['strategies'] if s['id'] in m]; open(p,'w').write(json.dumps(d, indent=2, default=str))"
```

Verify exactly two entries gained the field and pead/monthly did not:

```bash
python -c "import json; d=json.load(open('strategies_index.json')); print({s['id']: s.get('backtest') for s in d['strategies']})"
```

Expected: `{'monthly_rotation': None, 'ipo_edge': ['ipo_edge_backtest.py'], 'momentum_edge': ['momentum_edge_backtest.py'], 'pead': None}` (order may differ).

- [ ] **Step 6: Commit**

```bash
git add web/lib/data/strategies.ts web/tests/strategies.test.ts strategies_index.json
git commit -m "feat(s4): Strategy.backtest argv field + wire momentum_edge/ipo_edge"
```

---

### Task 2: Shared `job-lock` + refactor recompute route

**Files:**
- Create: `web/lib/job-lock.ts`
- Modify: `web/app/api/recompute/route.ts`
- Test: `web/tests/backtest.test.ts` (new)

- [ ] **Step 1: Write the failing test**

Create `web/tests/backtest.test.ts`:

```typescript
import { describe, it, expect, beforeEach } from "vitest";
import { tryAcquire, release, isHeld } from "@/lib/job-lock";

describe("job-lock", () => {
  beforeEach(() => release()); // singleton module — reset between tests

  it("acquires when free, refuses while held", () => {
    expect(isHeld()).toBe(false);
    expect(tryAcquire()).toBe(true);
    expect(isHeld()).toBe(true);
    expect(tryAcquire()).toBe(false); // already held
  });

  it("release frees the lock", () => {
    expect(tryAcquire()).toBe(true);
    release();
    expect(isHeld()).toBe(false);
    expect(tryAcquire()).toBe(true);
  });
});
```

- [ ] **Step 2: Run, verify it fails**

Run: `cd web && npm run test -- backtest`
Expected: FAIL — cannot resolve `@/lib/job-lock`.

- [ ] **Step 3: Create `web/lib/job-lock.ts`**

```typescript
// Shared single-process in-flight lock so heavy jobs (recompute, backtest) cannot overlap.
let held = false;

export function tryAcquire(): boolean {
  if (held) return false;
  held = true;
  return true;
}

export function release(): void {
  held = false;
}

export function isHeld(): boolean {
  return held;
}
```

- [ ] **Step 4: Run, verify it passes**

Run: `cd web && npm run test -- backtest`
Expected: PASS — both `job-lock` cases green.

- [ ] **Step 5: Refactor the recompute route to use the shared lock**

Replace the ENTIRE contents of `web/app/api/recompute/route.ts` with:

```typescript
import { NextResponse } from "next/server";
import { spawn } from "node:child_process";
import { resolveRecompute, runRecompute, type SpawnedChild } from "@/lib/recompute";
import { tryAcquire, release } from "@/lib/job-lock";

export const dynamic = "force-dynamic";

const TIMEOUT_MS = 120_000;

export async function POST() {
  if (!tryAcquire()) {
    return NextResponse.json(
      { ok: false, error: "A job is already running" },
      { status: 409 },
    );
  }
  try {
    const { bin, args, cwd } = resolveRecompute(process.env, process.cwd());
    const { status, body } = await runRecompute(
      (b, a, o) => spawn(b, a, o) as unknown as SpawnedChild,
      { bin, args, cwd, timeoutMs: TIMEOUT_MS },
    );
    return NextResponse.json(body, { status });
  } finally {
    release();
  }
}
```

- [ ] **Step 6: Verify the full suite still passes**

Run: `cd web && npm run test`
Expected: PASS — prior 99 + 2 new `job-lock` = 101. (The recompute route is integration-verified; its 409 message changed to "A job is already running" but no unit test asserts that string.)

- [ ] **Step 7: Commit**

```bash
git add web/lib/job-lock.ts web/app/api/recompute/route.ts web/tests/backtest.test.ts
git commit -m "feat(s4): shared job-lock; recompute route uses it"
```

---

### Task 3: `resolveBacktest` helper

**Files:**
- Modify: `web/lib/recompute.ts` (add `resolveBacktest`)
- Test: `web/tests/backtest.test.ts`

- [ ] **Step 1: Write the failing tests**

Add to `web/tests/backtest.test.ts` (add `import { resolveBacktest } from "@/lib/recompute";`):

```typescript
describe("resolveBacktest", () => {
  it("resolves a valid argv to bin/args/cwd", () => {
    const r = resolveBacktest(["momentum_edge_backtest.py"], "/repo", {});
    expect(r).toEqual({ bin: "python", args: ["momentum_edge_backtest.py"], cwd: "/repo" });
  });
  it("honors PYTHON_BIN", () => {
    expect(resolveBacktest(["x.py"], "/repo", { PYTHON_BIN: "python3" }).bin).toBe("python3");
  });
  it("passes through extra argv elements", () => {
    expect(resolveBacktest(["a.py", "--flag", "v"], "/repo", {}).args).toEqual(["a.py", "--flag", "v"]);
  });
  it("throws when not configured (null/empty)", () => {
    expect(() => resolveBacktest(null, "/repo", {})).toThrow();
    expect(() => resolveBacktest([], "/repo", {})).toThrow();
  });
  it("rejects absolute paths", () => {
    expect(() => resolveBacktest(["/etc/x.py"], "/repo", {})).toThrow();
    expect(() => resolveBacktest(["C:\\x.py"], "/repo", {})).toThrow();
  });
  it("rejects .. traversal", () => {
    expect(() => resolveBacktest(["../x.py"], "/repo", {})).toThrow();
  });
  it("rejects a non-.py first arg", () => {
    expect(() => resolveBacktest(["momentum_edge_backtest"], "/repo", {})).toThrow();
  });
  it("rejects shell metacharacters anywhere in argv", () => {
    expect(() => resolveBacktest(["x.py", "; rm -rf /"], "/repo", {})).toThrow();
  });
});
```

- [ ] **Step 2: Run, verify it fails**

Run: `cd web && npm run test -- backtest`
Expected: FAIL — `resolveBacktest is not a function`.

- [ ] **Step 3: Add `resolveBacktest` to `web/lib/recompute.ts`**

Append (after `runRecompute`):

```typescript
/**
 * Resolve a strategy's declarative backtest argv (from the trusted index, NOT the request)
 * to a spawn command. Validates defensively: repo-relative .py first arg, no absolute path,
 * no ".." traversal, no shell metacharacters anywhere. Throws on invalid/missing argv.
 */
export function resolveBacktest(
  argv: string[] | null,
  repoRoot: string,
  env: { PYTHON_BIN?: string },
): { bin: string; args: string[]; cwd: string } {
  if (!argv || argv.length === 0) throw new Error("no backtest command configured");
  const script = argv[0];
  if (
    script.startsWith("/") ||
    /^[a-zA-Z]:/.test(script) || // windows absolute (C:\...)
    script.includes("..") ||
    !script.endsWith(".py") ||
    /[;&|`$<>\n]/.test(argv.join(" ")) // shell metacharacters anywhere
  ) {
    throw new Error(`unsafe backtest command: ${script}`);
  }
  return {
    bin: env.PYTHON_BIN ?? "python",
    args: argv,
    cwd: repoRoot,
  };
}
```

- [ ] **Step 4: Run, verify it passes**

Run: `cd web && npm run test -- backtest`
Expected: PASS — all `resolveBacktest` cases + `job-lock` cases green.

- [ ] **Step 5: Commit**

```bash
git add web/lib/recompute.ts web/tests/backtest.test.ts
git commit -m "feat(s4): resolveBacktest argv validator/resolver"
```

---

### Task 4: `POST /api/backtest` route handler

**Files:**
- Create: `web/app/api/backtest/route.ts`

- [ ] **Step 1: Create the route handler**

```typescript
import { NextResponse } from "next/server";
import { spawn } from "node:child_process";
import path from "node:path";
import { runRecompute, resolveBacktest, type SpawnedChild } from "@/lib/recompute";
import { getStrategy } from "@/lib/data/strategies";
import { tryAcquire, release } from "@/lib/job-lock";

export const dynamic = "force-dynamic";

const BACKTEST_TIMEOUT_MS = 600_000;
const RECOMPUTE_TIMEOUT_MS = 120_000;

const spawnChild = (b: string, a: string[], o: { cwd: string }) =>
  spawn(b, a, o) as unknown as SpawnedChild;

export async function POST(request: Request) {
  const body = (await request.json().catch(() => ({}))) as { id?: unknown };
  const id = body.id;
  if (typeof id !== "string" || id.length === 0) {
    return NextResponse.json({ ok: false, error: "missing id" }, { status: 400 });
  }

  const strategy = await getStrategy(id);
  if (!strategy) {
    return NextResponse.json({ ok: false, error: "unknown strategy" }, { status: 404 });
  }
  if (!strategy.backtest) {
    return NextResponse.json(
      { ok: false, error: "backtest not configured for this strategy" },
      { status: 422 },
    );
  }

  if (!tryAcquire()) {
    return NextResponse.json(
      { ok: false, error: "A job is already running" },
      { status: 409 },
    );
  }
  try {
    const repoRoot = path.resolve(process.cwd(), process.env.DATA_DIR ?? "..");
    let bt: { bin: string; args: string[]; cwd: string };
    try {
      bt = resolveBacktest(strategy.backtest, repoRoot, process.env);
    } catch (e) {
      return NextResponse.json(
        { ok: false, error: e instanceof Error ? e.message : String(e) },
        { status: 500 },
      );
    }

    // Step 1: run the backtest (regenerates the strategy's CSVs).
    const backtestRun = await runRecompute(spawnChild, {
      ...bt,
      timeoutMs: BACKTEST_TIMEOUT_MS,
    });
    if (backtestRun.status !== 200) {
      return NextResponse.json(backtestRun.body, { status: backtestRun.status });
    }

    // Step 2: chain a recompute to refresh KPIs + rank in the index.
    const recomputeRun = await runRecompute(spawnChild, {
      bin: bt.bin,
      args: ["-m", "core.leaderboard"],
      cwd: repoRoot,
      timeoutMs: RECOMPUTE_TIMEOUT_MS,
    });
    return NextResponse.json(recomputeRun.body, { status: recomputeRun.status });
  } finally {
    release();
  }
}
```

- [ ] **Step 2: Typecheck + build**

Run: `cd web && npx tsc --noEmit` then `npm run build`
Expected: both clean. `/api/backtest` listed as a dynamic API route. The `POST(request: Request)` signature is valid App Router. If Next-16 flags it, consult `web/AGENTS.md` + `node_modules/next/dist/docs/`.

- [ ] **Step 3: Full suite (no regressions)**

Run: `cd web && npm run test`
Expected: PASS — 101 (no new unit tests this task; route is integration-verified in Task 5).

- [ ] **Step 4: Commit**

```bash
git add web/app/api/backtest/route.ts
git commit -m "feat(s4): POST /api/backtest route (lookup, validate, run + chain recompute)"
```

---

### Task 5: `BacktestButton` + page wiring + runtime verify

**Files:**
- Create: `web/components/backtest-button.tsx`
- Modify: `web/app/strategy/[id]/page.tsx`

- [ ] **Step 1: Create the client button**

`web/components/backtest-button.tsx`:

```tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export function BacktestButton({ strategyId }: { strategyId: string }) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onClick() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/backtest", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ id: strategyId }),
      });
      const data = (await res.json().catch(() => ({}))) as {
        ok?: boolean;
        error?: string;
      };
      if (res.ok && data.ok) {
        router.refresh();
      } else {
        setError(data.error ?? `Backtest failed (${res.status})`);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Network error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <button
        onClick={onClick}
        disabled={loading}
        className="rounded-md border px-3 py-1.5 text-sm font-medium hover:bg-accent disabled:opacity-50"
      >
        {loading ? "Running backtest… (1–3 min)" : "▶ Run Backtest"}
      </button>
      {error && <span className="text-sm text-red-500">{error}</span>}
    </div>
  );
}
```

- [ ] **Step 2: Wire into the strategy-detail header**

Edit `web/app/strategy/[id]/page.tsx`. Add the import (with the other component imports):

```tsx
import { BacktestButton } from "@/components/backtest-button";
```

Replace the existing header block:

```tsx
      <div>
        <h1 className="text-2xl font-bold">{s.name}</h1>
        <p className="text-sm text-muted-foreground">{s.type} · {s.status}</p>
      </div>
```

with:

```tsx
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold">{s.name}</h1>
          <p className="text-sm text-muted-foreground">{s.type} · {s.status}</p>
        </div>
        {s.backtest && <BacktestButton strategyId={s.id} />}
      </div>
```

Leave the back-link, `KpiStrip`, sections, and `<StrategySection/>` unchanged.

- [ ] **Step 3: Typecheck + build**

Run: `cd web && npx tsc --noEmit` then `npm run build`
Expected: both clean.

- [ ] **Step 4: Runtime verify**

Build, then start the prod server on a free port (e.g. 3012) via the Bash tool's `run_in_background` (NOT `&`), cwd `web/`, with `python` on PATH (`DATA_DIR=".."` from `web/.env.local`). Wait for boot, then:

```bash
# Button present for a configured strategy, absent for pead:
curl -s localhost:3012/strategy/momentum_edge | grep -c "Run Backtest"
curl -s localhost:3012/strategy/pead | grep -c "Run Backtest"
# Validation paths (no real run triggered):
curl -s -X POST localhost:3012/api/backtest -H "content-type: application/json" -d '{"id":"pead"}'        # expect 422 body
curl -s -X POST localhost:3012/api/backtest -H "content-type: application/json" -d '{"id":"nope"}'        # expect 404 body
curl -s -X POST localhost:3012/api/backtest -H "content-type: application/json" -d '{}'                   # expect 400 body
# Unaffected pages:
curl -s -o /dev/null -w "%{http_code}\n" localhost:3012/leaderboard
curl -s -o /dev/null -w "%{http_code}\n" localhost:3012/
```

Expected: `momentum_edge` grep ≥ 1, `pead` grep = 0; the pead POST returns `{"ok":false,"error":"backtest not configured for this strategy"}` (422), unknown id → `{"ok":false,"error":"unknown strategy"}` (404), empty body → `{"ok":false,"error":"missing id"}` (400); `/leaderboard` and `/` return 200.

Optionally (heavier, may take minutes / need data prerequisites): `curl -s -X POST … -d '{"id":"momentum_edge"}'` should eventually return `{"ok":true,...}` and refresh the strategy's CSVs + `kpis_updated`. If the script fails for environment reasons (missing data, long run) unrelated to the wiring, **report it — do not modify the scripts**. The deterministic gates are the button-presence + 400/404/422 validation checks above. Stop the server when done; leave none running.

- [ ] **Step 5: Full suite**

Run: `cd web && npm run test`
Expected: PASS — 101.

- [ ] **Step 6: Commit**

```bash
git add web/components/backtest-button.tsx web/app/strategy/[id]/page.tsx
git commit -m "feat(s4): Run Backtest button on strategy detail (configured strategies only)"
```

---

## Self-Review

**Spec coverage:**
- Declarative `backtest` argv in index + loader `Strategy.backtest` + mapStrategy → Task 1. ✓
- Populate momentum_edge + ipo_edge, leave pead/monthly unset → Task 1 Step 5. ✓
- Shared `job-lock` (tryAcquire/release/isHeld) + recompute route refactor → Task 2. ✓
- `resolveBacktest` (resolve + validate: empty/absolute/`..`/non-`.py`/shell-meta) → Task 3. ✓
- `POST /api/backtest`: body id (400), getStrategy (404), no field (422), lock (409), run backtest (600s) → chain recompute (120s), release in finally → Task 4. ✓
- Request supplies only id; argv from trusted index; array args, no shell → Tasks 3-4 (security). ✓
- `BacktestButton` mirrors recompute-button; rendered only when `s.backtest` set → Task 5. ✓
- Tests: resolveBacktest + job-lock (vitest); runtime button-presence + 400/404/422 + 409 → Tasks 2-3 + Task 5. ✓
- Verification: tsc/build, runtime, other pages 200 → Task 4-5 steps. ✓

**Placeholder scan:** No TBD/TODO; every code step shows full code. The optional heavy runtime backtest is explicitly marked optional with deterministic gates called out separately — not a vague instruction.

**Type consistency:** `resolveBacktest(argv: string[] | null, repoRoot: string, env: {PYTHON_BIN?: string})` identical in Task 3 def and Task 4 call. `Strategy.backtest: string[] | null` (Task 1) consumed by Task 4 (`strategy.backtest`) and Task 5 (`s.backtest`). `tryAcquire`/`release`/`isHeld` (Task 2) used in Tasks 2 & 4. `runRecompute`/`SpawnedChild` reused from slice 9 with matching signatures. `BacktestButton({ strategyId })` (Task 5) matches its call site. ✓
