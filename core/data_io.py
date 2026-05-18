"""Unified OHLCV CSV loader.

Reuses the parallel ThreadPool pattern from momentum_edge_backtest.py and exposes
it to IPO Edge + Rotation backtests/dashboards. Backward compatible: returns the
same (ohlcv_dict, mtime_dict) shape that ME already uses.

API:
    load_ohlcv(folder, min_bars=10, skip=None, whitelist=None, workers=None)
    load_single(path)
    load_benchmark(folder, ticker_candidates)
"""

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

_DEFAULT_WORKERS = min(32, (os.cpu_count() or 4) * 2)
_OHLCV_COLS = ['Open', 'High', 'Low', 'Close', 'Volume']


def load_single(path: Path) -> pd.DataFrame | None:
    """Load one OHLCV CSV. Returns None on any failure."""
    try:
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        idx = pd.to_datetime(df.index, errors='coerce')
        if idx.tz is not None:
            idx = idx.tz_convert(None)
        df.index = idx
        df.index.name = 'Date'
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        needed = [c for c in _OHLCV_COLS if c in df.columns]
        if len(needed) < 5:
            return None
        df = df[needed].copy()
        df = df.dropna(subset=['Close'])
        df.sort_index(inplace=True)
        return df if len(df) >= 10 else None
    except Exception:
        return None


def _load_one(args: tuple):
    csv_file, min_bars, skip_stems, whitelist = args
    stem = csv_file.stem
    if stem in skip_stems:
        return None, None, 0.0
    if whitelist is not None and stem not in whitelist:
        return None, None, 0.0
    mtime = csv_file.stat().st_mtime
    df = load_single(csv_file)
    if df is not None and len(df) >= min_bars:
        return stem, df, mtime
    return None, None, 0.0


def load_ohlcv(
    folder: str | Path,
    min_bars: int = 10,
    skip: set[str] | None = None,
    whitelist: set[str] | None = None,
    workers: int | None = None,
    progress: bool = False,
) -> tuple[dict[str, pd.DataFrame], dict[str, float]]:
    """Load all *.csv in folder in parallel.

    Args:
        folder:    directory containing OHLCV CSVs
        min_bars:  drop tickers with fewer rows than this
        skip:      file stems to skip (e.g., {'^NSEI', 'NIFTYBEES.NS'})
        whitelist: if set, only load stems in this set
        workers:   thread pool size (default = 2× CPU count, capped 32)
        progress:  print progress every 500 symbols

    Returns:
        (ohlcv_dict, mtime_dict) — keyed by ticker stem.
    """
    folder = Path(folder)
    if not folder.exists():
        raise FileNotFoundError(f"Data folder '{folder}' not found.")

    skip_stems = skip or set()
    csv_files = sorted(folder.glob('*.csv'))
    total = len(csv_files)

    args_list = [(f, min_bars, skip_stems, whitelist) for f in csv_files]
    ohlcv: dict[str, pd.DataFrame] = {}
    mtimes: dict[str, float] = {}
    loaded = 0

    with ThreadPoolExecutor(max_workers=workers or _DEFAULT_WORKERS) as pool:
        for stem, df, mtime in pool.map(_load_one, args_list):
            if stem is not None:
                ohlcv[stem] = df
                mtimes[stem] = mtime
                loaded += 1
                if progress and loaded % 500 == 0:
                    print(f'  Loaded {loaded}/{total} symbols…', end='\r', flush=True)

    if progress:
        print(f'  Loaded {loaded} symbols from {folder}/' + ' ' * 20)
    return ohlcv, mtimes


def load_benchmark(
    folder: str | Path,
    ticker_candidates: list[str] | None = None,
    extra_paths: list[Path] | None = None,
) -> pd.Series | None:
    """Load benchmark Close series. Tries each ticker in folder, then extra_paths.

    Returns Close Series or None if nothing matches.
    """
    folder = Path(folder)
    candidates = ticker_candidates or ['^NSEI', 'NIFTYBEES.NS']
    paths_to_try: list[Path] = []
    for t in candidates:
        paths_to_try.append(folder / f'{t}.csv')
    if extra_paths:
        paths_to_try.extend(extra_paths)

    for path in paths_to_try:
        if path.exists():
            df = load_single(path)
            if df is not None and 'Close' in df.columns:
                return df['Close'].dropna()
    return None
