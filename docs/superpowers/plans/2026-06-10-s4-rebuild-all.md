# Rebuild All Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a one-click leaderboard "Rebuild All" action that serially re-runs every strategy's wired `backtest` argv (best-effort), then recomputes KPIs + rank.

**Architecture:** A pure, spawn-injected orchestrator `runRebuildAll` (mirrors the existing `runRecompute`) loops the backtests serially via `runRecompute` + `resolveBacktest`, collects ran/failed, then runs one recompute. A thin `force-dynamic` POST route builds the backtest list from the trusted index and holds the shared `job-lock`. A client button posts to it and refreshes the leaderboard.

**Tech Stack:** Next.js 16 (App Router, Route Handlers), TypeScript, Vitest, `node:child_process` (real route only).

Spec: `docs/superpowers/specs/2026-06-10-s4-rebuild-all-design.md`

---

### Task 1: `runRebuildAll` orchestrator (pure, unit-tested)

**Files:**
- Create: `web/lib/rebuild-all.ts`
- Test: `web/tests/rebuild-all.test.ts`

This is the only unit-tested unit. It imports `resolveBacktest`, `runRecompute`, `SpawnFn`, `SpawnedChild` from `@/lib/recompute` (already present — see `web/lib/recompute.ts`). No Next or `child_process` imports, so the fake-spawn pattern from `web/tests/recompute.test.ts` applies directly.

- [ ] **Step 1: Write the failing test**

Create `web/tests/rebuild-all.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import { EventEmitter } from "node:events";
import { runRebuildAll } from "@/lib/rebuild-all";
import { type SpawnFn, type SpawnedChild } from "@/lib/recompute";

type Outcome = { code: number; stderr?: string };

// Returns a SpawnFn that yields one scripted child per call (in order), each
// emitting its stderr then exit on a microtask so serial runRecompute calls settle.
// Records the script (argv[0]) of every spawn for order assertions.
function scriptedSpawn(outcomes: Outcome[]): { fn: SpawnFn; calls: string[] } {
  let i = 0;
  const calls: string[] = [];
  const fn: SpawnFn = (_bin, args) => {
    calls.push(args[0] ?? "");
    const outcome = outcomes[i++] ?? { code: 0 };
    const child = new EventEmitter() as EventEmitter & {
      stderr: EventEmitter;
      kill: () => void;
    };
    child.stderr = new EventEmitter();
    child.kill = () => {};
    queueMicrotask(() => {
      if (outcome.stderr) child.stderr.emit("data", outcome.stderr);
      child.emit("exit", outcome.code);
    });
    return child as unknown as SpawnedChild;
  };
  return { fn, calls };
}

const baseOpts = {
  repoRoot: "/repo",
  env: {},
  recompute: { bin: "python", args: ["-m", "core.leaderboard"], cwd: "/repo" },
  backtestTimeoutMs: 1000,
  recomputeTimeoutMs: 1000,
};

describe("runRebuildAll", () => {
  it("all backtests succeed -> ran has all ids, failed empty, recompute 200, ok true", async () => {
    const { fn } = scriptedSpawn([{ code: 0 }, { code: 0 }, { code: 0 }]);
    const r = await runRebuildAll(fn, {
      ...baseOpts,
      backtests: [
        { id: "a", argv: ["a.py"] },
        { id: "b", argv: ["b.py"] },
      ],
    });
    expect(r.status).toBe(200);
    expect(r.body.ran).toEqual(["a", "b"]);
    expect(r.body.failed).toEqual([]);
    expect(r.body.recompute.status).toBe(200);
    expect(r.body.ok).toBe(true);
  });

  it("runs backtests in array order, recompute last", async () => {
    const { fn, calls } = scriptedSpawn([{ code: 0 }, { code: 0 }, { code: 0 }]);
    await runRebuildAll(fn, {
      ...baseOpts,
      backtests: [
        { id: "a", argv: ["a.py"] },
        { id: "b", argv: ["b.py"] },
      ],
    });
    expect(calls).toEqual(["a.py", "b.py", "-m"]);
  });

  it("one backtest fails -> it lands in failed, others ran, recompute still runs, ok false", async () => {
    const { fn } = scriptedSpawn([
      { code: 1, stderr: "boom" },
      { code: 0 },
      { code: 0 },
    ]);
    const r = await runRebuildAll(fn, {
      ...baseOpts,
      backtests: [
        { id: "a", argv: ["a.py"] },
        { id: "b", argv: ["b.py"] },
      ],
    });
    expect(r.body.ran).toEqual(["b"]);
    expect(r.body.failed).toEqual([{ id: "a", error: "boom" }]);
    expect(r.body.recompute.status).toBe(200);
    expect(r.body.ok).toBe(false);
  });

  it("unsafe argv -> resolveBacktest throw captured as failed, loop continues, no spawn for it", async () => {
    const { fn, calls } = scriptedSpawn([{ code: 0 }, { code: 0 }]);
    const r = await runRebuildAll(fn, {
      ...baseOpts,
      backtests: [
        { id: "bad", argv: ["../evil.py"] },
        { id: "b", argv: ["b.py"] },
      ],
    });
    expect(r.body.ran).toEqual(["b"]);
    expect(r.body.failed).toHaveLength(1);
    expect(r.body.failed[0].id).toBe("bad");
    expect(calls).toEqual(["b.py", "-m"]); // bad never spawned
    expect(r.body.ok).toBe(false);
  });

  it("recompute fails -> recompute.status reflects it, ok false", async () => {
    const { fn } = scriptedSpawn([{ code: 0 }, { code: 1, stderr: "rc boom" }]);
    const r = await runRebuildAll(fn, {
      ...baseOpts,
      backtests: [{ id: "a", argv: ["a.py"] }],
    });
    expect(r.body.ran).toEqual(["a"]);
    expect(r.body.recompute.status).toBe(500);
    expect(r.body.recompute.error).toBe("rc boom");
    expect(r.body.ok).toBe(false);
  });

  it("empty backtests -> recompute still runs, ran/failed empty, ok true", async () => {
    const { fn, calls } = scriptedSpawn([{ code: 0 }]);
    const r = await runRebuildAll(fn, { ...baseOpts, backtests: [] });
    expect(r.body.ran).toEqual([]);
    expect(r.body.failed).toEqual([]);
    expect(r.body.recompute.status).toBe(200);
    expect(r.body.ok).toBe(true);
    expect(calls).toEqual(["-m"]); // only recompute
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npx vitest run tests/rebuild-all.test.ts`
Expected: FAIL — `Failed to resolve import "@/lib/rebuild-all"` (module not created yet).

