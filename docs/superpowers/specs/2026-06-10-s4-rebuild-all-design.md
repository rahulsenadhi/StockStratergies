# S4 Rebuild All — Design

**Date:** 2026-06-10
**Status:** Approved (brainstorm)
**Depends on:** slice-9 (Recompute), slice-10 (Run Backtest), `web/lib/job-lock.ts`, `web/lib/recompute.ts`

## Goal

One-click leaderboard action that regenerates **every** strategy's backtest data,
then recomputes KPIs + rank. Distinct from the existing fast KPI-only **Recompute**
(slice-9) and the per-strategy **Run Backtest** (slice-10). Build it without
polluting either of those fast paths.

## Decisions (settled in brainstorm)

- **Execution:** serial — run backtests one at a time, then a single recompute.
  Avoids 4x CPU/memory contention (`momentum_edge` loads ~963 tickers). Total time
  = sum of backtests (~minutes); acceptable for a rarely-clicked deliberate action.
- **Partial failure:** best-effort — on a backtest failure (nonzero exit, timeout,
  or unsafe-argv reject) record `{id, error}` and continue; run recompute regardless.
  Matches `refresh_all`'s per-strategy isolation (it already sets `kpis_error`).
- **Timeout:** per-step — each backtest reuses slice-10's 600s, recompute 120s, via
  `runRecompute`. No single aggregate timeout.
- **Lock:** the same global `job-lock`. Rebuild All acquires once, holds through all
  backtests + recompute, releases in `finally`. Per-strategy Run Backtest / Recompute
  return 409 while it runs, and vice versa.
- **Strategy set:** dynamic — every strategy in the index with a `backtest` field
  (currently all 4). No hardcoding.
- **Feedback:** fire-and-wait (SSE deferred). Button disables + shows progress text,
  then `router.refresh()` + a summary line.

## Architecture

### `web/lib/rebuild-all.ts` (new, pure / injectable-spawn)

Mirrors `runRecompute`'s testable design (spawn injected, no Next/`child_process`
imports).

```
type RebuildBacktest = { id: string; argv: string[] };

type RebuildResult = {
  status: number;          // always 200 (best-effort)
  body: {
    ok: boolean;           // failed.length === 0 && recompute.status === 200
    ran: string[];         // ids whose backtest exited 200
    failed: { id: string; error: string }[];
    recompute: { status: number; error?: string };
  };
};

async function runRebuildAll(
  spawnFn: SpawnFn,
  opts: {
    backtests: RebuildBacktest[];
    repoRoot: string;
    env: { PYTHON_BIN?: string };
    recompute: { bin: string; args: string[]; cwd: string };
    backtestTimeoutMs: number;
    recomputeTimeoutMs: number;
  },
): Promise<RebuildResult>;
```

Behavior:
1. For each `backtest` **in order**: `resolveBacktest(argv, repoRoot, env)` then
   `runRecompute(spawnFn, { ...bt, timeoutMs: backtestTimeoutMs, label: \`Backtest ${id}\` })`.
   - `status === 200` → push `id` to `ran`.
   - non-200 → push `{ id, error: <body.error or status> }` to `failed`, continue.
   - `resolveBacktest` throws (unsafe argv) → push `{ id, error }` to `failed`, continue.
2. After the loop, **always** `runRecompute(spawnFn, { ...recompute, timeoutMs:
   recomputeTimeoutMs, label: "Recompute" })`.
3. Return `{ status: 200, body: { ok, ran, failed, recompute: { status, error? } } }`.

Empty `backtests` → `ran: []`, `failed: []`, recompute still runs, `ok` reflects it.

### `web/app/api/rebuild-all/route.ts` (new)

`POST`, `export const dynamic = "force-dynamic"`. No request body needed.
1. `tryAcquire()` → false → 409 `{ ok:false, error:"A job is already running" }`.
2. `try`:
   - `repoRoot = path.resolve(process.cwd(), process.env.DATA_DIR ?? "..")`.
   - `backtests = (await getStrategies()).filter(s => s.backtest).map(s => ({ id: s.id, argv: s.backtest! }))`.
   - `recompute = resolveRecompute(process.env, process.cwd())`.
   - `const result = await runRebuildAll(realSpawn, { backtests, repoRoot, env:{PYTHON_BIN}, recompute, backtestTimeoutMs:600_000, recomputeTimeoutMs:120_000 })`.
   - return `NextResponse.json(result.body, { status: result.status })`.
3. `finally { release(); }`.

`realSpawn` = same `spawn(b,a,o) as unknown as SpawnedChild` wrapper as the other routes.

### `web/components/rebuild-all-button.tsx` (new, "use client")

Same shape as `backtest-button.tsx`:
- `POST /api/rebuild-all`, no body.
- `loading` → button disabled, text `"Rebuilding all… (several min)"`; idle → `"⟳ Rebuild All"`.
- On response: `router.refresh()`; render a summary span — `"Rebuilt {ran.length}"` plus,
  if `failed.length`, `" · failed: {failed ids joined}"` in red. Network error → red span.

### Wiring

Leaderboard header (where `RecomputeButton` + "+ New strategy" live) gains
`<RebuildAllButton />` beside them. No loader or other page changes.

## Data flow

```
click → POST /api/rebuild-all
      → acquire lock
      → getStrategies() filter backtest
      → runRebuildAll: [backtest A → … → backtest N] (serial, best-effort) → recompute
      → release lock
      → { ok, ran, failed, recompute }
client→ router.refresh() (re-pulls force-dynamic leaderboard RSC) + summary span
```

## Error handling

- Lock busy → 409, no work done.
- Per-backtest failure → captured in `failed[]`, loop continues, recompute still runs.
- Recompute failure → surfaced in `body.recompute`, `ok=false`.
- Unsafe argv (shouldn't happen — trusted index) → `resolveBacktest` throw caught as a
  `failed[]` entry, not a 500.
- `release()` always runs in `finally`.

## Security

Identical posture to slice-10. Request carries **no** input that reaches a spawn
(POST has no body). `argv` comes only from the server-side index; `resolveBacktest`
guards (no shell-meta / `..` / absolute / non-`.py`) still apply per backtest; array
args, no `shell:true`. Injection structurally impossible.

## Testing (TDD)

Unit-test `runRebuildAll` with a fake `spawnFn` (mirrors existing `runRecompute`
tests in `web/`):
- serial order — backtests invoked in array order, recompute last.
- all succeed → `ran` = all ids, `failed` = [], `ok` true.
- one backtest non-200 → it lands in `failed`, others in `ran`, recompute still ran, `ok` false.
- `resolveBacktest` throw (unsafe argv) → `failed` entry, loop continues.
- recompute non-200 → `body.recompute.status` reflects it, `ok` false.
- empty `backtests` → recompute still runs, `ran`/`failed` empty.

No new Python. Route + component verified at runtime (build + click) like prior slices.

## Out of scope (YAGNI)

- SSE / streaming progress (whole-platform deferred item).
- Parallel execution.
- Cancel mid-rebuild.
- Per-strategy selection (it's all-or-nothing; use Run Backtest for one).
