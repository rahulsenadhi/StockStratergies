# S0a — Parquet/DuckDB Local Data Layer — Design

**Date:** 2026-06-04
**Status:** Approved for planning
**Parent:** `docs/superpowers/specs/2026-06-04-platform-v2-prd.md` (Subsystem S0, local half)
**Author:** brainstorming session (rahulsenadhi)

## Problem

The dashboard and backtests read price data by globbing hundreds of per-ticker CSVs
on every access (`data/nse_bse/` ~963 files; `ipo_data/`; `momentum_edge_data/`).
`load_ipo()` scans `ipo_data/` live on every page load and `load_momentum()` can fall
back to a ~52s live compute. Reading and parsing CSVs repeatedly is the core slow-load
pain. We want a fast, compact, append-friendly columnar store with **zero disruption**
to existing call sites, and one that will upload cleanly to Cloudflare R2 in the
follow-up cloud phase (S0b).

## Decisions (from brainstorming)

| Question | Decision |
|---|---|
| Scope | **Local data layer only.** Cloud refresh + R2 publish deferred to S0b. |
| Storage shape | **Partitioned Parquet** (source of truth) **queried via DuckDB.** No separate binary DB file to keep in sync. |
| Read path | **Drop-in compat loader + query helper.** A `load_ohlcv`-shaped function returning the same dict, plus a `get_bars` slice query for new code. No mass refactor. |
| Population | **Keep CSV downloaders untouched** + a one-time backfill and an idempotent CSV→Parquet sync (mtime-gated). Native-Parquet downloaders deferred to S0b. |
| App-state DB (D1) | Not part of S0a — applies to later subsystems (ledger/goals). Noted only. |

## Architecture

Three units with clear boundaries:

```
convert_to_parquet.py     CSV -> Parquet backfill + idempotent sync (CLI)
core/store.py             Parquet/DuckDB read layer (compat loader + query helper)
core/data_io.load_ohlcv   gains a Parquet fast-path (transparent to all callers)
```

**Non-breaking principle:** if a dataset's Parquet store does not exist, every path
falls back to the current CSV behavior. The fast-path activates only once the store
is populated.

### Store layout

```
data/parquet/<dataset>/ticker=<TICKER>/bars.parquet
data/parquet/<dataset>/_manifest.json
```

- Hive-style partition `ticker=<TICKER>` so DuckDB prunes by ticker.
- `bars.parquet` columns: `Date` (timestamp, tz-naive), `Open`, `High`, `Low`,
  `Close` (float64), `Volume` (int64). Sorted ascending by Date, NaN-Close rows dropped.
- `_manifest.json`: `{ "<TICKER>": <source_csv_mtime_float>, ... }` — drives incremental sync.
- Datasets in scope (basename keys): `nse_bse`, `ipo_data`, `momentum_edge_data`.

### Component 1 — `convert_to_parquet.py` (CLI)

Reuses `core.data_io.load_single` for CSV parsing/normalization so Parquet bytes match
what `load_ohlcv` would have produced.

- `dataset_paths(dataset) -> (csv_dir, parquet_dir)` — maps a dataset name to
  `<dataset>` (or `data/nse_bse` for `nse_bse`) and `data/parquet/<dataset>`.
- `backfill(dataset)` — parse every CSV in the dataset's CSV dir, write
  `ticker=<TICKER>/bars.parquet`, write `_manifest.json`. Overwrites existing.
- `sync(dataset)` — read `_manifest.json`; for each CSV whose current mtime differs
  from the manifest (or is absent), reconvert that ticker and update the manifest entry.
  Tickers whose CSV vanished are left as-is (no deletion in S0a). Manifest written
  atomically (temp file + `os.replace`). Returns counts `{converted, skipped}`.
- CLI flags: `--backfill <dataset>`, `--sync <dataset>`, `--backfill-all`, `--sync-all`
  (all = the three in-scope datasets). Prints per-dataset converted/skipped counts.

### Component 2 — `core/store.py`

```python
DATASETS = {                       # dataset name -> CSV source dir
    "nse_bse": "data/nse_bse",
    "ipo_data": "ipo_data",
    "momentum_edge_data": "momentum_edge_data",
}
PARQUET_ROOT = "data/parquet"

def parquet_dir(dataset: str) -> Path: ...
def has_store(dataset: str) -> bool:          # True if data/parquet/<dataset>/ has any bars

def _connect() -> duckdb.DuckDBPyConnection:  # in-memory connection

def load_ohlcv_parquet(
    dataset: str, min_bars: int = 10,
    skip: set[str] | None = None, whitelist: set[str] | None = None,
) -> tuple[dict[str, pd.DataFrame], dict[str, float]]:
    """Drop-in equivalent of data_io.load_ohlcv, reading the Parquet store.
    Returns ({ticker: OHLCV DataFrame (Date index)}, {ticker: parquet mtime}).
    Honors skip/whitelist/min_bars exactly as the CSV loader does."""

def get_bars(
    dataset: str, tickers: list[str] | None = None,
    start: str | None = None, end: str | None = None,
    cols: list[str] | None = None,
) -> pd.DataFrame:
    """Tidy slice query for new code. Columns: ticker, Date, + requested OHLCV
    (all OHLCV if cols is None). Pushdown filters via DuckDB."""
```

