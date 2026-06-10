# S4 — Local Write-API: Run-Backtest (slice 10)

**Date:** 2026-06-09
**Slice:** S4 frontend (slice 10) — second write action
**Status:** Design approved, ready for plan

## Goal

Add a per-strategy **Run Backtest** button on `/strategy/[id]` that re-runs the
strategy's backtest script (regenerating its equity/trades CSVs), then chains a
recompute to refresh KPIs + rank, then live-refreshes the page. Builds directly on
the slice-9 write mechanism (`web/lib/recompute.ts`, `POST /api/recompute`). Fire-and-
wait (no streaming).

## Background / current state

- Slice 9 shipped `web/lib/recompute.ts` with `resolveRecompute(env,cwd)` and a
  **generic** `runRecompute(spawnFn, {bin,args,cwd,timeoutMs}) -> {status, body}`
  mapper (exit 0→200, nonzero→500+stderr, timeout→504+kill, spawn error/throw→500;
  `settled` guard + `clearTimeout`). `POST /api/recompute` holds a module-level
  in-flight lock and spawns `python -m core.leaderboard`.
- Built-in backtest scripts are heterogeneous: `momentum_edge_backtest.py` and
  `ipo_edge_backtest.py` run with **no args**; `pead_backtest.py` needs required
  `--start`/`--events`; `generic_backtest.py` needs `--spec`. There is currently **no
  backtest command recorded** in `strategies_index.json`.
- The strategy-detail page `web/app/strategy/[id]/page.tsx` is a `force-dynamic` RSC:
  back-link, a header `<div>` with `<h1>{s.name}</h1>` + `<p>{type · status}</p>`,
  then KpiStrip / sections.
- Loader `web/lib/data/strategies.ts`: `Strategy` type + `mapStrategy(raw)` +
  `getStrategy(id, dataDir?)`. Reads `$DATA_DIR/strategies_index.json`.

## Command resolution (declarative)

Each strategy entry in `strategies_index.json` gets an **optional `backtest` argv
array** — the exact argument vector to pass to Python (after the interpreter). This
slice populates two:

```json
"backtest": ["momentum_edge_backtest.py"]   // momentum_edge
"backtest": ["ipo_edge_backtest.py"]        // ipo_edge
```

`pead` and `monthly_rotation` get **no** `backtest` field → the button is not rendered
for them (run via Streamlit). Adding a strategy later = add the field, no code change.

Loader changes (`web/lib/data/strategies.ts`):
- `Strategy` gains `backtest: string[] | null`.
- `mapStrategy`: `backtest: Array.isArray(raw.backtest) ? raw.backtest : null`.

The request never supplies the command — only the strategy `id`. The command comes
from the trusted server-side index.

## Architecture

### 1. `web/lib/recompute.ts` — add `resolveBacktest` (reuse `runRecompute`)

`runRecompute` is already generic (command comes from `opts.args`); reuse it verbatim
for both the backtest step and the recompute step. Do **not** rename it (slice-9 tests
depend on the name).

Add a pure helper:

```ts
export function resolveBacktest(
  argv: string[] | null,
  repoRoot: string,
  env: { PYTHON_BIN?: string },
): { bin: string; args: string[]; cwd: string } {
  if (!argv || argv.length === 0) throw new Error("no backtest command configured");
  const script = argv[0];
  if (
    script.startsWith("/") ||
    /^[a-zA-Z]:/.test(script) ||        // windows absolute
    script.includes("..") ||
    !script.endsWith(".py") ||
    /[;&|`$<>\n]/.test(argv.join(" "))  // shell metacharacters anywhere in argv
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

(Validation is defense-in-depth: the argv is from the trusted index, not the request,
but we still reject absolute paths, `..` traversal, non-`.py` first arg, and shell
metacharacters. Spawn always uses array args with no `shell:true`.)

### 2. `web/lib/job-lock.ts` — shared in-flight lock (new)

Extract the lock so recompute and backtest **cannot overlap**:

