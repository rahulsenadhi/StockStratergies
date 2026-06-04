"""
nse_bse_downloader.py
---------------------
Downloads 10 years of OHLCV data for all NSE + BSE symbols.

Pipeline:
  Phase 1 — Load symbol universe (combined_universe.csv or direct NSE fetch)
  Phase 2 — Skip fresh files (< 1 day old)
  Phase 3 — Batch download: 50 symbols at a time via yf.download(group_by='ticker')
  Phase 4 — Retry every failure individually with 0.5s sleep
  Phase 5 — Benchmark (^NSEI) + save status/failed CSVs

Run order:
  python nse_bse_downloader.py          # full run
  python build_universe.py              # optional: pre-build combined universe first
"""

import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
import time
import datetime
import requests
import pandas as pd
import yfinance as yf
from io import StringIO
from pathlib import Path

from core import incremental

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────

UNIVERSE_FILE    = './data/universe/combined_universe.csv'
DATA_FOLDER      = './data/nse_bse'
YEARS_HISTORY    = 10           # 10y needed for backtest indicators (220-EMA etc.)
STALE_DAYS       = 1            # skip re-download if file modified < 1 day ago
MIN_ROWS         = 100          # discard stocks with fewer rows than this
BATCH_SIZE       = 100          # symbols per yf.download() call
BATCH_SLEEP      = 1.0          # seconds between batch calls
SYMBOL_SLEEP     = 0.3          # seconds between individual retry downloads
BENCHMARK_SYM    = '^NSEI'

NSE_URL = 'https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv'

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 1 — SYMBOL UNIVERSE
# ─────────────────────────────────────────────────────────────────────────────

def _fetch_nse_symbols() -> list[str]:
    """Download NSE EQ-series symbol list and return yfinance tickers (SYM.NS)."""
    print('  Fetching NSE symbol list from nseindia.com ...')
    try:
        resp = requests.get(NSE_URL, headers={'User-Agent': 'Mozilla/5.0'}, timeout=30)
        resp.raise_for_status()
        df = pd.read_csv(StringIO(resp.text))
        df.columns = [c.strip() for c in df.columns]
        df = df[df['SERIES'].str.strip() == 'EQ']
        symbols = [s.strip() + '.NS' for s in df['SYMBOL'].dropna()]
        print(f'  NSE symbols fetched: {len(symbols)}')
        return symbols
    except Exception as e:
        print(f'  ERROR fetching NSE list: {e}')
        return []


def load_symbols() -> list[str]:
    """
    Load symbol list from combined_universe.csv if it exists,
    otherwise fall back to fetching NSE directly.
    """
    upath = Path(UNIVERSE_FILE)
    if upath.exists():
        try:
            df = pd.read_csv(upath)
            syms = df['Symbol'].dropna().unique().tolist()
            print(f'  Loaded {len(syms)} symbols from {upath}')
            return syms
        except Exception as e:
            print(f'  WARNING: could not read {upath}: {e}')

    print(f'  combined_universe.csv not found — falling back to NSE direct fetch.')
    print(f'  (Run build_universe.py once to get the full NSE + BSE universe.)')
    return _fetch_nse_symbols()


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _is_fresh(path: Path) -> bool:
    """True if the file exists and was modified less than STALE_DAYS ago."""
    if not path.exists():
        return False
    age = (datetime.datetime.now() - datetime.datetime.fromtimestamp(path.stat().st_mtime))
    return age.total_seconds() / 86400 < STALE_DAYS


# Standardize / merge / save now live in core.incremental:
#   incremental.standardize(df)        — normalise a raw yfinance frame
#   incremental.merge_save(df, path)   — standardize + merge + dedup + atomic write


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 3 — BATCH DOWNLOAD
# ─────────────────────────────────────────────────────────────────────────────