- `load_ohlcv_parquet` reconstructs the same per-ticker DataFrame shape the CSV loader
  returns (Date index named `Date`, `[Open,High,Low,Close,Volume]` columns), applying
  `min_bars`, `skip`, `whitelist`. mtime = the `bars.parquet` file mtime.
- All reads go through DuckDB over the Parquet glob; a per-dataset query failure logs and
  raises so the caller's fast-path guard (below) can fall back.

### Component 3 — `data_io.load_ohlcv` fast-path

Add, at the top of `load_ohlcv`, after resolving `folder`:

```python
from core import store   # lazy import INSIDE load_ohlcv — avoids circular import
import logging
dataset = Path(folder).name
if store.has_store(dataset):
    try:
        return store.load_ohlcv_parquet(dataset, min_bars, skip, whitelist)
    except Exception:
        logging.warning("Parquet read failed for %s; falling back to CSV", dataset)
# ... existing CSV glob path unchanged ...
```

**Circular-import note:** `store.py` imports `data_io.load_single` at module level; therefore
`data_io` must NOT import `store` at module level. The `from core import store` above lives
*inside* `load_ohlcv` (call-time import), breaking the cycle.

This keeps every current caller (backtests, precompute, dashboard `load_*`) working with
no edits, automatically fast once the store exists. The `workers`/`progress` params are
accepted and ignored on the parquet path.

## Data Flow & Pipeline Wiring

```
downloaders (unchanged) -> CSV -> convert_to_parquet sync -> data/parquet/<dataset>/
                                                                   |
            data_io.load_ohlcv (parquet fast-path) -> backtests / precompute / dashboard
```

Parquet must be fresh before backtests read it (load_ohlcv now prefers Parquet):

- `run_all.py`: add a sync step `[PY, 'convert_to_parquet.py', '--sync-all']` after the
  downloader steps and before the backtests in the data-update path. Simplest correct
  placement: a dedicated early pipeline group run right after the three OHLCV downloaders
  have populated CSVs, before `momentum_edge_backtest.py` / `ipo_edge_backtest.py`.
- `refresh_data.bat`: add `"%PY%" convert_to_parquet.py --sync-all` after the
  `nse_bse_downloader.py` step and before `momentum_edge_backtest.py` (renumber the
  step labels accordingly).
- One-time seed: `python convert_to_parquet.py --backfill-all`.

## Error Handling

- Corrupt/short CSV → `load_single` returns `None` → skipped + logged; `min_bars`
  enforced on the parquet path too.
- Missing/partial Parquet store → `has_store` false (or query error) → CSV fallback.
- Manifest mtime mismatch / missing ticker entry → reconvert that ticker on next sync.
- Manifest write is atomic (temp + `os.replace`) to survive interruption.
- Empty dataset or empty whitelist → empty dict (matches current behavior).
- Write-time schema guard: tz-naive Date, ascending sort, OHLCV dtypes, drop NaN Close.

## Testing

`tests/test_store.py` and `tests/test_convert_to_parquet.py` (pure, use `tmp_path`; no network):

1. **Equivalence gate (critical):** synthetic CSV dir → backfill → `store.load_ohlcv_parquet`
   returns the same ticker set, DataFrame shapes, index, and values (within float tol) as
   `data_io.load_ohlcv` on the same CSVs.
2. **Fast-path parity:** with a store present, `data_io.load_ohlcv(folder)` equals the CSV
   result; with no store, it uses CSV — both verified.
3. **backfill:** CSVs → `ticker=<T>/bars.parquet` exists, schema + values correct,
   `_manifest.json` written with mtimes.
4. **sync idempotency:** second `sync` converts 0; touching one CSV (newer mtime) reconverts
   only that ticker and updates only its manifest entry.
5. **get_bars filters:** `tickers`, `start`, `end`, `cols` each restrict output correctly;
   tidy shape (`ticker, Date, ...`).
6. **skip / whitelist / min_bars** honored on the parquet path (parity with CSV loader).
7. **benchmark:** `load_benchmark` still resolves `^NSEI`/`NIFTYBEES.NS` (CSV path
   unaffected; benchmark stays CSV in S0a unless its dataset has a store).
8. **perf sanity:** on a synthetic multi-ticker set, parquet load wall-time < CSV load
   wall-time (loose assert, not a fixed threshold — guards against accidental regression).

## Out of Scope (YAGNI / deferred)

- Cloud: GitHub Actions nightly, Cloudflare R2 publish, D1/Workers → **S0b**.
- Polars compute-hotpath refactor → separate optimization; the IO win does not need it.
- `data/` Nifty-50 close-only CSVs (50 files, `Date,<ticker>` schema, already fast via
  `core.rotation_trades`) → stay CSV.
- Rewriting downloaders to write Parquet natively → **S0b**.
- Deleting Parquet for tickers whose CSV disappeared → not needed yet.
- DuckDB-WASM / browser-side queries → frontend phase.

## Success Criteria

- `convert_to_parquet.py --backfill-all` then `--sync-all` produce a populated, manifest-tracked
  Parquet store for the three datasets without error.
- With the store present, `data_io.load_ohlcv('data/nse_bse')` returns results identical to the
  pre-change CSV load (verified by the equivalence/parity tests) and measurably faster.
- The full existing test suite still passes (no regressions); the dashboard and backtests run
  unchanged against the new fast-path.
- Removing/renaming `data/parquet/` cleanly reverts to CSV behavior (fallback verified).
