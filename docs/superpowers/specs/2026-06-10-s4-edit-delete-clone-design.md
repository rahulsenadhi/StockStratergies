# S4 — Edit / Delete / Clone strategy (slice 13)

**Date:** 2026-06-10
**Slice:** S4 frontend (slice 13) — completes strategy CRUD
**Status:** Design approved (brainstorming locked), ready for plan

## Goal

Finish the user-strategy lifecycle. Slice 11 created the **create** write-path; slices
9/10/12 added Recompute / Run-Backtest / SSE streaming. This slice adds the three missing
operations — **edit**, **delete**, **clone** — for *user-created* strategies only:

- **Edit** — overwrite a strategy's spec (formula, exits, sizing, type, description,
  universe) keeping its `id` and `name` frozen, then re-run `generic_backtest.py` to
  refresh KPIs/CSVs (streamed, like create).
- **Delete** — remove a strategy: its index entry, `strategies/{id}.json`, and its
  `trades_csv`/`equity_csv` outputs. Instant, no backtest, no stream.
- **Clone** — fork an existing strategy into a new one (prefill the create form from the
  source spec, name `Copy of {name}`), then the normal create flow runs.

Reuses slice-12 `runJobStream` + `JobProgress` + `streamJob` + `job-lock`, and the
slice-11 create write-path (`writeStrategySpec` / `appendStrategyStub` /
`deriveStrategyId` / `summarizeExits`).

## Eligibility (the gate for all three ops)

All three operations are gated on **`strategies/{id}.json` existing** — i.e. the strategy
was created via the generic-spec path (slice 11). Built-ins (`momentum_edge`, `ipo_edge`,
`pead`, `monthly_rotation`) have **bespoke backtest scripts + a `backtest` argv** in the
index and **no generic spec file** → they get no Edit / Delete / Clone affordances.

The route param `id` is validated against `^[a-z0-9_]+$` **before any fs/spawn**
(path-traversal guard) — same regex the create route applies to the derived sid.

## Background / current state

- **Create route** (`web/app/api/strategy/route.ts`): validates body (name req, name≤80,
  `SID_RE` on derived sid, entry_formula req, ≥1 exit, sizing>0), dup-checks via
  `getStrategy(sid)` → 409, `tryAcquire` → 409 busy, then `streamJob`: build spec + stub,
  `writeStrategySpec` + `appendStrategyStub`, spawn `generic_backtest.py --spec
  strategies/{sid}.json` (600s, array args, `PYTHONUNBUFFERED=1`, no shell), release in
  `finally`. The validation block (lines ~42–61) is the part to extract.
- **Loader** (`web/lib/data/strategies.ts`): `getStrategy(id, dataDir?)`,
  `getStrategies(dataDir?)`, `mapStrategy(raw)`, plus slice-11 writes `writeStrategySpec`,
  `appendStrategyStub`, `deriveStrategyId`, `summarizeExits`, types `ExitsSpec` /
  `StrategyStub`. `DATA_DIR=".."` → repo root. Read-side maps empty `kpis_inline` → null
  KPIs, empty `equity_csv` → null.
- **Form** (`web/components/strategy-form.tsx`): `"use client"`, all fields are local
  state (no props today), submits `POST /api/strategy` via `runJobStream`, on `ok` →
  `router.push("/strategy/"+sid)`. Renders `<JobProgress/>` while loading.
- **`generic_backtest.main()`**: `_strategy_id = spec_path.stem`; `run_backtest(spec)`;
  `_update_strategies_index(sid, …)` **updates an existing index entry only**; then
  `refresh_all()`. So for edit, the index entry must already exist (it does) and the spec
  file must be overwritten before the spawn.
- **Job infra**: `web/lib/job-lock.ts` (`tryAcquire`/`release`/`isHeld`),
  `web/lib/job-stream.ts` (`streamJob(run)` — releases lock inside `run`'s finally),
  `runRecompute(spawnFn, {bin,args,cwd,timeoutMs,label?,onLine?})`.

## Architecture

### 1. Loader helpers (`web/lib/data/strategies.ts`)

```ts
export async function getStrategySpec(
  id: string, dataDir = DEFAULT_DATA_DIR,
): Promise<Record<string, unknown> | null>
```
Reads `${dataDir}/strategies/${id}.json` → parsed object, or `null` if absent (ENOENT) /
unparseable. This is the **eligibility probe** and the clone-prefill source.

```ts
export async function updateStrategyIndexEntry(
  id: string, patch: Record<string, unknown>, dataDir = DEFAULT_DATA_DIR,
): Promise<void>
```
Reads `strategies_index.json`; finds `strategies[].id === id`; **throws** `Error("strategy
not found: <id>")` if absent; shallow-merges `patch` into that entry; atomic write
(tmp + rename, `JSON.stringify(idx, null, 2)`). Used by edit to set `status:"Research"` +
refreshed `entry_rule`/`exit_rule`/`description`/`type`/`universe`/`sizing` before the
re-backtest. (`generic_backtest` then fills KPIs/CSVs and re-`refresh_all`s.)

```ts
export async function deleteStrategy(
  id: string, dataDir = DEFAULT_DATA_DIR,
): Promise<boolean>
```
Reads the index; locate entry by `id`. If absent → return `false`. Else: capture its
`trades_csv` / `equity_csv`; remove the entry; atomic write the index; `unlink`
`strategies/${id}.json` and each non-empty CSV path (resolved under `dataDir`),
**best-effort** (swallow ENOENT). Return `true`.

```ts
export function validateStrategyFields(body: CreateBody):
  | { ok: true }
  | { ok: false; error: string }
```
Extracted verbatim from the create route's validation (entry_formula required, ≥1 exit,
sizing `max_positions`>0 + `initial_cash`>0). **Excludes** name/sid checks — those are
create-only (edit freezes the name; sid comes from the route param). Create route is
refactored to call this **after** its name/sid checks (DRY; behavior-preserving).