def _parse_batch_result(
    raw: pd.DataFrame,
    symbols: list[str],
) -> dict[str, pd.DataFrame]:
    """
    Parse the DataFrame returned by yf.download(list, group_by='ticker').

    yfinance returns:
      - MultiIndex columns (ticker, field) when len(symbols) > 1
      - Flat columns (field)               when len(symbols) == 1
    """
    results: dict[str, pd.DataFrame] = {}
    if raw is None or raw.empty:
        return results

    if not isinstance(raw.columns, pd.MultiIndex):
        # Single-symbol batch — raw IS the ticker's DataFrame
        if len(symbols) == 1:
            df = incremental.standardize(raw)
            if df is not None:
                results[symbols[0]] = df
        return results

    # MultiIndex: level 0 = ticker when group_by='ticker'
    top = set(raw.columns.get_level_values(0))
    for sym in symbols:
        if sym not in top:
            continue
        try:
            ticker_df = raw[sym].copy()
            df = incremental.standardize(ticker_df)
            if df is not None:
                results[sym] = df
        except Exception:
            continue

    return results


def download_batch(
    symbols: list[str],
    start: datetime.date,
    end: datetime.date,
) -> dict[str, pd.DataFrame]:
    """
    Download a list of symbols in one yf.download() call over [start, end).
    `end` is exclusive (yfinance convention, supplied by plan_fetch).
    Returns {symbol: cleaned_DataFrame} for every successful symbol.
    """
    if not symbols:
        return {}
    try:
        raw = yf.download(
            symbols,
            start=str(start),
            end=str(end),
            interval='1d',
            group_by='ticker',
            auto_adjust=True,
            threads=True,
            progress=False,
        )
        return _parse_batch_result(raw, symbols)
    except Exception as e:
        print(f'\n  Batch error ({len(symbols)} symbols): {e}')
        return {}


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 4 — INDIVIDUAL RETRY
# ─────────────────────────────────────────────────────────────────────────────

def download_single(
    symbol: str,
    start: datetime.date,
    end: datetime.date,
) -> pd.DataFrame | None:
    """
    Download one symbol individually over [start, end) with try/except.
    `end` is exclusive. Returns a cleaned DataFrame or None on any failure.
    """
    try:
        raw = yf.download(
            symbol,
            start=str(start),
            end=str(end),
            interval='1d',
            auto_adjust=True,
            progress=False,
        )
        return incremental.standardize(raw)
    except Exception as e:
        if '429' in str(e):
            print(f'\n  Rate-limit (429) on {symbol} — waiting 60s ...', flush=True)
            time.sleep(60)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# BENCHMARK
# ─────────────────────────────────────────────────────────────────────────────

def download_benchmark(data_folder: Path) -> None:
    sym = BENCHMARK_SYM
    path = data_folder / f'{sym}.csv'
    if _is_fresh(path):
        print(f'  Benchmark {sym}: fresh, skipping.')
        return
    today = datetime.date.today()
    plan = incremental.plan_fetch(path, today)
    if plan.kind == 'skip':
        print(f'  Benchmark {sym}: up to date, skipping.')
        return
    print(f'  Downloading benchmark {sym} ...')
    df = download_single(sym, plan.start, plan.end)
    added = incremental.merge_save(df, path)
    if added >= 0:
        print(f'  Benchmark saved: {path}  (+{added} rows)')
    else:
        print(f'  WARNING: benchmark {sym} download failed.')


# ─────────────────────────────────────────────────────────────────────────────
# PROGRESS
# ─────────────────────────────────────────────────────────────────────────────