- [ ] **Step 3: Write minimal implementation**

Create `web/lib/rebuild-all.ts`:

```typescript
import { resolveBacktest, runRecompute, type SpawnFn } from "@/lib/recompute";

export type RebuildBacktest = { id: string; argv: string[] };

export interface RebuildAllBody {
  ok: boolean;
  ran: string[];
  failed: { id: string; error: string }[];
  recompute: { status: number; error?: string };
}

const errMsg = (e: unknown): string => (e instanceof Error ? e.message : String(e));

/**
 * Serially run each backtest (best-effort), then recompute once.
 * spawnFn is injected so this is unit-testable without real Python processes.
 * argv comes only from the trusted server-side index — never request input.
 */
export async function runRebuildAll(
  spawnFn: SpawnFn,
  opts: {
    backtests: RebuildBacktest[];
    repoRoot: string;
    env: { PYTHON_BIN?: string };
    recompute: { bin: string; args: string[]; cwd: string };
    backtestTimeoutMs: number;
    recomputeTimeoutMs: number;
  },
): Promise<{ status: number; body: RebuildAllBody }> {
  const ran: string[] = [];
  const failed: { id: string; error: string }[] = [];

  for (const bt of opts.backtests) {
    let cmd: { bin: string; args: string[]; cwd: string };
    try {
      cmd = resolveBacktest(bt.argv, opts.repoRoot, opts.env);
    } catch (e) {
      failed.push({ id: bt.id, error: errMsg(e) });
      continue;
    }
    const run = await runRecompute(spawnFn, {
      ...cmd,
      timeoutMs: opts.backtestTimeoutMs,
      label: `Backtest ${bt.id}`,
    });
    if (run.status === 200) {
      ran.push(bt.id);
    } else {
      failed.push({ id: bt.id, error: run.body.ok ? "" : run.body.error });
    }
  }

  const rc = await runRecompute(spawnFn, {
    ...opts.recompute,
    timeoutMs: opts.recomputeTimeoutMs,
    label: "Recompute",
  });
  const recompute =
    rc.status === 200
      ? { status: rc.status }
      : { status: rc.status, error: rc.body.ok ? undefined : rc.body.error };

  const ok = failed.length === 0 && recompute.status === 200;
  return { status: 200, body: { ok, ran, failed, recompute } };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && npx vitest run tests/rebuild-all.test.ts`