All new write helpers use the existing atomic tmp+rename pattern and confine paths under
`dataDir`/repo root.

### 2. `web/app/api/strategy/[id]/route.ts` (new — PUT + DELETE)

Both handlers first: `const { id } = await params` (Next-16 async params);
`if (!SID_RE.test(id))` → `400`; `if (!(await getStrategySpec(id)))` → `404 {ok:false,
error:"strategy not found"}` (this is the user-created gate — built-ins have no spec).

**PUT (edit):**
- Parse body; `validateStrategyFields(body)` → 400 on failure.
- `tryAcquire()` → false → `409 {ok:false,error:"A job is already running"}`.
- `streamJob(async (onLine) => { try { … } finally { release() } })`:
  - Read existing spec via `getStrategySpec(id)`; **freeze `name`** from it (ignore any
    body name); build the new spec object (same shape as create: `entry_mode:"Formula
    DSL"`, body's `entry_formula`/`exits`/`sizing`/`type`/`description`/`universe`,
    preserved `name`).
  - `await writeStrategySpec(id, spec)` (overwrite); `await updateStrategyIndexEntry(id,
    { status:"Research", entry_rule:entryFormula, exit_rule:summarizeExits(exits),
    description, type, universe, sizing })`.
  - Spawn `runRecompute(spawnChild, { bin, args:["generic_backtest.py","--spec",
    `strategies/${id}.json`], cwd:repoRoot, timeoutMs:CREATE_TIMEOUT_MS, label:"Backtest",
    onLine })`. exit 0 → `200 {ok:true, sid:id}`; nonzero/timeout → return its status+body
    (spec already overwritten + status→Research; no rollback — matches create's
    stub-persists behavior).

**DELETE:**
- `tryAcquire()` → false → `409`. (Cheap, but guarded so a delete can't race a running
  backtest mutating the same files.)
- `try { const ok = await deleteStrategy(id); return ok ? 200 {ok:true} : 404
  {ok:false,error:"strategy not found"} } finally { release() }`. No stream (instant).

Shared module-scope `spawnChild` (PYTHONUNBUFFERED) + `SID_RE` + `CREATE_TIMEOUT_MS`
mirror the create route. `export const dynamic = "force-dynamic"`.

### 3. Create route refactor (`web/app/api/strategy/route.ts`)

Replace the inline entry_formula/exits/sizing validation with
`validateStrategyFields(body)` (called after the name/sid checks). No behavior change —
covered by existing `strategy-create.test.ts` + new `validateStrategyFields` unit tests.

### 4. Form parameterization (`web/components/strategy-form.tsx`)

