# S4 — Local Write-API Sidecar: Recompute (slice 9)

**Date:** 2026-06-09
**Slice:** S4 frontend (slice 9) — first write action
**Status:** Design approved, ready for plan

## Goal

Add the first **write** path to the local-first Next.js app: a "Recompute" button
that triggers `core.leaderboard.refresh_all` (recomputes canonical KPIs + composite
rank for every strategy and rewrites `strategies_index.json`), then refreshes the UI
so new ranks/KPIs appear without a manual reload. This proves the local backend
mechanism; **Run-Backtest** and the **new-strategy wizard** are deferred to later
slices that reuse the same mechanism.

This deliberately breaks the prior read-only invariant, in a contained way (see
Security).

## Background / current state

- `core/leaderboard.py` exports `refresh_all(index_path="strategies_index.json",
  benchmark_loader=None) -> list[dict]`: reads the index, recomputes the 10 canonical
  KPIs per strategy via `compute_kpis`, ranks the cohort via `rank_strategies`,
  isolates any per-strategy failure into `kpis_error` (never aborts the batch), and
  **atomically** writes the index (`tmp` file + `os.replace`). It uses
  `from core.kpis import …` / `from core.ranking import …`, so it must run as a
  **module** (`python -m core.leaderboard`), not as a loose script.
- `tests/test_leaderboard.py` already tests `refresh_all` with `tmp_path` fixtures;
  pytest is configured (`pyproject.toml`).
- The web app (`web/`) is read-only today. Loader seam: `lib/data/strategies.ts`,
  `DATA_DIR=".."` (relative to `web/`) → repo root. Pages are `force-dynamic` RSC,
  reading files at request time — so a client-side refresh re-pulls fresh data.
- Leaderboard page (`web/app/leaderboard/page.tsx`) is a simple RSC: title +
  subtitle + `<LeaderboardTable rows={rows} />`.

## Architecture

Three units plus a thin Python entry point.

### 1. Python CLI entry — `core/leaderboard.py`

Add a `main()` and module guard (add `import sys` to the existing imports):

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

- Invoked as `python -m core.leaderboard` with **cwd = repo root** → `refresh_all`'s
  default `index_path="strategies_index.json"` resolves to the repo-root index.
- `refresh_all` already isolates per-strategy errors, so `main` returns 1 only on a
  catastrophic error (missing/unreadable index, import failure, etc.).
- No change to `refresh_all`'s signature or behavior.

### 2. Route Handler — `web/app/api/recompute/route.ts`

`POST` handler (no `GET`). Responsibilities:

- **In-flight lock:** a module-level boolean (`let running = false`). If already
  running, respond `409 { ok: false, error: "Recompute already running" }`. Set on
  entry, clear in a `finally`.
- **Spawn:** `spawn(bin, ["-m", "core.leaderboard"], { cwd: repoRoot })` using
  `node:child_process`. **Array args, no `shell: true`** → no shell interpolation.
  - `bin = process.env.PYTHON_BIN ?? "python"`
  - `repoRoot = path.resolve(process.cwd(), process.env.DATA_DIR ?? "..")`
- **Timeout:** 120 000 ms. On timeout, `child.kill()` and respond
  `504 { ok: false, error: "Recompute timed out" }`.
- **Result mapping:** collect `stderr`. Exit code `0` → `200 { ok: true, durationMs }`.
  Nonzero → `500 { ok: false, error: <stderr or "exit N"> }`. Spawn error (e.g. python
  not found) → `500 { ok: false, error }`.

**Testable seams** (extracted so vitest needs no real Python):

```ts
// pure: resolve what to run from the environment
export function resolveRecompute(env: NodeJS.ProcessEnv, cwd: string):
  { bin: string; args: string[]; cwd: string } {
  return {
    bin: env.PYTHON_BIN ?? "python",
    args: ["-m", "core.leaderboard"],
    cwd: path.resolve(cwd, env.DATA_DIR ?? ".."),
  };
}

// status mapping; spawnFn injected for tests. Returns the response shape, not a Response.
export async function runRecompute(
  spawnFn: SpawnFn,
  opts: { bin: string; args: string[]; cwd: string; timeoutMs: number },
): Promise<{ status: number; body: RecomputeResult }> { … }
```

`SpawnFn` is a minimal interface matching the parts of `child_process.spawn` used
(returns an object with `stderr` (an event emitter), `on("exit"|"error")`, `kill()`).
The real handler passes `child_process.spawn`; tests pass a fake that emits chosen
exit codes / stderr / errors / never-exits (for timeout). The in-flight lock lives in
the route module and wraps `runRecompute`.