Expected: PASS — 6 tests.

- [ ] **Step 5: Run full suite + typecheck (no regressions)**

Run: `cd web && npx vitest run && npx tsc --noEmit`
Expected: all prior tests still pass (121 + 6 = 127), tsc clean.

- [ ] **Step 6: Commit**

```bash
git add web/lib/rebuild-all.ts web/tests/rebuild-all.test.ts
git commit -m "feat(s4): runRebuildAll orchestrator (serial backtests + recompute, best-effort)"
```

---

### Task 2: `POST /api/rebuild-all` route

**Files:**
- Create: `web/app/api/rebuild-all/route.ts`

No unit test (Next Route Handler; verified at runtime in Task 3). Mirrors `web/app/api/backtest/route.ts` and `web/app/api/recompute/route.ts` exactly (lock, force-dynamic, real-spawn wrapper, release-in-finally).

- [ ] **Step 1: Write the route**

Create `web/app/api/rebuild-all/route.ts`:

```typescript
import { NextResponse } from "next/server";
import { spawn } from "node:child_process";
import path from "node:path";
import { resolveRecompute, type SpawnedChild } from "@/lib/recompute";
import { runRebuildAll } from "@/lib/rebuild-all";
import { getStrategies } from "@/lib/data/strategies";
import { tryAcquire, release } from "@/lib/job-lock";

export const dynamic = "force-dynamic";

const BACKTEST_TIMEOUT_MS = 600_000;
const RECOMPUTE_TIMEOUT_MS = 120_000;

const spawnChild = (b: string, a: string[], o: { cwd: string }) =>
  spawn(b, a, o) as unknown as SpawnedChild;

export async function POST() {
  if (!tryAcquire()) {
    return NextResponse.json(
      { ok: false, error: "A job is already running" },
      { status: 409 },
    );
  }
  try {
    const repoRoot = path.resolve(process.cwd(), process.env.DATA_DIR ?? "..");
    const strategies = await getStrategies();
    const backtests = strategies
      .filter((s) => s.backtest)
      .map((s) => ({ id: s.id, argv: s.backtest as string[] }));
    const recompute = resolveRecompute(process.env, process.cwd());

    const result = await runRebuildAll(spawnChild, {
      backtests,
      repoRoot,
      env: { PYTHON_BIN: process.env.PYTHON_BIN },
      recompute,
      backtestTimeoutMs: BACKTEST_TIMEOUT_MS,
      recomputeTimeoutMs: RECOMPUTE_TIMEOUT_MS,
    });
    return NextResponse.json(result.body, { status: result.status });
  } finally {
    release();
  }
}
```

- [ ] **Step 2: Typecheck + build**

Run: `cd web && npx tsc --noEmit && npm run build`
Expected: tsc clean; build lists `ƒ /api/rebuild-all` among routes.

- [ ] **Step 3: Commit**

```bash
git add web/app/api/rebuild-all/route.ts
git commit -m "feat(s4): POST /api/rebuild-all (lock, dynamic strategy list, best-effort)"
```

---

### Task 3: `RebuildAllButton` component + leaderboard wiring + runtime verify

**Files:**
- Create: `web/components/rebuild-all-button.tsx`
- Modify: `web/app/leaderboard/page.tsx` (import + render beside `RecomputeButton`, line ~27)

Mirrors `web/components/backtest-button.tsx` (use client, fetch, loading/error states, `router.refresh()`).

- [ ] **Step 1: Write the component**

Create `web/components/rebuild-all-button.tsx`:

