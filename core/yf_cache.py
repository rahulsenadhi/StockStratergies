"""Per-ticker yfinance snapshot cache.

Fetches earnings_dates + income_stmt + balance_sheet + cashflow + info ONCE per
ticker, persists to `pead_data/yf_cache/<ticker>.pkl`. Refreshes when older than
`max_age_days`. Cuts repeated PEAD backfills from minutes to seconds.

API:
    snap = get_snapshot("RELIANCE.NS")            # dict with 5 keys
    snap = get_snapshot("RELIANCE.NS", force=True) # refetch ignoring cache

Returns dict shape:
    {
        "earnings_dates": pd.DataFrame | None,
        "income_stmt":    pd.DataFrame | None,
        "balance_sheet":  pd.DataFrame | None,
        "cashflow":       pd.DataFrame | None,
        "info":           dict,
        "fetched_at":     date,
    }
"""
from __future__ import annotations

import pickle
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import yfinance as yf

CACHE_DIR = Path("pead_data/yf_cache")
DEFAULT_MAX_AGE_DAYS = 7


def _cache_path(ticker: str) -> Path:
    safe = ticker.replace("/", "_").replace("\\", "_")
    return CACHE_DIR / f"{safe}.pkl"


def _is_fresh(path: Path, max_age_days: int) -> bool:
    if not path.exists():
        return False
    age_days = (time.time() - path.stat().st_mtime) / 86400
    return age_days < max_age_days


def _fetch_live(ticker: str) -> dict[str, Any]:
    """One pass of yfinance — pull every attr we need for PEAD."""
    t = yf.Ticker(ticker)
    snap: dict[str, Any] = {"fetched_at": date.today()}

    def _safe_attr(attr: str):
        try:
            return getattr(t, attr)
        except Exception:
            return None

    snap["earnings_dates"] = _safe_attr("earnings_dates")
    snap["income_stmt"] = _safe_attr("income_stmt")
    snap["balance_sheet"] = _safe_attr("balance_sheet")
    snap["cashflow"] = _safe_attr("cashflow")
    try:
        snap["info"] = t.info or {}
    except Exception:
        snap["info"] = {}
    return snap


def get_snapshot(
    ticker: str,
    max_age_days: int = DEFAULT_MAX_AGE_DAYS,
    force: bool = False,
) -> dict[str, Any]:
    """Return cached snapshot for ticker; refetch if stale or missing."""
    path = _cache_path(ticker)
    if not force and _is_fresh(path, max_age_days):
        try:
            with open(path, "rb") as f:
                return pickle.load(f)
        except Exception:
            pass  # fall through to refetch on corrupt cache
    snap = _fetch_live(ticker)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with open(path, "wb") as f:
            pickle.dump(snap, f)
    except Exception:
        pass
    return snap


def clear(ticker: str | None = None) -> int:
    """Delete cache for one ticker (None = all). Returns count of files removed."""
    n = 0
    if ticker is None:
        if CACHE_DIR.exists():
            for f in CACHE_DIR.glob("*.pkl"):
                f.unlink()
                n += 1
    else:
        p = _cache_path(ticker)
        if p.exists():
            p.unlink()
            n += 1
    return n
