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