```typescript
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

interface RebuildAllResponse {
  ok?: boolean;
  ran?: string[];
  failed?: { id: string; error: string }[];
  error?: string;
}

export function RebuildAllButton() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [summary, setSummary] = useState<string | null>(null);
  const [isError, setIsError] = useState(false);

  async function onClick() {
    setLoading(true);
    setSummary(null);
    setIsError(false);
    try {
      const res = await fetch("/api/rebuild-all", { method: "POST" });
      const data = (await res.json().catch(() => ({}))) as RebuildAllResponse;
      if (res.status === 409) {
        setIsError(true);
        setSummary(data.error ?? "A job is already running");
        return;
      }
      router.refresh();
      const ran = data.ran?.length ?? 0;
      const failed = data.failed ?? [];
      if (failed.length > 0) {
        setIsError(true);
        setSummary(`Rebuilt ${ran} · failed: ${failed.map((f) => f.id).join(", ")}`);
      } else {
        setSummary(`Rebuilt ${ran}`);
      }
    } catch (e) {
      setIsError(true);
      setSummary(e instanceof Error ? e.message : "Network error");
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
        {loading ? "Rebuilding all… (several min)" : "⟳ Rebuild All"}
      </button>
      {summary && (
        <span className={`text-sm ${isError ? "text-red-500" : "text-muted-foreground"}`}>
          {summary}
        </span>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Wire into the leaderboard header**

In `web/app/leaderboard/page.tsx`, add the import after the `RecomputeButton` import (line 4):

```typescript
import { RebuildAllButton } from "@/components/rebuild-all-button";
```

And render it right after `<RecomputeButton />` (line ~27):

```tsx
          <RecomputeButton />
          <RebuildAllButton />
```

- [ ] **Step 3: Typecheck + build**

Run: `cd web && npx tsc --noEmit && npm run build`
Expected: tsc clean; build succeeds.

- [ ] **Step 4: Runtime verify (button renders + lock)**

Run (isolated port, do not collide with other dev servers):

```bash
cd web && (npx next start -p 3021 > /tmp/rebuild_verify.log 2>&1 &) ; sleep 6
curl -s http://localhost:3021/leaderboard -o /tmp/lb.html
grep -c "Rebuild All" /tmp/lb.html   # expect 1
# lock: fire rebuild-all twice concurrently -> one 200, one 409
( curl -s -w " HTTP:%{http_code}\n" -X POST http://localhost:3021/api/rebuild-all &
  curl -s -w " HTTP:%{http_code}\n" -X POST http://localhost:3021/api/rebuild-all & wait )
```

Expected: leaderboard HTML contains the `⟳ Rebuild All` button (grep = 1). Concurrent POSTs → one `{"ok":...,"ran":[...]}` HTTP 200 (full rebuild, may take minutes), one `{"ok":false,"error":"A job is already running"}` HTTP 409. Stop the server afterward (Windows: `Get-NetTCPConnection -LocalPort 3021 -State Listen | Stop-Process -Id { OwningProcess } -Force`).

Note: a successful POST regenerates all strategy CSVs + `strategies_index.json`. Either restore those (`git checkout -- <files>`) or commit them separately as a data refresh — do not bundle data churn into the feature commit.

- [ ] **Step 5: Commit (code only)**

```bash
git add web/components/rebuild-all-button.tsx web/app/leaderboard/page.tsx
git commit -m "feat(s4): Rebuild All button wired into leaderboard header"
```

---

## Self-Review

**Spec coverage:**
- `runRebuildAll` serial + best-effort + always-recompute + summary shape → Task 1. ✓
- Per-step timeouts (600s/120s) → Task 2 constants passed through. ✓
- Shared job-lock, acquire-once/release-finally → Task 2. ✓
- Dynamic strategy set (filter `backtest`) → Task 2. ✓
- Button fire-and-wait + `router.refresh()` + summary → Task 3. ✓
- Security (no request input to spawn; argv from index; `resolveBacktest` guards) → Task 2 passes only index-derived argv; `runRebuildAll` calls `resolveBacktest` per backtest (Task 1). ✓
- Tests enumerated in spec → Task 1 covers all six. ✓

**Placeholder scan:** none — all code blocks complete, exact commands given.

**Type consistency:** `RebuildBacktest {id, argv}`, `RebuildAllBody {ok, ran, failed, recompute}` defined in Task 1 and consumed by the route (Task 2) and component (Task 3). `runRecompute`/`resolveBacktest`/`resolveRecompute`/`SpawnFn`/`SpawnedChild` match `web/lib/recompute.ts`. `getStrategies` + `Strategy.backtest: string[]|null` match the existing loader. ✓
