# S0b — Local Incremental Catch-Up Refresh: Design Spec

**Author:** rahulsenadhi
**Date:** 2026-06-04
**Status:** Draft
**Depends on:** S0a data layer (Parquet/DuckDB store + `convert_to_parquet.py --sync`)
**Supersedes (scope):** the original cloud-flavored S0b in the platform v2 roadmap — see "Deviation from roadmap" below.

---

## 1. Goal

When the PC has been off, turning it on and running the app should bring each strategy's data current **quickly**, fetching only the missing days — not re-downloading history. Add a per-strategy **Update** button and a launch **staleness banner** so the user controls refresh and page loads stay fast.

**Requirement (user, this session):** "I don't mind running on PC, provided I don't keep it on. When I turn it on and run, data must update accordingly — and quick."

## 2. Non-Goals

- **No cloud / R2 / GitHub Actions / VM** in S0b. Deferred (see roadmap). Local-only.
- **No auto-download on page load.** Launch shows a banner; the user clicks to update. Page loads stay < 2s (preserves the S0a win).
- **No full re-download of existing tickers.** Always gap-fetch. The only full fetch is initial backfill of a brand-new ticker (no CSV yet).
- **No change to backtest/precompute logic.** S0b only changes how raw bars are fetched + how refresh is triggered from the UI.

## 3. Current State (why this is needed)

| Downloader | Today's behavior |
|---|---|
| `step1_download_data.py` (Nifty 50) | Full range `start→end`, `to_csv` overwrite. No incremental. |
| `momentum_edge_downloader.py` | Full range, overwrite. No incremental. |
| `ipo_edge_downloader.py` | Full range, overwrite. No incremental. |
| `nse_bse_downloader.py` | **Has** staleness logic (mtime-based, "stale → append 60d") + `_standardize` / `_merge_with_existing` / `_save`. Most advanced. |
| `pead_downloader.py` | Already incremental (`append_events`). Out of scope to change. |

Problem: the gap-aware logic exists only inside `nse_bse_downloader.py`, is keyed on **file mtime + a fixed 60-day window** (crude), and the other three downloaders re-download full history every run. S0b generalizes a cleaner version into `core/` and makes all price downloaders use it.

## 4. Architecture

One new shared module + a small staleness helper + thin call-sites. No new infrastructure.

```
core/incremental.py        NEW — gap-aware fetch engine (the only substantial new code)
  last_stored_date(path)       read max(Date) from a ticker CSV (None if missing/empty)
  plan_fetch(path, today)      → FULL | GAP(start,end) | SKIP
  fetch_increment(...)         yf.download only the needed range (batched/threaded)
  merge_save(new_df, path)     standardize + append + dedup by Date + atomic write
  refresh_tickers(tickers,...) orchestrates plan→fetch→merge; returns {ticker: status}

core/staleness.py          NEW (small) — "is this dataset N trading-days behind?"
  dataset_staleness(folder)    latest stored bar vs last NSE trading day → days_behind, latest_date

step1_download_data.py     REFACTOR → call core.incremental.refresh_tickers
momentum_edge_downloader.py  REFACTOR → same
ipo_edge_downloader.py     REFACTOR → same
nse_bse_downloader.py      MIGRATE its bespoke incremental logic INTO core.incremental, then call it
                           (remove duplication; keep its symbol-list/batch-parse phases)

<dashboards>               ADD staleness banner + "Update [strategy]" button
  dashboard_visual.py (Monthly), ipo_edge_dashboard.py, momentum_edge_dashboard.py,
  master_dashboard.py (PEAD page)
```

**Boundaries:**
- `core/incremental.py` = single source of truth for "fetch only the gap." Independently testable with a fake fetch fn (no network).
- `core/staleness.py` = pure/testable (folder + injectable clock).
- Downloaders become thin (build ticker list → `refresh_tickers`). Each stays < ~150 lines.
- Post-refresh chain unchanged: `convert_to_parquet.py --sync <dataset>` (S0a, already incremental) → strategy precompute.

## 5. Fetch Logic (`core/incremental.py`)

### plan_fetch

```
plan_fetch(path, today):
    if not path.exists() or last_stored_date(path) is None:
        return FULL(start = today - FULL_LOOKBACK, end = today + 1)   # initial backfill only
    last = last_stored_date(path)
    if trading_days_between(last, today) <= 0:
        return SKIP                                                   # already current
    return GAP(start = last + 1 day, end = today + 1)                 # ALWAYS gap, any size
```

- **Staleness keyed on last stored bar Date**, not file mtime. PC off 5 days → fetch exactly those trading days. Same-day re-run → SKIP.
- **Always-gap, no threshold.** Existing tickers always gap-fetch regardless of gap size. FULL happens only when there is no CSV (new ticker initial backfill).
- **`end = today + 1`** — yfinance `end` is exclusive (existing downloaders already do `end + timedelta(days=1)`).
- **Trading-day aware.** `trading_days_between` excludes weekends (and holidays if a holiday list is already available in the codebase; otherwise weekday approximation — an empty fetch on a holiday is a harmless no-op, see §7). Saturday with Friday's bar present → SKIP (0 trading days behind), not "1 behind."

