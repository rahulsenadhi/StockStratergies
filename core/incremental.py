# core/incremental.py
"""Gap-aware incremental OHLCV fetch engine (S0b).

Single source of truth for "fetch only the missing trading days" — generalizes
the incremental logic that previously lived inside nse_bse_downloader.py.
"""
from __future__ import annotations

import datetime as dt
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
    return pd.to_datetime(df["Date"]).dt.date.max()


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


import os


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
    if p.exists():
        existing = pd.read_csv(p)
        existing["Date"] = pd.to_datetime(existing["Date"]).dt.date
        before = len(existing)
        merged = (pd.concat([existing, std], ignore_index=True)
                    .drop_duplicates(subset="Date")
                    .sort_values("Date")
                    .reset_index(drop=True))
        if len(merged) == before:
            return 0                          # nothing new -> don't touch the file
    else:
        before = 0
        merged = std
    tmp = p.with_suffix(".csv.tmp")
    merged.to_csv(tmp, index=False)
    os.replace(tmp, p)                        # atomic; crash before this keeps old CSV
    return len(merged) - before