Add props (default to today's create behavior):
```ts
interface StrategyFormProps {
  mode?: "create" | "edit";      // default "create"
  initial?: Partial<FormValues>; // prefill (clone + edit)
  strategyId?: string;           // edit target id (PUT endpoint)
  lockName?: boolean;            // edit → render Name read-only
}
```
- `useState` initializers read from `initial` (fallback to current defaults).
- Endpoint + method: create → `POST /api/strategy`; edit → `PUT /api/strategy/${strategyId}`.
  `runJobStream` currently POSTs — extend it to accept an optional `method` (default
  `"POST"`) so edit can PUT through the same SSE driver. On `ok` → edit pushes
  `/strategy/${strategyId}`, create pushes `/strategy/${data.sid}`.
- `lockName` → Name `<input readOnly disabled>` (edit). Submit button label: edit →
  "Save & re-backtest…", create unchanged.

### 5. UI wiring (detail page `web/app/strategy/[id]/page.tsx`)

Only when `await getStrategySpec(id)` is truthy (user-created), render an actions row:
- `<Link href={`/strategy/${id}/edit`}>Edit</Link>`
- `<Link href={`/strategy/new?from=${id}`}>Clone</Link>`
- `<DeleteStrategyButton id={id}/>`

Built-ins show none of these (no spec → guard false).

- **`web/app/strategy/[id]/edit/page.tsx`** (new RSC): `const { id } = await params`;
  `getStrategySpec(id)` → `notFound()` if null; map spec → `initial` FormValues; render
  `<StrategyForm mode="edit" strategyId={id} lockName initial={…}/>`.
- **`web/app/strategy/new/page.tsx`**: read `searchParams.from`; if set,
  `getStrategySpec(from)` → build `initial` with `name:"Copy of "+spec.name` (else
  defaults). Render `<StrategyForm initial={…}/>` (create mode). Clone needs **no new
  endpoint** — it's the create flow with a prefilled form.
- **`web/components/delete-strategy-button.tsx`** (new, `"use client"`): inline two-step
  confirm — first click → "Confirm delete?" (red), second click → `fetch(`/api/strategy/${id}`,
  {method:"DELETE"})`; on `ok` → `router.push("/leaderboard")`; on error → inline message.
  A 5s timeout (or a Cancel affordance) resets the armed state.

## Data flow

- **Edit:** `/strategy/{id}/edit` form → `PUT /api/strategy/{id}` → SID guard → spec-exists
  (404) → validate (400) → lock (409) → overwrite spec + index patch (status→Research) →
  spawn `generic_backtest.py --spec strategies/{id}.json` (streamed) → `{ok,sid:id}` →
  `router.push("/strategy/"+id)`. Lock released in finally.
- **Delete:** DeleteStrategyButton (2-step) → `DELETE /api/strategy/{id}` → SID guard →
  spec-exists (404) → lock (409) → `deleteStrategy` (entry + spec + CSVs) → `{ok}` →
  `router.push("/leaderboard")`.
- **Clone:** Clone link → `/strategy/new?from={id}` → RSC reads source spec → form
  prefilled, name `Copy of …` → normal create `POST /api/strategy`.

## Error handling

- Bad `id` (regex) → 400. Built-in / missing spec → 404. Validation → 400. Busy lock →
  409. Edit backtest nonzero/timeout → its 500/504 surfaces (spec already updated, status
  Research — no rollback). `deleteStrategy` IO error → caught → 500. All write helpers
  use atomic tmp+rename.

## Testing

**vitest** (`web/tests/strategy-edit-delete.test.ts`, new; temp-dir fixtures like
`strategy-create.test.ts`):
- `getStrategySpec`: returns parsed object for a written spec; `null` for absent /
  unparseable.
- `updateStrategyIndexEntry`: merges patch into the matching entry; **throws** "strategy
  not found" when absent; output parses as indent=2 JSON; other entries untouched.
- `deleteStrategy`: removes entry + spec file + both CSVs; returns `true`; returns `false`
  + leaves index intact when id absent; tolerates already-missing spec/CSV (no throw).
- `validateStrategyFields`: passes a valid body; rejects empty formula / no exits enabled /
  non-positive sizing — with the right message. Confirm the **create route still rejects**
  the same cases (existing `strategy-create.test.ts` stays green post-refactor).

**Runtime** (`cd web && npm run build && next start -p <port>`):
- Create a throwaway strategy → on its `/strategy/{id}`: Edit / Clone / Delete present.
  Open `/strategy/{id}/edit` → Name read-only, fields prefilled → change formula → Save →
  streamed progress → redirect, KPIs refreshed.
- Clone it via `/strategy/new?from={id}` → name `Copy of …`, fields prefilled → create.
- Delete the clone (2-step) → redirect to `/leaderboard`, gone from the list; spec +
  CSVs removed.
- A **built-in** detail page (`/strategy/momentum_edge`) shows **no** Edit/Clone/Delete;
  `PUT`/`DELETE /api/strategy/momentum_edge` → 404; `/api/strategy/../x` style bad id →
  400. Concurrent edit + recompute/backtest → 409.

## Out of scope (YAGNI)

- Rename on edit (name frozen; rename = clone-then-delete).
- Soft-delete, undo, trash, bulk operations.
- Server-side clone endpoint (clone = prefilled create).
- DSL dry-run / formula validation (separate slice).
- Rollback of spec/index on edit-backtest failure.
- Auth, cloud.

## Security

- `id` from the route param is **strictly `^[a-z0-9_]+$`** before any fs/spawn → path
  traversal (`..`, `/`, absolute) structurally blocked. The spec filename and the spawn
  argv use only that validated id.
- Spawn uses a **fixed array argv, no `shell:true`**; the only variable is the validated
  id → no command injection. `entry_formula` is written verbatim into the spec JSON,
  parsed by the existing Python DSL evaluator — never a shell.
- All writes/deletes confined to `strategies/{id}.json`, its `trades_csv`/`equity_csv`,
  and `strategies_index.json` under the repo root (atomic tmp+rename). Delete is
  best-effort on already-missing files. Local single-user tool; no auth (documented YAGNI).
- Edit/Delete share the single-process `job-lock` with create/backtest/recompute → no
  overlapping file mutation.
- Dedicated security-review pass at the route task.

## Verification

- `cd web && npm run test` green (new edit/delete helpers + refactored create still pass).
- `npx tsc --noEmit` + `npm run build` clean (heed `web/AGENTS.md` Next-16 caution —
  async `params`/`searchParams`).
- Runtime checks above (edit → clone → delete a created strategy; built-in shows no
  affordances + 404s).
