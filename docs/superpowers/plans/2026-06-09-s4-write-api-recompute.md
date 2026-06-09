# Local Write-API Recompute Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A "Recompute" button in the Next.js leaderboard triggers `core.leaderboard.refresh_all` via a local Route Handler that spawns Python, then live-refreshes the ranks.

**Architecture:** Thin Python CLI entry (`python -m core.leaderboard`) → pure testable helpers in `web/lib/recompute.ts` (env resolution + subprocess→HTTP-status mapping with an injectable spawn) → thin `POST /api/recompute` Route Handler (module-level in-flight lock + real `child_process.spawn` + `NextResponse`) → `"use client"` `RecomputeButton` that POSTs and calls `router.refresh()`.

**Tech Stack:** Python 3 (pytest), Next.js 16 Route Handler + client component, TypeScript, `node:child_process`, Vitest.

**Spec:** `docs/superpowers/specs/2026-06-09-s4-write-api-recompute-design.md`

**Grounding facts:**
- `core/leaderboard.py` exports `refresh_all(index_path="strategies_index.json", benchmark_loader=None)`; reads the index, recomputes KPIs+rank, atomic-writes. Uses `from core.kpis import …` → must run as a module (`python -m core.leaderboard`), cwd = repo root.
- `tests/test_leaderboard.py` already imports `from core import leaderboard as LB` and has helpers `_mk(tmp_path, sid, eq_vals, trades=None)` (writes an equity CSV + returns an index entry dict) and `_make_equity(n, drift, vol, seed=42)`. Run: `pytest tests/test_leaderboard.py -v` from repo root.
- Web tests live in `web/tests/`, run via `cd web && npm run test` (vitest). The `@` alias maps to `web/` (e.g. existing `import … from "@/lib/data/strategies"`).
- Loader seam env: `DATA_DIR=".."` (relative to `web/`) → repo root. Leaderboard page (`web/app/leaderboard/page.tsx`) is `force-dynamic` RSC.
- Repo uses **2-space** TS indentation and the existing shadcn/tailwind classes.

**File structure:**
- `core/leaderboard.py` — add `import sys`, `main()`, `if __name__ == "__main__"` guard (Task 1).
- `web/lib/recompute.ts` — NEW. Pure helpers `resolveRecompute`, `runRecompute`, types `SpawnedChild`, `SpawnFn`, `RecomputeResult`. No Next or `child_process` imports → unit-testable (Tasks 2-3).
- `web/app/api/recompute/route.ts` — NEW. `POST` handler: in-flight lock + real `spawn` + `NextResponse` (Task 4).
- `web/components/recompute-button.tsx` — NEW. `"use client"` button (Task 5).
- `web/app/leaderboard/page.tsx` — wire the button into the header (Task 5).
- Tests: `tests/test_leaderboard.py` (Task 1), `web/tests/recompute.test.ts` NEW (Tasks 2-3).

---

### Task 1: Python CLI entry `main()`

**Files:**
- Modify: `core/leaderboard.py`
- Test: `tests/test_leaderboard.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_leaderboard.py` (it already imports `json`, `LB`, and defines `_mk`/`_make_equity`):