Constant: `FULL_LOOKBACK` (initial backfill window, e.g. ~10y; reuse each downloader's existing history span).

### refresh_tickers

- Classify all tickers via `plan_fetch` → SKIP set never touches the network (this is what makes catch-up fast).
- Batch GAP+FULL tickers through `yf.download(group_by='ticker')` (reuse `nse_bse` `BATCH_SIZE` + `_parse_batch_result`), threaded across batches.
- Each result → `merge_save`.
- Returns `{ticker: status}`, status ∈ `skipped | gap_appended(n) | full(n) | failed(reason)`. Caller logs counts.

### merge_save

- Lift `_standardize` (flatten MultiIndex, OHLCV-only, drop NaN-Close, dedup Date, `MIN_ROWS`) and `_merge_with_existing` (concat + dedup by Date + sort) from `nse_bse_downloader.py` into `core/incremental.py`.
- **Atomic write:** write temp file → `os.replace` (same pattern as S0a manifest). A crash mid-write cannot corrupt a good CSV.
- Idempotent: re-running the same day appends nothing new (dedup by Date) → file byte-identical.

## 6. UI — Staleness Banner + Update Button

Added to each strategy dashboard (Monthly, IPO, Momentum, PEAD page).

```
┌─ data status banner (top of page) ──────────────────────────┐
│ ⚠ Data 3 trading days behind (latest: 2026-05-30)  [Update now] │
└──────────────────────────────────────────────────────────────┘
```

- Banner driven by `core.staleness.dataset_staleness(folder)`:
  - `0 behind` → small green "✓ Up to date (YYYY-MM-DD)", no nag, no button.
  - `≥1 behind` → amber warning + **[Update now]** button.
- **[Update now]** calls a per-strategy entrypoint `refresh_strategy(name)`:
  1. `refresh_tickers(strategy_tickers)` — gap only,
  2. `convert_to_parquet.py --sync <dataset>` (if the strategy uses the Parquet store),
  3. that strategy's precompute (e.g. `precompute_momentum_signals.py`, `precompute_exit_recommendations.py`).
  - Wrapped in `st.status()` with live step text ("Fetching 3 days for 48 tickers… syncing Parquet… precomputing…").
  - On success → `st.cache_data.clear()` + `st.rerun()` so the page shows fresh data.
- **Launch = banner only.** Opening a page detects staleness cheaply (one max-Date read per dataset) and renders the banner. It never auto-downloads. Page loads stay < 2s.
- **Concurrency guard:** `st.session_state` flag (+ optional lockfile) so a double-click can't launch two overlapping fetches into the same CSVs. Released in `finally`.

## 7. Error Handling

- **Per-ticker isolation.** A single ticker failing (timeout, empty, malformed) → caught, recorded `failed(reason)`, batch continues. Matches current downloader behavior.
- **Empty gap return = success/no-op.** yf returning nothing (non-trading day, lag) → SKIP, CSV untouched. This is also the holiday safety net for the weekday approximation.
- **Atomic merge guards the file.** Merge throws → keep old CSV, mark ticker failed. No partial-corrupt state.
- **Network-wide failure** (all tickers error → yf/NSE down or blocked): `refresh_strategy` surfaces a clear banner error ("Update failed: N/N tickers errored — likely network/Yahoo. Data unchanged.") and leaves data as-was.
- **UI:** errors caught in the `st.status` block → red message + per-ticker failure count; data left intact; lock released in `finally`.
- **Boundary validation:** reuse `_standardize` (OHLCV columns, NaN-Close drop, `MIN_ROWS`) — reject a malformed fetched frame rather than appending garbage.

## 8. Testing

All unit-testable with **no network** (inject a fake fetch fn into `refresh_tickers`).

| Test | Asserts |
|---|---|
| `plan_fetch` no file | → FULL (initial backfill range) |
| `plan_fetch` last bar = today | → SKIP |
| `plan_fetch` last bar = today − 5 trading days | → GAP(last+1, today+1) |
| `plan_fetch` Sat/Sun with Fri data | → SKIP (trading-day aware) |
| `merge_save` overlapping rows | append + dedup by Date, sorted, no dupes |
| `merge_save` idempotent | re-run same day → file byte-identical |
| `merge_save` crash before replace | original CSV intact (atomic temp) |
| `refresh_tickers` one ticker throws | others still saved; status map correct |
| `refresh_tickers` empty gap return | SKIP; file untouched |
| `dataset_staleness` weekend | correct trading-days-behind |
| integration | gap-appended CSV → `--sync` → Parquet store reflects new rows |

- Coverage target **≥80%** on `core/incremental.py` + `core/staleness.py`.
- Downloader refactors verified by an existing-pipeline smoke run (`python run_all.py --data-only`) + spot-check appended dates.

## 9. Deviation from Roadmap

The platform v2 roadmap listed S0b as "Cloud (GitHub Actions nightly, R2, Cloudflare)." During this session the user's hard requirement changed to **local, PC-on-demand, fast catch-up, no always-on PC**. Evaluated OCI Always-Free VM and GCP free tier (both genuinely $0; OCI far roomier at 4 OCPU/24 GB vs GCP e2-micro 1 GB) and pure-GitHub-Actions; all were rejected for S0b because the requirement is satisfied better locally with zero infra, zero IP-block risk, and zero monthly fragility. Cloud (R2 publish, remote viewing, VM/Actions) is **deferred** to a later subsystem and revisited only if remote access is wanted. Roadmap memory to be updated accordingly.

## 10. Open Questions

| Question | Resolution |
|---|---|
| Holiday calendar source for `trading_days_between`? | Use an existing holiday list if the codebase already has one; else weekday approximation — empty holiday fetch is a harmless no-op (§7). Confirm during plan. |
| `FULL_LOOKBACK` per strategy? | Reuse each downloader's current history span (don't change history depth). |
| Should `nse_bse`'s `STALE_DAYS` mtime fast-skip be kept as an optimization layer? | Optional: keep an mtime pre-filter to avoid reading max-Date on thousands of files, then confirm with `last_stored_date`. Decide during plan (perf vs simplicity). |
