# core/incremental.py
"""Gap-aware incremental OHLCV fetch engine (S0b).

Single source of truth for "fetch only the missing trading days" — generalizes
the incremental logic that previously lived inside nse_bse_downloader.py.
"""
from __future__ import annotations

import datetime as dt
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

OHLCV = ["Open", "High", "Low", "Close", "Volume"]
MIN_ROWS = 100                 # discard brand-new tickers with fewer rows than this
FULL_LOOKBACK_DAYS = 365 * 10  # initial backfill window for a never-seen ticker


def last_stored_date(path) -> dt.date | None:
    """Return max(Date) in a ticker CSV, or None if missing/empty/unreadable."""
    p = Path(path)
    if not p.exists():
        return None
    try:
        df = pd.read_csv(p, usecols=["Date"])
    except (ValueError, pd.errors.EmptyDataError, OSError):
        return None
    if df.empty:
        return None
    result = pd.to_datetime(df["Date"]).dt.date.max()
    return None if pd.isna(result) else result


def trading_days_between(last: dt.date, today: dt.date) -> int:
    """Business days strictly after `last` up to and including `today` (>=0).

    Weekend-aware via numpy busday_count (which treats Sat/Sun as non-business).
    Holidays are not modeled here; an empty fetch on a holiday is a harmless no-op.
    """
    if today <= last:
        return 0
    return int(np.busday_count(last + dt.timedelta(days=1), today + dt.timedelta(days=1)))


@dataclass(frozen=True)
class FetchPlan:
    kind: str                       # "full" | "gap" | "skip"
    start: dt.date | None = None
    end: dt.date | None = None      # exclusive (yfinance convention)


def plan_fetch(path, today: dt.date, full_lookback_days: int = FULL_LOOKBACK_DAYS) -> FetchPlan:
    """Decide what to fetch for one ticker.

    - No CSV yet            -> FULL (initial backfill).
    - Already current       -> SKIP.
    - Otherwise             -> GAP (always gap, any size; never auto-full an existing ticker).
    """
    last = last_stored_date(path)
    if last is None:
        start = today - dt.timedelta(days=full_lookback_days)
        return FetchPlan("full", start, today + dt.timedelta(days=1))
    if trading_days_between(last, today) <= 0:
        return FetchPlan("skip")
    return FetchPlan("gap", last + dt.timedelta(days=1), today + dt.timedelta(days=1))


def standardize(df: pd.DataFrame | None) -> pd.DataFrame | None:
    """Normalize a raw yfinance frame to Date,O,H,L,C,V. None if empty/invalid.

    Note: no minimum-row gate here (gap fetches return few rows); MIN_ROWS is
    enforced only for brand-new tickers in refresh_tickers.
    """
    if df is None or getattr(df, "empty", True):
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = [c[0] if c[0] else c[1] for c in df.columns]
    df = df.reset_index()
    for date_col in ("Date", "Datetime", "index"):
        if date_col in df.columns:
            df = df.rename(columns={date_col: "Date"})
            break
    if not {"Open", "High", "Low", "Close", "Volume"}.issubset(df.columns):
        return None
    keep = [c for c in ["Date"] + OHLCV if c in df.columns]
    df = df[keep].copy()
    df["Date"] = pd.to_datetime(df["Date"]).dt.date
    df = (df.dropna(subset=["Close"])
            .drop_duplicates(subset="Date")
            .sort_values("Date")
            .reset_index(drop=True))
    return df if len(df) else None


def merge_save(new_df: pd.DataFrame | None, path) -> int:
    """Standardize new_df, append into CSV at path (dedup by Date), atomic write.

    Returns count of NEW rows added (>=0), or -1 if new_df is empty/invalid.
    Idempotent: if nothing new, the file is left byte-identical (no rewrite).
    """
    std = standardize(new_df)
    if std is None:
        return -1
    p = Path(path)
    before = 0
    merged = std
    if p.exists():
        try:
            existing = pd.read_csv(p)
            existing["Date"] = pd.to_datetime(existing["Date"]).dt.date
            before = len(existing)
            merged = (pd.concat([existing, std], ignore_index=True)
                        .drop_duplicates(subset="Date")
                        .sort_values("Date")
                        .reset_index(drop=True))
            if len(merged) == before:
                return 0                      # nothing new -> don't touch the file
        except Exception:
            before = 0
            merged = std    # corrupt/unreadable existing CSV -> overwrite with fresh data
    tmp = p.with_suffix(".csv.tmp")
    merged.to_csv(tmp, index=False)
    os.replace(tmp, p)                        # atomic; crash before this keeps old CSV
    return len(merged) - before


from concurrent.futures import ThreadPoolExecutor
from typing import Callable

FetchFn = Callable[[str, dt.date, dt.date], pd.DataFrame]


def refresh_tickers(
    tickers,
    data_folder,
    today: dt.date,
    fetch_fn: FetchFn,
    *,
    max_workers: int = 8,
    min_rows_new: int = MIN_ROWS,
) -> dict[str, str]:
    """Plan -> fetch (only non-skip tickers) -> merge_save. Per-ticker isolated.

    fetch_fn(ticker, start, end) -> raw OHLCV DataFrame (end exclusive).
    Returns {ticker: "skipped" | "gap_appended(n)" | "full(n)" | "failed(reason)"}.
    """
    folder = Path(data_folder)
    folder.mkdir(parents=True, exist_ok=True)

    status: dict[str, str] = {}
    to_fetch: list[tuple[str, FetchPlan]] = []
    for t in tickers:
        plan = plan_fetch(folder / f"{t}.csv", today)
        if plan.kind == "skip":
            status[t] = "skipped"
        else:
            to_fetch.append((t, plan))

    def _one(item):
        ticker, plan = item
        path = folder / f"{ticker}.csv"
        existed = path.exists()
        try:
            raw = fetch_fn(ticker, plan.start, plan.end)
            added = merge_save(raw, path)
            if added < 0:
                # Empty/invalid fetch: no-op for existing files (e.g. holiday),
                # genuine failure only when there was no prior CSV at all.
                if existed:
                    return ticker, "skipped"
                return ticker, "failed(empty)"
            if not existed and plan.kind == "full":
                if added < min_rows_new:
                    path.unlink(missing_ok=True)
                    return ticker, "failed(min_rows)"
                return ticker, f"full({added})"
            return ticker, (f"gap_appended({added})" if plan.kind == "gap" else f"full({added})")
        except Exception as e:
            return ticker, f"failed({type(e).__name__})"

    if to_fetch:
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            for ticker, st in ex.map(_one, to_fetch):
                status[ticker] = st
    return status


def yf_fetch(ticker: str, start: dt.date, end: dt.date) -> pd.DataFrame:
    """Real network fetch: single-ticker yfinance download for [start, end)."""
    import yfinance as yf
    return yf.download(
        ticker, start=str(start), end=str(end),
        progress=False, auto_adjust=False,
    )
