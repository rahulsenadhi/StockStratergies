# S4 Slice — SSE Backtest Progress

**Date:** 2026-06-10
**Status:** Approved design

## Problem

The long write actions in the Next.js app are fire-and-wait: the client POSTs,
shows a blind spinner, and waits 100–160s with no feedback.

- Rebuild All ≈ 138s
- Per-strategy Backtest ≈ 107–158s
- Create (`/api/strategy` → `generic_backtest.py`) — long

The Python scripts already print phase markers to **stdout** (`[3/5] Computing
indicators…`, `Validated 600/963…`), but the routes currently capture only
**stderr** (for the error body) and drop stdout.

## Goal

Stream the running child's stdout to the UI so the user sees live progress
(latest line + a coarse phase) during these runs.

## Scope

**In:** Backtest (`/api/backtest`), Rebuild All (`/api/rebuild-all`), Create
(`/api/strategy`).

**Out (YAGNI):** Recompute streaming (runs in seconds); structured `PROGRESS`
json emission / true percentage bars; job registry + reconnect; abort-on-cancel;
cloud.

## Decisions

- **Fidelity:** raw stdout log + opportunistic `[N/5]` coarse-phase parse. **Zero
  Python changes** — robust across all backtests, `generic_backtest.py`, and
  `core.leaderboard`.
- **Transport:** Approach A — the POST route returns a streaming `ReadableStream`
  of SSE frames; the client reads it via `fetch` (not native `EventSource`).
  Matches the existing single-job lock model — one in-flight job, no job registry.
- **UI:** inline latest-line + coarse phase on the button, plus a collapsible
  mini-log (last ~10 lines).

## Architecture

Keep the single-job lock (`lib/job-lock.ts`). On a long action:

1. Route acquires the lock. If busy → **409 plain JSON** (no stream).
2. Route opens a `ReadableStream` and returns it as the response
   (`Content-Type: text/event-stream`).
3. Route spawns the Python child and streams its stdout line-by-line as SSE
   `line` frames.
4. On child exit, the route enqueues a terminal `done` frame carrying the same
   result JSON the route returns today, then closes the stream.
5. Lock is released in `finally` after the stream closes.

The client reads the stream, updates the UI per `line` frame, and on `done` runs
the existing `router.refresh()` / `router.push()`.

### SSE frame protocol

```
event: line
data: <one stdout line>

event: done
data: <result JSON: same shape the route returns today>
```

`done` always fires (success or failure). Failure is `{ok:false,error}` inside
the `done` payload — there is no separate transport-level error status once the
stream is open. The HTTP status is 200 as soon as the stream opens; the real
outcome lives in `done`.

## Components

### 1. Lib seam — stdout capture + `onLine`

- `SpawnedChild` (in `lib/recompute.ts`) gains `stdout` (same shape as `stderr`).
- `runRecompute` gains optional `onLine?(line: string)`: capture `child.stdout`,
  buffer, split on `/\r?\n|\r/` (handles the `\r` progress lines), emit each
  **complete** line via `onLine`. stderr still accumulates for the error body.
- `runRebuildAll` gains optional `onLine`: emits a `▶ running <id>` header line
  before each step, and threads `onLine` into each `runRecompute` call.
- `onLine` is optional → existing behavior and tests are unchanged. Both stay
  pure (injected `spawnFn`) and unit-testable with a fake child that emits stdout
  chunks.

### 2. `lib/sse.ts`

- Pure `sseFrame(event: string, data: string): string` →
  `event: ${event}\ndata: ${data}\n\n`. Data is single-line (stdout lines have no
  newlines after splitting); `done` data is JSON.stringify (no embedded newlines).
- Unit-tested.

### 3. Route changes (backtest, rebuild-all, strategy-create)

- After lock acquire, build a `ReadableStream`; wire `onLine → controller.enqueue(
  sseFrame("line", line))`.
- On the job promise resolving, enqueue `sseFrame("done", JSON.stringify(result))`,
  then `controller.close()`.
- Return `new Response(stream, { headers: { "content-type": "text/event-stream",
  "cache-control": "no-cache", "connection": "keep-alive" } })`.
- Release the lock in `finally` once the stream lifecycle completes.
- **Do NOT kill the child on stream `cancel()`** (client navigated away) — the job
  finishes and the lock frees normally. Trade-off: no abort-on-cancel.
- 409 / 400 / 404 / 422 validation responses (create, backtest) stay plain JSON,
  returned **before** the stream opens.

### 4. `lib/use-job-stream.ts` (`"use client"`)

- `runJobStream(url, body?, { onLine, onPhase }) → Promise<Result>`:
  - POST; if non-OK + non-stream (e.g. 409/400) → parse JSON, throw/return the
    error shape.
  - Else read `res.body.getReader()`, decode, buffer until `\n\n`, parse each
    frame; `line` → `onLine(line)` + parse `[N/5]` → `onPhase`; `done` → resolve
    with the parsed result.
- Shared by all three buttons.

### 5. `components/job-progress.tsx` + button updates

- `JobProgress` presentational: latest line + coarse phase badge; collapsible
  mini-log (last ~10 lines, capped buffer).
- `RebuildAllButton`, `BacktestButton`, `NewStrategyForm` switch from
  `fetch+await` to `runJobStream`, feed `JobProgress`, and keep their existing
  success/error handling on the resolved `done` payload.

## Data flow

```
click → POST → lock → open stream → spawn python
      → stdout line → onLine → "line" frame → client: update latest/log/phase
      → … → child exit → "done" frame (result) → close
      → client resolves → router.refresh()/push()
```

## Error handling

| Case | Behavior |
|------|----------|
| Lock busy | 409 plain JSON, no stream; client shows "already running" |
| Spawn throws / child `error` | `done` frame `{ok:false,error}` |
| Timeout | kill child; `done` frame `{ok:false,error:"… timed out"}` |
| Client disconnect | job runs to completion; lock frees in `finally` |
| Partial SSE frame | client buffers until `\n\n` |
| Validation (create/backtest) | plain JSON before stream opens |

## Testing

**Unit (vitest):**
- `runRecompute` `onLine`: fake child emits stdout chunks — lines split across
  chunks, `\r` progress runs, trailing partial line — assert exact emitted lines.
- `runRebuildAll`: `▶ running <id>` headers + `onLine` threaded per step.
- `sseFrame`: exact frame string.
- client frame parser: feed chunked bytes incl. a frame split across reads;
  assert parsed `line`/`done` events and `[N/5]` phase extraction.
- Existing `runRecompute` / `runRebuildAll` tests stay green (onLine optional).

**Runtime verify (verify skill, later):** real Rebuild All through the UI —
observe live phase + mini-log advancing, then the leaderboard refresh on `done`.

## Security

Unchanged. No new request input reaches `spawn` (still trusted argv from the
index / fixed `core.leaderboard` command, array args, no shell). The stream
carries only the child's stdout text to the single local user; backtest stdout
contains no secrets.
