"""Universe filter for PEAD: large/mid cap, listed >5y, ≥4 q EPS history."""
from __future__ import annotations

import time
from datetime import date, datetime

import pandas as pd
import yfinance as yf

_CR = 1_00_00_000  # 1 crore in rupees


def filter_universe(
    candidates: list[str],
    min_mcap_cr: float = 5_000,
    min_years_listed: int = 5,
    min_quarters_eps: int = 4,
    throttle_sec: float = 0.3,
) -> list[str]:
    """Return tickers passing all filters."""
    kept: list[str] = []
    today = date.today()
    for ticker in candidates:
        try:
            t = yf.Ticker(ticker)
            info = t.info or {}
            mcap = info.get("marketCap") or 0
            if mcap < min_mcap_cr * _CR:
                continue
            first_ts = info.get("firstTradeDateEpochUtc")
            if first_ts:
                first = datetime.utcfromtimestamp(first_ts).date()
                if (today - first).days < min_years_listed * 365:
                    continue
            qe = t.quarterly_earnings
            if qe is None or len(qe) < min_quarters_eps:
                continue
            kept.append(ticker)
        except Exception:
            continue
        time.sleep(throttle_sec)
    return kept
