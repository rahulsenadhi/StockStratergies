# S4 — DSL Dry-Run Design

**Date:** 2026-06-11
**Status:** Approved (brainstorming)
**Slice:** S4 frontend, follows slice 13 (edit/delete/clone)

## Problem

Creating or editing a strategy runs a full backtest (load all OHLCV → compute
features → simulate portfolio), which is heavy. Users have no way to validate
an entry-formula (the DSL) before committing to that run. A typo or a
mis-thresholded formula is only discovered after the wait.

Worse, the current engine **swallows formula errors silently**:
`generic_backtest._evaluate_signals` catches any exception, prints a WARN, and
returns an all-`False` mask. So a typo (`xyz_bad > 1`) is indistinguishable
from a valid-but-dead formula (`rsi_14 > 200`) — both produce zero signals.
(Confirmed via spike `_dryrun_spike.py`, since deleted.)

## Goal

A "Preview signals" action on the strategy form that, for the current entry
formula + selected universe, reports:

- **Syntax / unknown-feature errors** explicitly (no silent False).
- **Today's matches**: count + ticker names on the latest trading date.
- **Recent firing rate**: signal-rows + distinct tickers over the last 90
  trading days — separates dead / sane / firehose formulas.

### Decisions locked during brainstorming

- **What to check:** syntax + signal preview (not syntax-only, not per-keystroke).
- **Window:** today + last-90-trading-days. Full-period dropped (noisy, no extra
  signal over 90d).
- **Unknown-feature error:** explicit — added after the spike proved silent-False
  is a trap.
- **Universe:** the universe selected in the form (honest, matches the real
  backtest). Big universes (full NSE+BSE ≈ 2321 tickers) are slow (~30s); accepted
  — the user chose it. Caching deferred.

### Spike findings (informed the above)

On Nifty 50 (157 tickers): load 2.1s + features 1.3s ≈ **3.4s**; eval itself
~0.01s. The data load dominates, so computing all windows costs the same as one.
Window counts cleanly discriminate: dead formula → 0/0/0; firehose
(`close > 0`) → 157 today / 14113 over 90d; plausible momentum → 14 / 1389.

## Architecture

Three units, each independently testable.

### 1. Python entrypoint — `dryrun.py`

Thin CLI reusing `generic_backtest` helpers (no logic duplication):

```
python dryrun.py --formula "<dsl>" --universe "Nifty 50"
```

Flow:

1. `_load_universe({universe})` → `_compute_features(ohlcv)` → feature panel.
   Same code path as the real backtest, so counts are honest.
2. **Unknown-feature check (before eval):** extract identifiers from the
   normalized formula via regex `[A-Za-z_]\w*`, drop the `AND/OR/NOT` keywords
   and numeric literals, subtract the known feature columns
   (`close, volume, rsi_14, atr_14, sma_50, sma_200, volume_z`). Any leftover
   identifier → fail with `unknown_features: [...]`.
3. Eval via `_evaluate_signals`. On a pandas/eval error → `error: "<msg>"`.
   (Dry-run surfaces the error; it does not rely on the silent-False catch.)
4. Compute today's matches (latest date, count, ticker list capped at ~25) and
   last-90-trading-day stats (signal_rows, distinct_tickers).
5. Print one JSON blob to stdout (may be preceded by progress noise on stderr/stdout).

Output contract:

```json
{ "ok": true,
  "universe": "Nifty 50",
  "today": { "date": "2026-06-04", "count": 14, "tickers": ["ABB.NS", "..."] },
  "history": { "trading_days": 90, "signal_rows": 1389, "distinct_tickers": 110 } }
```

or

```json
{ "ok": false, "error": "name 'xyz_bad' is not defined", "unknown_features": ["xyz_bad"] }
```

`unknown_features` present ⇒ the failure is a bad feature name; otherwise
`error` carries the eval/parse message.

### 2. API route — `web/app/api/strategy/dryrun/route.ts`

`POST { entry_formula, universe }`:

1. Validate: `entry_formula` non-empty trimmed string; `universe` defaults to
   `"Nifty 50"`.
2. **No job lock** — read-only, must neither block nor be blocked by a running
   backtest.
3. Spawn `dryrun.py` via the existing `spawnChild` pattern (`PYTHON_BIN`,
   cwd = repoRoot resolved from `DATA_DIR`). Collect stdout; **not** SSE.
4. Timeout `DRYRUN_TIMEOUT_MS = 120_000` (below create's 600s; covers big universes).
5. Parse the JSON blob from stdout (scan for the JSON line; ignore progress noise).
   Parse failure / non-zero exit → `{ ok:false, error }` 500.
6. Return python's JSON verbatim via `NextResponse.json`:
   - 200 on `ok:true`.
   - 400 on request validation failure (empty formula).
   - **200 with `ok:false`** on formula-invalid / unknown-feature — a valid
     request with a bad formula; frontend renders it as a formula error, not HTTP.
   - 500 on spawn / parse failure.

`runRecompute` is SSE-oriented; dry-run needs a simpler "spawn, collect stdout,
await exit" helper — add small `lib/spawn-collect.ts` rather than bending
`runRecompute`.

### 3. Frontend — `web/components/strategy-form.tsx`

"Preview signals" button beside the entry-formula textarea. Works in both
`create` and `edit` (formula + universe already in form state).

- New state: `previewing`, `preview` (result | null), `previewError`.
- Click → `POST /api/strategy/dryrun` with current `entryFormula` + `universe`.
  Disabled when formula empty or already previewing. Independent of the
  submit/`loading` flow — never blocks Create/Save.
- Result card below the textarea:
  - **Error / unknown-feature:** red — `Unknown feature(s): xyz_bad`, or the eval
    error string.
  - **Success:** `✓ 14 tickers match today (2026-06-04)` + names (truncated,
    "+N more"); second line `1389 signals over last 90 trading days · 110 distinct tickers`.
  - **Dead formula** (today 0 + history 0, but valid): amber warn
    `Formula valid but never fires — check thresholds`.
- Spinner "Previewing…" while in flight.

## Data flow

```
form (formula, universe)
  → POST /api/strategy/dryrun
    → spawn dryrun.py
      → _load_universe → _compute_features → unknown-feature check → _evaluate_signals
      → stdout JSON
    → parse → NextResponse.json
  → result card
```

## Error handling

| Case | Where | Result |
|------|-------|--------|
| Empty formula | route | 400 `ok:false` |
| Unknown feature | dryrun.py | 200 `ok:false` + `unknown_features` |
| Eval/syntax error | dryrun.py | 200 `ok:false` + `error` |
| Valid but never fires | dryrun.py | 200 `ok:true`, today 0 / history 0 → amber warn |
| Spawn / parse / timeout | route | 500 `ok:false` |
| No universe data | dryrun.py | 200 `ok:false` + `error` |

## Testing

- **Python** (`tests/test_dryrun.py`): unknown-feature detection; dead formula
  (valid, 0 fires); firehose; valid formula → JSON shape. Tiny fixture feature panel.
- **Vitest**: dryrun route — empty formula → 400; ok passthrough; formula-error
  → 200 `ok:false`. Mock the spawn.
- Follow existing patterns (153 vitest already green).

## Out of scope (YAGNI)

Feature-panel caching, per-keystroke validation, full-period window, feature-name
autocomplete. Revisit caching only if big-universe preview latency hurts.