```python
def test_main_returns_0_and_writes_index(tmp_path, monkeypatch):
    a = _mk(tmp_path, "a", _make_equity(60, 0.002, 0.01))
    b = _mk(tmp_path, "b", _make_equity(60, 0.0005, 0.02))
    idx = tmp_path / "strategies_index.json"
    idx.write_text(json.dumps({"strategies": [a, b]}))
    monkeypatch.chdir(tmp_path)               # main() uses default index path = cwd/strategies_index.json
    rc = LB.main()
    assert rc == 0
    out = json.loads(idx.read_text())
    assert all("kpis_inline" in s for s in out["strategies"])
    assert any("rank" in s for s in out["strategies"])


def test_main_returns_1_when_index_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)               # no strategies_index.json present
    assert LB.main() == 1
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `pytest tests/test_leaderboard.py -v -k main`
Expected: FAIL — `AttributeError: module 'core.leaderboard' has no attribute 'main'`.

- [ ] **Step 3: Implement `main()`**

In `core/leaderboard.py`: add `import sys` to the existing imports (top of file, with the other stdlib imports). At the END of the file add:

```python
def main() -> int:
    try:
        refresh_all()
        return 0
    except Exception as e:
        print(f"recompute failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests, verify they pass**

Run: `pytest tests/test_leaderboard.py -v -k main`
Expected: PASS — both `main` tests green. Also run the full file to confirm no regressions: `pytest tests/test_leaderboard.py -v` (all pass).

- [ ] **Step 5: Commit**

```bash
git add core/leaderboard.py tests/test_leaderboard.py
git commit -m "feat(s4): core.leaderboard CLI entry (main) for recompute"
```

---

### Task 2: `resolveRecompute` env helper

**Files:**
- Create: `web/lib/recompute.ts`
- Test: `web/tests/recompute.test.ts`

- [ ] **Step 1: Write the failing test**

Create `web/tests/recompute.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import path from "node:path";
import { resolveRecompute } from "@/lib/recompute";

describe("resolveRecompute", () => {
  it("defaults bin to python and args to the module invocation", () => {
    const r = resolveRecompute({}, "/repo/web");
    expect(r.bin).toBe("python");
    expect(r.args).toEqual(["-m", "core.leaderboard"]);
  });
  it("honors PYTHON_BIN override", () => {
    expect(resolveRecompute({ PYTHON_BIN: "python3" }, "/repo/web").bin).toBe("python3");
  });
  it("resolves cwd from DATA_DIR (default '..') against the passed cwd", () => {
    expect(resolveRecompute({}, "/repo/web").cwd).toBe(path.resolve("/repo/web", ".."));
    expect(resolveRecompute({ DATA_DIR: "../data-root" }, "/repo/web").cwd).toBe(
      path.resolve("/repo/web", "../data-root"),
    );
  });
});
```

- [ ] **Step 2: Run the test, verify it fails**

Run: `cd web && npm run test -- recompute`
Expected: FAIL — cannot resolve `@/lib/recompute`.

- [ ] **Step 3: Create `web/lib/recompute.ts` with the helper + types**

```typescript
import path from "node:path";

export type RecomputeResult =
  | { ok: true; durationMs: number }
  | { ok: false; error: string };

/** Minimal shape of a spawned child that runRecompute needs (real child_process.spawn matches it). */
export interface SpawnedChild {
  stderr: { on(event: "data", listener: (chunk: unknown) => void): void };
  on(event: "exit", listener: (code: number | null) => void): void;
  on(event: "error", listener: (err: Error) => void): void;
  kill(): void;
}

export type SpawnFn = (bin: string, args: string[], opts: { cwd: string }) => SpawnedChild;

/** Resolve the command to run from the server environment. No request input is involved. */
export function resolveRecompute(
  env: NodeJS.ProcessEnv,
  cwd: string,
): { bin: string; args: string[]; cwd: string } {
  return {
    bin: env.PYTHON_BIN ?? "python",
    args: ["-m", "core.leaderboard"],
    cwd: path.resolve(cwd, env.DATA_DIR ?? ".."),
  };
}
```

- [ ] **Step 4: Run the test, verify it passes**

Run: `cd web && npm run test -- recompute`
Expected: PASS — 3 `resolveRecompute` cases green.

- [ ] **Step 5: Commit**

```bash
git add web/lib/recompute.ts web/tests/recompute.test.ts
git commit -m "feat(s4): resolveRecompute env helper for write-api"
```

---

### Task 3: `runRecompute` subprocess→status mapper

**Files:**
- Modify: `web/lib/recompute.ts` (add `runRecompute`)
- Test: `web/tests/recompute.test.ts`

- [ ] **Step 1: Write the failing tests**

Add to `web/tests/recompute.test.ts` (add `EventEmitter` import at top: `import { EventEmitter } from "node:events";`, and import `runRecompute` + types from `@/lib/recompute`):

```typescript
import { runRecompute, type SpawnedChild } from "@/lib/recompute";

function makeFakeChild() {
  const child = new EventEmitter() as EventEmitter & {
    stderr: EventEmitter;
    kill: () => void;
    killed: boolean;
  };
  child.stderr = new EventEmitter();
  child.killed = false;
  child.kill = () => {
    child.killed = true;
  };
  return child;
}

describe("runRecompute", () => {
  it("exit 0 -> 200 ok with numeric durationMs", async () => {
    const child = makeFakeChild();
    const p = runRecompute(() => child as unknown as SpawnedChild, {
      bin: "python", args: [], cwd: ".", timeoutMs: 1000,
    });
    child.emit("exit", 0); // handlers attached synchronously inside runRecompute
    const r = await p;
    expect(r.status).toBe(200);
    expect(r.body).toMatchObject({ ok: true });
    if (r.body.ok) expect(typeof r.body.durationMs).toBe("number");
  });

  it("nonzero exit -> 500 with stderr text", async () => {
    const child = makeFakeChild();
    const p = runRecompute(() => child as unknown as SpawnedChild, {
      bin: "python", args: [], cwd: ".", timeoutMs: 1000,
    });
    child.stderr.emit("data", "recompute failed: boom");
    child.emit("exit", 1);
    const r = await p;
    expect(r.status).toBe(500);
    expect(r.body).toEqual({ ok: false, error: "recompute failed: boom" });
  });

  it("timeout -> 504 and kills the child", async () => {
    const child = makeFakeChild();
    const p = runRecompute(() => child as unknown as SpawnedChild, {
      bin: "python", args: [], cwd: ".", timeoutMs: 10,
    }); // never emits exit
    const r = await p;
    expect(r.status).toBe(504);
    expect(r.body).toMatchObject({ ok: false });
    expect(child.killed).toBe(true);
  });

  it("spawn error event -> 500", async () => {
    const child = makeFakeChild();
    const p = runRecompute(() => child as unknown as SpawnedChild, {
      bin: "python", args: [], cwd: ".", timeoutMs: 1000,
    });
    child.emit("error", new Error("spawn ENOENT"));
    const r = await p;
    expect(r.status).toBe(500);
    expect(r.body).toEqual({ ok: false, error: "spawn ENOENT" });
  });

  it("throwing spawnFn -> 500", async () => {
    const r = await runRecompute(
      () => {
        throw new Error("cannot spawn");
      },
      { bin: "python", args: [], cwd: ".", timeoutMs: 1000 },
    );
    expect(r.status).toBe(500);
    expect(r.body).toEqual({ ok: false, error: "cannot spawn" });
  });
});
```

- [ ] **Step 2: Run the tests, verify they fail**

Run: `cd web && npm run test -- recompute`
Expected: FAIL — `runRecompute is not a function`.

- [ ] **Step 3: Implement `runRecompute` in `web/lib/recompute.ts`**

Append:

```typescript
const errMsg = (e: unknown): string => (e instanceof Error ? e.message : String(e));

/**
 * Run the recompute subprocess and map its outcome to an HTTP status + body.
 * spawnFn is injected so this is unit-testable without a real Python process.
 */
export function runRecompute(
  spawnFn: SpawnFn,
  opts: { bin: string; args: string[]; cwd: string; timeoutMs: number },
): Promise<{ status: number; body: RecomputeResult }> {
  return new Promise((resolve) => {
    const start = Date.now();
    let settled = false;
    let stderr = "";
    let child: SpawnedChild | undefined;

    const done = (status: number, body: RecomputeResult) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve({ status, body });
    };

    const timer = setTimeout(() => {
      try {
        child?.kill();
      } catch {
        // ignore kill failure; we're already timing out
      }
      done(504, { ok: false, error: "Recompute timed out" });
    }, opts.timeoutMs);

    try {
      child = spawnFn(opts.bin, opts.args, { cwd: opts.cwd });
    } catch (e) {
      done(500, { ok: false, error: errMsg(e) });
      return;
    }

    child.stderr.on("data", (c) => {
      stderr += String(c);
    });
    child.on("error", (e) => done(500, { ok: false, error: errMsg(e) }));
    child.on("exit", (code) => {
      if (code === 0) done(200, { ok: true, durationMs: Date.now() - start });
      else done(500, { ok: false, error: stderr.trim() || `exit ${code}` });
    });
  });
}
```

- [ ] **Step 4: Run the tests, verify they pass**

Run: `cd web && npm run test -- recompute`
Expected: PASS — all 5 `runRecompute` cases + 3 `resolveRecompute` cases green.

- [ ] **Step 5: Commit**

```bash
git add web/lib/recompute.ts web/tests/recompute.test.ts
git commit -m "feat(s4): runRecompute subprocess-to-status mapper"
```

---

### Task 4: `POST /api/recompute` Route Handler

**Files:**
- Create: `web/app/api/recompute/route.ts`

- [ ] **Step 1: Create the Route Handler**

```typescript
import { NextResponse } from "next/server";
import { spawn } from "node:child_process";
import { resolveRecompute, runRecompute, type SpawnedChild } from "@/lib/recompute";

export const dynamic = "force-dynamic";

const TIMEOUT_MS = 120_000;
let running = false; // module-level in-flight lock (single-process local server)

export async function POST() {
  if (running) {
    return NextResponse.json(
      { ok: false, error: "Recompute already running" },
      { status: 409 },
    );
  }
  running = true;
  try {
    const { bin, args, cwd } = resolveRecompute(process.env, process.cwd());
    const { status, body } = await runRecompute(
      (b, a, o) => spawn(b, a, o) as unknown as SpawnedChild,
      { bin, args, cwd, timeoutMs: TIMEOUT_MS },
    );
    return NextResponse.json(body, { status });
  } finally {
    running = false;
  }
}
```

- [ ] **Step 2: Typecheck + build**

Run: `cd web && npx tsc --noEmit` then `npm run build`
Expected: both clean. The route is recognized as an API endpoint. If Next-16 flags the handler signature, consult `web/AGENTS.md` + `node_modules/next/dist/docs/`. (A `POST()` export with no args is valid.)

- [ ] **Step 3: Run the full web test suite (no regressions)**

Run: `cd web && npm run test`
Expected: PASS — prior 91 + 8 new recompute tests = 99.

- [ ] **Step 4: Commit**

```bash
git add web/app/api/recompute/route.ts
git commit -m "feat(s4): POST /api/recompute route handler (lock + spawn)"
```

---

### Task 5: `RecomputeButton` + leaderboard wiring + runtime verify

**Files:**
- Create: `web/components/recompute-button.tsx`
- Modify: `web/app/leaderboard/page.tsx`

- [ ] **Step 1: Create the client button**

`web/components/recompute-button.tsx`:

```tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export function RecomputeButton() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onClick() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/recompute", { method: "POST" });
      const data = (await res.json().catch(() => ({}))) as {
        ok?: boolean;
        error?: string;
      };
      if (res.ok && data.ok) {
        router.refresh(); // re-pull the force-dynamic leaderboard RSC
      } else {
        setError(data.error ?? `Recompute failed (${res.status})`);
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
        {loading ? "Recomputing…" : "↻ Recompute"}
      </button>
      {error && <span className="text-sm text-red-500">{error}</span>}
    </div>
  );
}
```

- [ ] **Step 2: Wire into the leaderboard page header**

Edit `web/app/leaderboard/page.tsx`. Add the import:

```tsx
import { RecomputeButton } from "@/components/recompute-button";
```

Replace the single `<h1>` line:

```tsx
      <h1 className="mb-1 text-2xl font-bold">Strategy Leaderboard</h1>
```

with a flex header row:

```tsx
      <div className="mb-1 flex items-center justify-between">
        <h1 className="text-2xl font-bold">Strategy Leaderboard</h1>
        <RecomputeButton />
      </div>
```

Leave the subtitle `<p>` and `<LeaderboardTable>` unchanged.

- [ ] **Step 3: Typecheck + build**

Run: `cd web && npx tsc --noEmit` then `npm run build`
Expected: both clean.

- [ ] **Step 4: Runtime verify**

Build, then start the prod server on a free port via the Bash tool's `run_in_background` (NOT `&`). Ensure the server's cwd is `web/` and `DATA_DIR=".."` is set (it is, via `web/.env.local`), and that `python` is on PATH (or set `PYTHON_BIN`). Wait for boot, then:

```bash
# Button markup present on the leaderboard:
curl -s localhost:3011/leaderboard | grep -c "Recompute"
# The write endpoint runs the recompute and returns ok:true:
curl -s -X POST localhost:3011/api/recompute
# An immediate second POST while the first may still hold the lock returns 409 (race-dependent;
# the deterministic check is that a single POST returns {"ok":true,...}):
# Unaffected pages still serve:
curl -s -o /dev/null -w "%{http_code}\n" localhost:3011/
curl -s -o /dev/null -w "%{http_code}\n" localhost:3011/strategy/monthly_rotation
```

Expected: leaderboard grep ≥ 1; `POST /api/recompute` returns `{"ok":true,"durationMs":<n>}`; `strategies_index.json` at repo root has a refreshed `kpis_updated` timestamp afterward (check its mtime or the field); `/` and `/strategy/monthly_rotation` return `200`. Stop the server when done — leave none running.

Note: the live `router.refresh()` re-render is interactive (browser JS); curl confirms the endpoint works and the button renders, which is sufficient evidence for this slice. If a browser is available, optionally confirm the rank cells update in place after clicking.

- [ ] **Step 5: Run full test suite**

Run: `cd web && npm run test`
Expected: PASS — 99 tests.

- [ ] **Step 6: Commit**

```bash
git add web/components/recompute-button.tsx web/app/leaderboard/page.tsx
git commit -m "feat(s4): Recompute button wired into leaderboard header"
```

---

## Self-Review

**Spec coverage:**
- Python CLI entry `main()` (module mode, exit 0/1, stderr) → Task 1. ✓
- Pure helpers extracted + unit-testable with injected spawn → Tasks 2-3 (in `lib/recompute.ts`, a deliberate refinement of the spec's "extract two helpers" — cleaner than living in `route.ts` because vitest imports it with zero Next/`child_process` deps). ✓
- `resolveRecompute` env resolution (PYTHON_BIN default, DATA_DIR cwd, fixed args) → Task 2. ✓
- `runRecompute` status mapping (200/500/504) + in-flight handled at route → Task 3 + Task 4. ✓
- Route Handler: POST only, module-level lock → 409, real `spawn` (array args, no shell), 120 s timeout, `NextResponse` → Task 4. ✓
- Client button: POST, loading/disabled, `router.refresh()` on ok, inline error → Task 5. ✓
- Leaderboard header wiring → Task 5. ✓
- pytest (`main` success + missing-index) → Task 1; vitest (resolve + run cases) → Tasks 2-3. ✓
- Security: fixed command, no user input, no shell, local-only → realized in Task 4 (array args, no `shell:true`) + Task 2 (env not request). ✓
- Verification (pytest, vitest, tsc/build, runtime, other pages 200) → Task 1 / Tasks 2-3 / Task 4-5 steps. ✓

**Placeholder scan:** No TBD/TODO. Every code step shows full code. The runtime second-POST/409 check is explicitly noted as race-dependent with the deterministic assertion called out — not a vague instruction.

**Type consistency:** `RecomputeResult`, `SpawnedChild`, `SpawnFn` defined in Task 2, used identically in Tasks 3-4. `resolveRecompute(env, cwd)` and `runRecompute(spawnFn, {bin,args,cwd,timeoutMs})` signatures match across tasks and tests. `RecomputeButton` named export imported in Task 5. `main()` referenced by Task 1 tests matches the implementation. ✓