def _bar(done: int, total: int, label: str, n_ok: int, n_fail: int) -> None:
    pct = done / total if total else 0
    filled = int(pct * 20)
    bar = '█' * filled + '░' * (20 - filled)
    pct_str = f'{pct * 100:.0f}%'
    print(
        f'\r  [{bar}] {pct_str}  {done}/{total}  '
        f'OK:{n_ok}  Fail:{n_fail}  {label[:28]:<28}',
        end='', flush=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    print('=' * 60)
    print('  NSE + BSE Historical Data Downloader')
    print('=' * 60)

    data_folder = Path(DATA_FOLDER)
    data_folder.mkdir(parents=True, exist_ok=True)

    # ── Phase 1: symbol list ──────────────────────────────────────────────────
    all_symbols = load_symbols()
    if not all_symbols:
        print('ERROR: no symbols to download. Exiting.')
        sys.exit(1)

    total = len(all_symbols)
    print(f'\n  Total symbols  : {total}')

    # ── Phase 2: classify via plan_fetch (skip / gap / full) ──────────────────
    # _is_fresh is a cheap mtime pre-filter: if the CSV was just written we skip
    # the (more expensive) max-Date read inside plan_fetch.
    today = datetime.date.today()
    fresh_syms: list[str] = []
    full_syms:  list[str] = []   # no CSV yet → full backfill window
    # stale symbols carry their per-symbol gap start (from plan_fetch)
    gap_starts: dict[str, datetime.date] = {}
    gap_end:    datetime.date | None = None

    for sym in all_symbols:
        path = data_folder / f'{sym}.csv'
        if _is_fresh(path):
            fresh_syms.append(sym)
            continue
        plan = incremental.plan_fetch(path, today)
        if plan.kind == 'skip':
            fresh_syms.append(sym)
        elif plan.kind == 'full':
            full_syms.append(sym)
        else:  # gap
            gap_starts[sym] = plan.start
            gap_end = plan.end

    stale_syms = list(gap_starts.keys())

    print(f'  Fresh (skip)   : {len(fresh_syms)}')
    print(f'  Full download  : {len(full_syms)}')
    print(f'  Update (stale) : {len(stale_syms)}')

    status_rows: list[dict] = []
    failed_syms: list[str] = []    # collected across both passes

    t_start = time.time()

    # helper: run batches for a symbol list over [start, end) (end exclusive).
    # When per-symbol starts differ (gap pass), the caller passes the minimum
    # start; over-fetching is harmless — merge_save dedups by Date per symbol.
    def _run_batches(syms: list[str], start: datetime.date,
                     end: datetime.date, mode: str) -> None:
        nonlocal failed_syms
        n_ok = n_fail = done = 0
        batches = [syms[i:i + BATCH_SIZE] for i in range(0, len(syms), BATCH_SIZE)]
        n_batches = len(batches)

        for b_idx, batch in enumerate(batches, start=1):
            label = batch[0] if batch else ''
            _bar(done, len(syms), label, n_ok, n_fail)

            results = download_batch(batch, start, end)

            for sym in batch:
                path = data_folder / f'{sym}.csv'
                df = results.get(sym)

                if df is not None:
                    # Capture brand-new status BEFORE merge_save so we can clean
                    # up a partial CSV that never met MIN_ROWS (mirrors
                    # core/incremental.py refresh_tickers._one).
                    existed = path.exists()
                    # merge_save standardizes (no-op here), merges with any
                    # existing CSV, dedups by Date, and writes atomically.
                    added = incremental.merge_save(df, path)
                    rows = 0
                    if added >= 0:
                        try:
                            rows = len(pd.read_csv(path, usecols=['Date']))
                        except Exception:
                            rows = 0

                    if added >= 0 and rows >= MIN_ROWS:
                        status_rows.append({
                            'Symbol': sym, 'Status': 'SUCCESS',
                            'Rows': rows,
                            'LastDate': str(incremental.last_stored_date(path) or 'N/A'),
                            'Mode': mode,
                        })
                        n_ok += 1
                    else:
                        # Brand-new symbol below MIN_ROWS: delete the partial CSV
                        # so it neither pollutes the universe nor gets re-fetched
                        # as a phantom gap on the next run.
                        if not existed:
                            Path(path).unlink(missing_ok=True)
                        failed_syms.append(sym)
                        status_rows.append({'Symbol': sym, 'Status': 'INSUFFICIENT_DATA', 'Mode': mode})
                        n_fail += 1
                else:
                    failed_syms.append(sym)
                    status_rows.append({'Symbol': sym, 'Status': 'BATCH_FAILED', 'Mode': mode})
                    n_fail += 1

                done += 1

            _bar(done, len(syms), label, n_ok, n_fail)

            if b_idx < n_batches:
                time.sleep(BATCH_SLEEP)

        print()  # newline after progress bar

    full_start = today - datetime.timedelta(days=incremental.FULL_LOOKBACK_DAYS)
    full_end   = today + datetime.timedelta(days=1)

    # ── Phase 3a: full downloads ──────────────────────────────────────────────
    if full_syms:
        print(f'\n  ── Pass 1/2: Full downloads ({len(full_syms)} symbols) ──')
        _run_batches(full_syms, full_start, full_end, 'full')

    # ── Phase 3b: stale updates (gap fetch) ───────────────────────────────────
    if stale_syms:
        # one batch window = earliest gap start across the pass; per-symbol
        # over-fetch is deduped on merge.
        batch_start = min(gap_starts.values())
        print(f'\n  ── Pass 1/2: Stale updates ({len(stale_syms)} symbols) ──')
        _run_batches(stale_syms, batch_start, gap_end, 'stale')

    # ── Phase 3c: fresh skips ─────────────────────────────────────────────────
    for sym in fresh_syms:
        path = data_folder / f'{sym}.csv'
        try:
            rows = len(pd.read_csv(path))
        except Exception:
            rows = 0
        status_rows.append({'Symbol': sym, 'Status': 'SKIPPED', 'Rows': rows, 'Mode': 'fresh'})

    # ── Phase 4: retry failures individually ─────────────────────────────────
    if failed_syms:
        print(f'\n  ── Pass 2/2: Retry {len(failed_syms)} failed symbols individually ──')
        retry_ok = retry_fail = 0
        for i, sym in enumerate(failed_syms, start=1):
            print(f'\r  Retry {i}/{len(failed_syms)}: {sym:<30}', end='', flush=True)
            path = data_folder / f'{sym}.csv'

            # Capture brand-new status BEFORE merge_save (see batch pass).
            existed = path.exists()
            # Retry always re-fetches the full window so a missing CSV can be
            # backfilled; merge_save dedups against anything already present.
            df = download_single(sym, full_start, full_end)
            added = incremental.merge_save(df, path)
            rows = 0
            if added >= 0:
                try:
                    rows = len(pd.read_csv(path, usecols=['Date']))
                except Exception:
                    rows = 0
            if added >= 0 and rows >= MIN_ROWS:
                # Update status_rows: replace last BATCH_FAILED entry for this sym
                for row in reversed(status_rows):
                    if row['Symbol'] == sym and row['Status'] in ('BATCH_FAILED', 'INSUFFICIENT_DATA'):
                        row['Status'] = 'SUCCESS'
                        row['Rows'] = rows
                        row['LastDate'] = str(incremental.last_stored_date(path) or 'N/A')
                        break
                retry_ok += 1
            else:
                # Brand-new symbol that never reached MIN_ROWS: delete the
                # partial CSV so it doesn't pollute the universe or become a
                # phantom gap on the next run.
                if not existed:
                    Path(path).unlink(missing_ok=True)
                # Final failure — keep as FAILED
                for row in reversed(status_rows):
                    if row['Symbol'] == sym and row['Status'] in ('BATCH_FAILED', 'INSUFFICIENT_DATA'):
                        row['Status'] = 'FAILED'
                        break
                retry_fail += 1

            time.sleep(SYMBOL_SLEEP)

        print(f'\n  Retry results: {retry_ok} recovered, {retry_fail} still failed')

    # ── Benchmark ─────────────────────────────────────────────────────────────
    print()
    download_benchmark(data_folder)

    # ── Save status CSV ───────────────────────────────────────────────────────
    status_df = pd.DataFrame(status_rows)
    status_path = data_folder / 'download_status.csv'
    status_df.to_csv(status_path, index=False)

    # Save failed symbols separately
    final_failed = status_df[status_df['Status'] == 'FAILED']['Symbol'].tolist()
    if final_failed:
        failed_path = data_folder / 'failed_symbols.csv'
        pd.DataFrame({'Symbol': final_failed}).to_csv(failed_path, index=False)
        print(f'  Failed symbols saved: {failed_path}  ({len(final_failed)} symbols)')

    # ── Summary ───────────────────────────────────────────────────────────────
    elapsed_min = (time.time() - t_start) / 60
    n_success   = len(status_df[status_df['Status'] == 'SUCCESS'])
    n_skipped   = len(status_df[status_df['Status'] == 'SKIPPED'])
    n_failed    = len(status_df[status_df['Status'] == 'FAILED'])
    n_insuf     = len(status_df[status_df['Status'] == 'INSUFFICIENT_DATA'])

    print('\n' + '─' * 40)
    print('  Download Complete')
    print('─' * 40)
    print(f'  Total symbols      : {total}')
    print(f'  Successful         : {n_success}')
    print(f'  Skipped (fresh)    : {n_skipped}')
    print(f'  Failed (final)     : {n_failed}')
    print(f'  Insufficient data  : {n_insuf}')
    print(f'  Time elapsed       : {elapsed_min:.1f} min')
    print('─' * 40)


if __name__ == '__main__':
    main()
