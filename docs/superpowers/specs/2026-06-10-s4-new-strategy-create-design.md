# S4 — New-Strategy Create (slice 11)

**Date:** 2026-06-10
**Slice:** S4 frontend (slice 11) — third write action
**Status:** Design approved, ready for plan

## Goal

A minimal single-page form to create a user strategy from the web app: it writes the
strategy spec (`strategies/{sid}.json`) plus a Research stub into
`strategies_index.json`, then runs `generic_backtest.py --spec strategies/{sid}.json`
(which fills KPIs/CSVs and already calls `refresh_all` itself). The new strategy then
appears on the leaderboard. Reuses the slice-9/10 write mechanism (shared `job-lock`,
`runRecompute`). Defers the full multi-step wizard, indicator pickers, and DSL
dry-run validation to later slices.

## Background / current state

- Streamlit's `_save_user_strategy(data)` (master_dashboard.py, Streamlit-coupled — NOT
  importable) writes a Research **stub** into the index (empty kpis/csvs,
  `status:"Research"`, `page_key:"Library"`) and dumps `strategies/{sid}.json`, then
  spawns `generic_backtest.py --spec strategies/{sid}.json`.
- `generic_backtest.main()` derives `_strategy_id = spec_path.stem` (filename without
  `.json`), runs `run_backtest(spec)`, calls `_update_strategies_index(sid, kpis,
  trades_path, equity_path)` — which **only updates an existing** index entry — then
  calls `refresh_all()`. So the stub must exist in the index before the backtest runs;
  the recompute is already chained inside `generic_backtest` (no separate recompute
  step needed, unlike slice 10).
- `run_backtest(spec)` reads exactly: `spec["universe"]`, `spec["entry_formula"]`,
  `spec["exits"]` keys `{time_enabled, time_days, hard_stop_enabled, hard_stop_pct,
  trail_enabled, trail_pct}`, `spec["sizing"]` keys `{method, max_positions,
  initial_cash}`. (`name`/`description`/`type`/`entry_mode` are index/UI metadata, not
  read by the backtest. `next_earnings` is NOT read by generic_backtest — omitted.)
  Reference good spec: `strategies/test_rsi_breakout.json`.
- Loader `web/lib/data/strategies.ts`: read-only today. `getStrategies(dataDir?)`,
  `getStrategy(id, dataDir?)`, `mapStrategy(raw)`. `DATA_DIR=".."` → repo root.
  `mapStrategy` maps empty `kpis_inline` → null KPIs and empty `equity_csv` → null, so a
  Research stub renders cleanly (unranked → sorts last).
- Slice-9/10 infra available: `web/lib/job-lock.ts` (`tryAcquire`/`release`),
  `runRecompute(spawnFn, {bin,args,cwd,timeoutMs,label?})`. Leaderboard header already
  hosts `<RecomputeButton/>`.

## Spec shape written to `strategies/{sid}.json`

```json
{
  "name": "<string>",
  "description": "<string>",
  "type": "<string, e.g. Momentum>",
  "universe": "<string, e.g. Nifty 50>",
  "entry_mode": "Formula DSL",
  "entry_formula": "<DSL string>",
  "exits": {
    "time_enabled": true,
    "time_days": 30,
    "hard_stop_enabled": true,
    "hard_stop_pct": 8.0,
    "trail_enabled": true,
    "trail_pct": 12.0
  },
  "sizing": {
    "method": "Equal weight (capped)",
    "max_positions": 5,
    "initial_cash": 1000000
  }
}
```

(Each `*_enabled` toggle is independent; the disabled ones may carry default numbers.)

## Architecture

### 1. Loader write helpers (`web/lib/data/strategies.ts`)

First **writes** added to the loader seam.

```ts
export function deriveStrategyId(name: string): string {
  return name.trim().toLowerCase().replace(/[ -]/g, "_");
}
```
Used by the route, which then asserts the result matches `^[a-z0-9_]+$` (reject
otherwise). (Kept pure + tiny; the regex guard lives in the route so the helper stays a
plain transform — both are unit-tested.)