`RecomputeResult = { ok: true; durationMs: number } | { ok: false; error: string }`.

### 3. Client button — `web/components/recompute-button.tsx`

`"use client"` component:

- A button ("↻ Recompute"). On click: set `loading`, `fetch("/api/recompute",
  { method: "POST" })`, parse JSON.
- On `ok`: call `router.refresh()` (`next/navigation`) — re-pulls the `force-dynamic`
  leaderboard RSC so new ranks/KPIs render in place. Clear loading.
- On non-ok (incl. 409/500/504) or network error: show an inline error message
  (`text-sm text-red-500`) and clear loading. Disable the button while `loading`.
- No props needed.

### Wiring — `web/app/leaderboard/page.tsx`

Wrap the title in a flex header row and place `<RecomputeButton />` on the right:

```tsx
<div className="mb-1 flex items-center justify-between">
  <h1 className="text-2xl font-bold">Strategy Leaderboard</h1>
  <RecomputeButton />
</div>
```

Import `RecomputeButton`. No other page changes; subtitle + table unchanged.

## Data flow

Click → `POST /api/recompute` → handler acquires lock → spawns
`python -m core.leaderboard` (cwd repo root) → `refresh_all` rewrites
`strategies_index.json` atomically → handler returns `{ok:true}` → client
`router.refresh()` → leaderboard RSC re-reads the index via the loader seam → new
ranks render. Lock released in `finally`.

## Error handling

- Per-strategy KPI failures are already swallowed by `refresh_all` into `kpis_error`
  (the loader maps that to null KPIs) — recompute still succeeds.
- Catastrophic Python failure → exit 1 + stderr → handler `500` → button shows the
  stderr text.
- Concurrent click → `409` → button shows "already running".
- Timeout → `504` → button shows "timed out".
- Python binary missing → spawn `error` → `500` with the spawn error message.

## Testing

**pytest** (extend `tests/test_leaderboard.py`):
- `main()` returns `0` and writes a valid index, when invoked with cwd/`index_path`
  pointing at a valid fixture index (use the existing `_mk` helpers + `monkeypatch`
  to run `refresh_all` against a `tmp_path` index, or call a small seam). Assert the
  written index has `rank`/`kpis_inline` populated.
- `main()` returns `1` when the index is missing (point `refresh_all` at a
  nonexistent path via `monkeypatch.chdir(tmp_path)` with no index present).

**vitest** (`web/tests/recompute.test.ts`, new):
- `resolveRecompute`: default `bin === "python"`; `PYTHON_BIN` override respected;
  `cwd` resolves `DATA_DIR` (default `".."`) against the passed cwd; `args` are
  `["-m","core.leaderboard"]`.
- `runRecompute` with a fake spawn:
  - exit 0 → `{ status: 200, body: { ok: true } }` (durationMs is a number ≥ 0).
  - exit 1 with stderr → `{ status: 500, body: { ok: false, error: <stderr> } }`.
  - never-exits + small `timeoutMs` → `{ status: 504, body: { ok:false } }` and
    `kill()` was called.
  - spawn emits `error` → `{ status: 500, body: { ok:false } }`.

**Runtime:**
- `cd web && npm run dev` (or build + start). Click Recompute on `/leaderboard`:
  observe `strategies_index.json` mtime/`kpis_updated` change and ranks refresh
  without a manual reload.
- Click again immediately during a run → button reports "already running" (409).
- `/`, `/strategy/[id]` unaffected and still 200.

## Out of scope (YAGNI)

- Run-Backtest, new-strategy wizard (later slices, reuse this mechanism).
- Progress streaming / SSE / websockets.
- Authentication / authorization (local single-user tool).
- A job queue beyond the single in-flight lock.
- Cloud / remote serving.

## Security

This endpoint executes a subprocess — a deliberate, contained break of the read-only
invariant:

- **No command injection:** fixed command and arguments
  (`python -m core.leaderboard`); **no user-supplied input** reaches the spawn;
  array args with **no `shell: true`**.
- **Local only:** runs under `next dev`/`next start` on localhost; single-user
  developer tool, so no auth/rate-limiting in scope (documented YAGNI).
- **No secrets** read or written; `refresh_all` only touches local CSVs + the index.
- `PYTHON_BIN`/`DATA_DIR` come from the server's own environment, not the request.

## Verification

- `pytest tests/test_leaderboard.py` green (new `main` cases included).
- `cd web && npm run test` green (new `recompute.test.ts`).
- `npx tsc --noEmit` + `npm run build` clean (heed `web/AGENTS.md` Next-16 caution
  for the Route Handler signature).
- Runtime checks above.