```ts
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

Refactor `web/app/api/recompute/route.ts` to use `tryAcquire()`/`release()` instead of
its local `let running` (behavior identical: 409 when busy, release in `finally`).

### 3. `web/app/api/backtest/route.ts` — `POST` handler (new)

- `force-dynamic`. Parse JSON body; require `id: string` (else
  `400 {ok:false,error:"missing id"}`).
- `getStrategy(id)` (loader, default data dir). Unknown → `404
  {ok:false,error:"unknown strategy"}`. No `backtest` field → `422
  {ok:false,error:"backtest not configured for this strategy"}`.
- `tryAcquire()` → if false, `409 {ok:false,error:"A job is already running"}`.
- In `try/finally` (release in finally):
  - `repoRoot = path.resolve(process.cwd(), process.env.DATA_DIR ?? "..")`.
  - `const bt = resolveBacktest(strategy.backtest, repoRoot, process.env)` (a thrown
    validation error → `500 {ok:false,error}` — catch around it).
  - Step 1 — run backtest: `runRecompute(spawn-wrapper, {...bt, timeoutMs: 600_000})`.
    If `status !== 200`, return that `{status, body}`.
  - Step 2 — chain recompute: `runRecompute(spawn-wrapper, { bin: bt.bin,
    args: ["-m","core.leaderboard"], cwd: repoRoot, timeoutMs: 120_000 })`. Return its
    `{status, body}` (so a recompute failure surfaces too). Success → `200 {ok:true,
    durationMs}` from the recompute step.
- The spawn-wrapper is `(b,a,o) => spawn(b,a,o) as unknown as SpawnedChild`, identical
  to the recompute route.

Constants: `BACKTEST_TIMEOUT_MS = 600_000`, `RECOMPUTE_TIMEOUT_MS = 120_000`.

### 4. `web/components/backtest-button.tsx` — client button (new)

`"use client"`, props `{ strategyId: string }`:
- Button "▶ Run Backtest"; while loading → "Running backtest… (1–3 min)", disabled.
- `fetch("/api/backtest", { method: "POST", headers: {"content-type":"application/json"},
  body: JSON.stringify({ id: strategyId }) })`.
- Parse JSON (catch → `{}`). `res.ok && data.ok` → `router.refresh()`; else
  `setError(data.error ?? "Backtest failed (" + res.status + ")")`. Network error →
  inline message. `finally` clears loading. Inline red error span. Mirrors
  `recompute-button.tsx`.

### 5. Wire into `web/app/strategy/[id]/page.tsx`

In the existing header `<div>` (name + type·status), render `<BacktestButton
strategyId={s.id} />` on the right, **only when `s.backtest` is set**:

```tsx
<div className="flex items-start justify-between">
  <div>
    <h1 className="text-2xl font-bold">{s.name}</h1>
    <p className="text-sm text-muted-foreground">{s.type} · {s.status}</p>
  </div>
  {s.backtest && <BacktestButton strategyId={s.id} />}
</div>
```

(Preserve the existing classes/structure; only add the flex wrapper + conditional
button. The back-link, KpiStrip, sections, and `<StrategySection/>` are unchanged.)

## Data flow

Click → `POST /api/backtest {id}` → lookup + validate → `tryAcquire` → spawn
`python <script>.py` (cwd repo root, 600 s) regenerates the strategy's CSVs → on exit 0,
spawn `python -m core.leaderboard` (120 s) rewrites `strategies_index.json` KPIs/rank →
`{ok:true}` → client `router.refresh()` → strategy-detail RSC re-reads loader → fresh
KPIs/equity render. Lock released in `finally`.

## Error handling

- Missing/invalid body id → 400. Unknown strategy → 404. No `backtest` field → 422.
- Busy (lock held by recompute or another backtest) → 409.
- Backtest script nonzero exit → 500 with its stderr (recompute step skipped).
- Backtest timeout (>600 s) → 504, child killed.
- Recompute step failure after a successful backtest → its 500/504 surfaces (CSVs were
  still regenerated; the user sees the recompute error and can retry recompute).
- `resolveBacktest` validation throw → 500 with the message.

## Testing

**vitest** (`web/tests/recompute.test.ts` extend, or `web/tests/backtest.test.ts` new):
- `resolveBacktest`:
  - valid argv `["momentum_edge_backtest.py"]` + repoRoot → `{bin:"python", args:[…],
    cwd: repoRoot}`; `PYTHON_BIN` override honored.
  - throws on: `null`/`[]` (not configured); absolute path (`/etc/x.py`, `C:\x.py`);
    `..` traversal (`../x.py`); non-`.py` first arg (`momentum_edge_backtest`); shell
    metacharacters in argv (`["x.py", "; rm -rf /"]`).
- `job-lock`: `tryAcquire()` returns true then false while held; `release()` frees it;
  `isHeld()` reflects state. (Reset state between tests — the module is singleton, so
  `release()` in a `beforeEach`/`afterEach`.)
- Existing `runRecompute`/`resolveRecompute` tests remain green (reused unchanged).

**Runtime:**
- `cd web && npm run build && next start`. Open `/strategy/momentum_edge`: the
  "▶ Run Backtest" button is present. Click → after the run completes, the strategy's
  equity CSV + `kpis_updated` change and KPIs refresh without manual reload.
- `/strategy/pead` shows **no** button (no `backtest` field).
- While a backtest runs, `POST /api/recompute` (or a second backtest) returns 409.
- `/leaderboard`, `/` still 200.

Note: the runtime backtest invokes real Python scripts that may require their own data
prerequisites or take minutes; if a script fails in this environment for reasons
unrelated to the wiring (missing data, long run), report it — do not alter the scripts.
The vitest + build are the hard gates; the deterministic runtime checks are: button
renders for momentum_edge/ipo_edge, absent for pead, and 409 while busy.

## Out of scope (YAGNI)

- Streaming/SSE progress, status polling, job queue.
- Wiring `pead` (required args) and `monthly_rotation` (script unconfirmed).
- New-strategy wizard (`generic_backtest.py --spec`).
- Authentication, cloud/remote serving.

## Security

Same posture as slice 9, extended:
- Request supplies only the strategy `id`; the command **argv comes from the
  server-side trusted index**, never the request.
- `resolveBacktest` validates the argv (repo-relative `.py`, no absolute, no `..`, no
  shell metacharacters); spawn uses **array args, no `shell:true`** → no command
  injection.
- Local single-user developer tool — no auth/rate-limiting in scope (documented YAGNI).
- No secrets read/written.

## Verification

- `cd web && npm run test` green (new `resolveBacktest` + `job-lock` cases; existing
  suite unchanged).
- `npx tsc --noEmit` + `npm run build` clean (heed `web/AGENTS.md` Next-16 caution).
- Runtime checks above.