```ts
export async function writeStrategySpec(
  sid: string, spec: unknown, dataDir = DEFAULT_DATA_DIR,
): Promise<void>
```
Atomically writes `${dataDir}/strategies/${sid}.json` (`mkdir -p strategies`, write to a
`.tmp` sibling, `rename`), `JSON.stringify(spec, null, 2)`.

```ts
export type StrategyStub = {
  id: string; name: string; type: string; status: string; description: string;
  universe: string; entry_rule: string; exit_rule: string;
  sizing: Record<string, unknown>;
  trades_csv: string; equity_csv: string; kpis_inline: Record<string, never>;
  last_run: string; created: string; page_key: string;
};

export async function appendStrategyStub(
  stub: StrategyStub, dataDir = DEFAULT_DATA_DIR,
): Promise<void>
```
Reads `${dataDir}/strategies_index.json`; if any existing `strategies[].id === stub.id`
throws `Error("strategy id already exists: <id>")`; appends the stub; atomic write
(tmp + rename, `JSON.stringify(idx, null, 2)` — matches `refresh_all`'s indent=2). The
stub mirrors Streamlit's `_save_user_strategy` shape.

`exit_rule` is a human summary built in the route (port of `_summarize_exits`):
`["hold 30d", "hard stop 8%", "trail 12%"]` joined by `" · "`, or `"—"`.

### 2. `POST /api/strategy` (`web/app/api/strategy/route.ts`, new)

Body (JSON): `{ name, description, type, universe, entry_formula, exits, sizing }`.

- **Validate (400 with message)**: `name` non-empty string; `deriveStrategyId(name)`
  matches `^[a-z0-9_]+$` (non-empty after sanitize); `entry_formula` non-empty string;
  at least one of `exits.time_enabled | hard_stop_enabled | trail_enabled` true;
  `sizing.max_positions` and `sizing.initial_cash` positive numbers.
- **Duplicate id → 409**: if `getStrategy(sid)` already exists →
  `{ok:false,error:"A strategy with that name already exists"}`.
- `tryAcquire()` → false → `409 {ok:false,error:"A job is already running"}`.
- In `try/finally(release)`:
  - Build the spec object (shape above; `entry_mode:"Formula DSL"`) and the stub.
  - `await writeStrategySpec(sid, spec)`; `await appendStrategyStub(stub)`. (If
    `appendStrategyStub` throws on a race duplicate → catch → 409.)
  - Spawn the backtest: `runRecompute(spawnChild, { bin: PYTHON_BIN ?? "python",
    args: ["generic_backtest.py", "--spec", `strategies/${sid}.json`], cwd: repoRoot,
    timeoutMs: 600_000, label: "Backtest" })`, where `repoRoot = path.resolve(
    process.cwd(), process.env.DATA_DIR ?? "..")`. `sid` is already sanitized to
    `^[a-z0-9_]+$`, so the constructed spec path is safe; **array args, no shell**.
  - On backtest exit 0 → `200 {ok:true, sid}`. On nonzero/timeout → return that status
    + body (the **stub persists as "Research"** — matches Streamlit's "saved as
    Research"; user sees the error). No rollback this slice.
- Constant `CREATE_TIMEOUT_MS = 600_000`.

### 3. UI

- **`web/components/new-strategy-link.tsx`** OR reuse a plain `<Link>`: add a
  "+ New strategy" link/button in the leaderboard header (`web/app/leaderboard/page.tsx`),
  next to `<RecomputeButton/>`, pointing to `/strategy/new`.
- **`web/app/strategy/new/page.tsx`** (RSC shell) renders **`StrategyForm`**.
- **`web/components/strategy-form.tsx`** (`"use client"`): controlled fields — name,
  type, description, universe (text inputs/selects), entry_formula (textarea), exits
  (3 checkboxes + number inputs: time_days, hard_stop_pct, trail_pct), sizing (method
  select, max_positions, initial_cash numbers). Submit → `POST /api/strategy` with the
  assembled body. On `ok` → `router.push("/strategy/" + data.sid)`. On error → inline
  red message. Disabled + "Creating & backtesting… (1–3 min)" while loading. Mirrors
  the existing button components' fetch/error/loading pattern.

## Data flow

Submit → `POST /api/strategy` → validate + derive/sanitize sid → dup check (409) →
`tryAcquire` → write `strategies/{sid}.json` + append Research stub → spawn
`python generic_backtest.py --spec strategies/{sid}.json` (writes equity/trades CSVs,
updates the stub's kpis/csvs, calls `refresh_all`) → `{ok:true, sid}` → client
`router.push("/strategy/"+sid)` → the strategy-detail RSC reads the now-populated entry.
Lock released in `finally`.

## Error handling

- Validation failures → 400 with a specific message.
- Duplicate id (pre-check or `appendStrategyStub` throw) → 409.
- Busy lock → 409.
- Backtest nonzero/timeout → its 500/504 surfaces; stub remains "Research".
- `writeStrategySpec`/`appendStrategyStub` IO errors → caught → 500 with message.

## Testing

**vitest** (`web/tests/strategy-create.test.ts`, new):
- `deriveStrategyId`: `"My Cool Strat"` → `"my_cool_strat"`; hyphen → `_`; trims;
  (route-level guard against bad chars is tested via the validation unit if extracted,
  else covered by an explicit `deriveStrategyId` + regex assertion).
- `writeStrategySpec`: writes `strategies/{sid}.json` under a tmp dataDir with the exact
  object (read back + parse).
- `appendStrategyStub`: appends to a tmp index; **throws on duplicate id**; result index
  contains the stub and parses as indent=2 JSON.
- `summarizeExits` (the `exit_rule` builder, if extracted as a pure helper): toggles →
  `"hold 30d · hard stop 8% · trail 12%"`, none → `"—"`.
- Reuse existing job-lock / runRecompute tests.

**Runtime:**
- `cd web && npm run build && next start`. Open `/strategy/new`, fill a simple formula
  (e.g. `rsi_14 > 70 AND close > sma_200`), submit. Confirm `strategies/{sid}.json` is
  written, a stub appears in `strategies_index.json`, and (if the backtest succeeds in
  this env) the strategy shows on `/leaderboard` with KPIs; on redirect `/strategy/{sid}`
  renders.
- Submit a duplicate name → 409 message. Submit empty name / empty formula / no exits →
  400 message. While a create runs, `POST /api/recompute` → 409.
- `/leaderboard`, `/`, existing strategy pages still 200.

Note: the backtest invokes the real `generic_backtest.py`, which needs universe data and
may take minutes or fail for data reasons unrelated to the wiring. If it fails for
environment reasons, report it — do not alter the Python. Deterministic gates: the spec
file + stub are created, validation 400/409 paths, and the form renders/redirects.

## Out of scope (YAGNI)

- Multi-step wizard, stepper, indicator pickers.
- DSL dry-run / live formula validation (bad formula → backtest fails → Research stub).
- Edit / delete / clone strategy.
- Rollback of the stub on backtest failure.
- Streaming progress, authentication, cloud.

## Security

- Request supplies form data only. `sid` is **derived from `name` then strictly
  sanitized** to `^[a-z0-9_]+$` (reject otherwise) — used for the spec filename and the
  fixed spawn argv. Spawn uses **array args, no `shell:true`**; the only variable in the
  argv is the sanitized `sid`. No command injection.
- `entry_formula` is written verbatim into the spec JSON file and parsed by the existing
  Python DSL evaluator — it never reaches a shell.
- Writes are confined to `strategies/{sid}.json` and `strategies_index.json` under the
  repo root (atomic tmp+rename). Local single-user tool; no auth (documented YAGNI). No
  secrets.

## Verification

- `cd web && npm run test` green (new create helpers + existing suite unchanged).
- `npx tsc --noEmit` + `npm run build` clean (heed `web/AGENTS.md` Next-16 caution).
- Runtime checks above.
