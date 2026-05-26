"""NSE corporate-financial-results client + parser.

Endpoints:
    https://www.nseindia.com/api/corporates-financial-results?index=equities&period=Quarterly
    https://www.nseindia.com/api/corporates-financial-results?index=equities&period=Annual

Required cookie/header dance: GET nseindia.com first, then call API with browser
UA + Referer. Retries 3× on 401/403 with cookie reseed. 2s sleep between calls.
"""
from __future__ import annotations

import json
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any

import requests


_NSE_HOME = "https://www.nseindia.com"
_NSE_API = "https://www.nseindia.com/api/corporates-financial-results"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": (
        "https://www.nseindia.com/companies-listing/"
        "corporate-filings-financial-results"
    ),
}


def _parse_date(s: str) -> date | None:
    """Parse '21-Apr-2026' or '21-Apr-2026 18:30:00' into date."""
    if not s:
        return None
    s = s.strip()
    for fmt in ("%d-%b-%Y %H:%M:%S", "%d-%b-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def infer_period_type(period_from: date, period_to: date) -> str | None:
    """Return 'Q' (~90d span), 'A' (~365d span), or None if neither."""
    if period_from is None or period_to is None:
        return None
    span = (period_to - period_from).days + 1
    if 80 <= span <= 100:
        return "Q"
    if 350 <= span <= 380:
        return "A"
    return None


def nse_symbol_to_yf(symbol: str) -> str:
    """Map NSE bare symbol to yfinance ticker (.NS suffix)."""
    return f"{symbol.strip()}.NS"


def parse_announcements(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert raw NSE API rows into normalized events. Drops unparseable rows."""
    out: list[dict[str, Any]] = []
    for row in raw:
        sym = (row.get("symbol") or "").strip()
        rd = _parse_date(row.get("broadcastDate") or row.get("filingDate") or "")
        pf = _parse_date(row.get("fromDate") or "")
        pt = _parse_date(row.get("toDate") or "")
        period = infer_period_type(pf, pt) if (pf and pt) else None
        if not sym or rd is None or period is None:
            continue
        out.append(
            {
                "symbol": sym,
                "yf_ticker": nse_symbol_to_yf(sym),
                "result_date": rd,
                "period_from": pf,
                "period_to": pt,
                "period_type": period,
            }
        )
    return out


def _new_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(_HEADERS)
    s.get(_NSE_HOME, timeout=30)
    time.sleep(1)
    return s


def fetch_announcements(period: str = "Quarterly", retries: int = 3) -> list[dict]:
    """Fetch raw rows from NSE corp-announce API. Returns list of dicts."""
    assert period in ("Quarterly", "Annual")
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            sess = _new_session()
            r = sess.get(
                _NSE_API,
                params={"index": "equities", "period": period},
                timeout=30,
            )
            if r.status_code in (401, 403):
                raise RuntimeError(f"NSE_BLOCKED status={r.status_code}")
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last_err = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"NSE_BLOCKED after {retries} retries: {last_err}")


def cache_raw(raw: list[dict], cache_dir: Path, day: date) -> Path:
    """Persist raw JSON to pead_data/nse_announce_raw/{YYYY-MM-DD}.json."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{day.isoformat()}.json"
    path.write_text(json.dumps(raw, indent=2))
    return path
