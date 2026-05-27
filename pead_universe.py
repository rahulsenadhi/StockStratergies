"""Universe filter for PEAD: large/mid cap, listed >5y, ≥4 q EPS history,
sufficient Piotroski data (2+ valid annual statement columns).

Uses cached yfinance snapshots via core.yf_cache — orders of magnitude faster
than direct API calls.
"""
from __future__ import annotations

from datetime import date, datetime

import pandas as pd

from core.yf_cache import get_snapshot

_CR = 1_00_00_000  # 1 crore in rupees


def filter_universe(
    candidates: list[str],
    min_mcap_cr: float = 5_000,
    min_years_listed: int = 5,
    min_quarters_eps: int = 4,
    require_piotroski: bool = True,
) -> list[str]:
    """Return tickers passing all filters."""
    kept: list[str] = []
    today = date.today()
    for ticker in candidates:
        try:
            snap = get_snapshot(ticker)
            info = snap.get("info") or {}

            mcap = info.get("marketCap") or 0
            if mcap < min_mcap_cr * _CR:
                continue

            first_ts = info.get("firstTradeDateEpochUtc")
            if first_ts:
                first = datetime.utcfromtimestamp(first_ts).date()
                if (today - first).days < min_years_listed * 365:
                    continue

            ed = snap.get("earnings_dates")
            if ed is None or len(ed) < min_quarters_eps:
                continue
            if "Reported EPS" in ed.columns and ed["Reported EPS"].notna().sum() < min_quarters_eps:
                continue

            if require_piotroski:
                inc = snap.get("income_stmt")
                bal = snap.get("balance_sheet")
                cf = snap.get("cashflow")
                if inc is None or bal is None or cf is None:
                    continue
                if inc.shape[1] < 2 or bal.shape[1] < 2 or cf.shape[1] < 2:
                    continue

            kept.append(ticker)
        except Exception:
            continue
    return kept
