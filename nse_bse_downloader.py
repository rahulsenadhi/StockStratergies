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
import time
import datetime
import requests
import pandas as pd
import yfinance as yf
from io import StringIO
from pathlib import Path

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
BATCH_SIZE       = 50           # symbols per yf.download() call
BATCH_SLEEP      = 2.0          # seconds between batch calls
SYMBOL_SLEEP     = 0.5          # seconds between individual retry downloads
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


def _standardize(df: pd.DataFrame) -> pd.DataFrame | None:
    """
    Normalise a raw yfinance DataFrame:
    - Flatten MultiIndex columns
    - Ensure Date index → Date column
    - Keep only OHLCV columns
    - Drop rows where Close is NaN
    - Return None if result is empty
    """
    if df is None or df.empty:
        return None

    # Flatten MultiIndex (single-ticker batch returns flat; belt-and-suspenders)
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = [col[0] if col[0] else col[1] for col in df.columns]

    df = df.reset_index()
    # yfinance names the date column 'Date' or 'Datetime' depending on version
    for date_col in ('Date', 'Datetime', 'index'):
        if date_col in df.columns:
            df = df.rename(columns={date_col: 'Date'})
            break

    required = {'Open', 'High', 'Low', 'Close', 'Volume'}
    if not required.issubset(df.columns):
        return None

    keep = [c for c in ['Date', 'Open', 'High', 'Low', 'Close', 'Volume'] if c in df.columns]
    df = df[keep].copy()
    df['Date'] = pd.to_datetime(df['Date']).dt.date
    df = df.dropna(subset=['Close']).drop_duplicates(subset='Date').sort_values('Date')
    df = df.reset_index(drop=True)
    return df if len(df) >= MIN_ROWS else None


def _merge_with_existing(new_df: pd.DataFrame, existing_path: Path) -> pd.DataFrame:
    """Append new rows to an existing CSV, dedup by Date, return merged."""
    try:
        existing = pd.read_csv(existing_path)
        existing['Date'] = pd.to_datetime(existing['Date']).dt.date
        merged = pd.concat([existing, new_df], ignore_index=True)
        merged = merged.drop_duplicates(subset='Date').sort_values('Date').reset_index(drop=True)
        return merged
    except Exception:
        return new_df


def _save(df: pd.DataFrame, path: Path) -> bool:
    try:
        df.to_csv(path, index=False)
        return True
    except Exception:
        return False


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
            df = _standardize(raw)
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
            df = _standardize(ticker_df)
            if df is not None:
                results[sym] = df
        except Exception:
            continue

    return results


def download_batch(symbols: list[str], period: str) -> dict[str, pd.DataFrame]:
    """
    Download a list of symbols in one yf.download() call.
    Returns {symbol: cleaned_DataFrame} for every successful symbol.
    """
    if not symbols:
        return {}
    try:
        raw = yf.download(
            symbols,
            period=period,
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

def download_single(symbol: str, period: str) -> pd.DataFrame | None:
    """
    Download one symbol individually with try/except.
    Returns a cleaned DataFrame or None on any failure.
    """
    try:
        raw = yf.download(
            symbol,
            period=period,
            interval='1d',
            auto_adjust=True,
            progress=False,
        )
        return _standardize(raw)
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
    print(f'  Downloading benchmark {sym} ...')
    df = download_single(sym, '10y')
    if df is not None and not df.empty:
        _save(df, path)
        print(f'  Benchmark saved: {path}  ({len(df)} rows)')
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

    # ── Phase 2: separate fresh vs needs-download ─────────────────────────────
    fresh_syms:    list[str] = []
    full_syms:     list[str] = []   # file missing → download full 10y
    stale_syms:    list[str] = []   # file exists but old → append 60d

    for sym in all_symbols:
        path = data_folder / f'{sym}.csv'
        if _is_fresh(path):
            fresh_syms.append(sym)
        elif path.exists():
            stale_syms.append(sym)
        else:
            full_syms.append(sym)

    print(f'  Fresh (skip)   : {len(fresh_syms)}')
    print(f'  Full download  : {len(full_syms)}')
    print(f'  Update (stale) : {len(stale_syms)}')

    status_rows: list[dict] = []
    failed_syms: list[str] = []    # collected across both passes

    t_start = time.time()

    # helper: run batches for a symbol list and period
    def _run_batches(syms: list[str], period: str, mode: str) -> None:
        nonlocal failed_syms
        n_ok = n_fail = done = 0
        batches = [syms[i:i + BATCH_SIZE] for i in range(0, len(syms), BATCH_SIZE)]
        n_batches = len(batches)

        for b_idx, batch in enumerate(batches, start=1):
            label = batch[0] if batch else ''
            _bar(done, len(syms), label, n_ok, n_fail)

            results = download_batch(batch, period)

            for sym in batch:
                path = data_folder / f'{sym}.csv'
                df = results.get(sym)

                if df is not None:
                    # Merge with existing for stale updates
                    if mode == 'stale' and path.exists():
                        df = _merge_with_existing(df, path)

                    if len(df) >= MIN_ROWS and _save(df, path):
                        status_rows.append({
                            'Symbol': sym, 'Status': 'SUCCESS',
                            'Rows': len(df),
                            'LastDate': str(df['Date'].iloc[-1]),
                            'Mode': mode,
                        })
                        n_ok += 1
                    else:
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

    # ── Phase 3a: full downloads ──────────────────────────────────────────────
    if full_syms:
        print(f'\n  ── Pass 1/2: Full downloads ({len(full_syms)} symbols) ──')
        _run_batches(full_syms, f'{YEARS_HISTORY}y', 'full')

    # ── Phase 3b: stale updates ───────────────────────────────────────────────
    if stale_syms:
        print(f'\n  ── Pass 1/2: Stale updates ({len(stale_syms)} symbols) ──')
        _run_batches(stale_syms, '60d', 'stale')

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

            df = download_single(sym, f'{YEARS_HISTORY}y')
            if df is not None and len(df) >= MIN_ROWS and _save(df, path):
                # Update status_rows: replace last BATCH_FAILED entry for this sym
                for row in reversed(status_rows):
                    if row['Symbol'] == sym and row['Status'] in ('BATCH_FAILED', 'INSUFFICIENT_DATA'):
                        row['Status'] = 'SUCCESS'
                        row['Rows'] = len(df)
                        row['LastDate'] = str(df['Date'].iloc[-1])
                        break
                retry_ok += 1
            else:
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
