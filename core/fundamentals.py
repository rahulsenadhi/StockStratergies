"""yfinance fundamentals wrapper. Returns dicts/lists ready for SUE & Piotroski.

All getters accept `as_of: date` and FILTER OUT periods whose announce date
(approximated by period_end) is >= as_of. This is the primary look-ahead guard
at the data layer; the backtest engine re-verifies.
"""
from __future__ import annotations

import math
from datetime import date
from typing import Any

import pandas as pd
import yfinance as yf

from core.piotroski import PiotroskiInputs
from core.yf_cache import get_snapshot


def _safe_float(v: Any) -> float:
    try:
        f = float(v)
        return f if not math.isnan(f) else math.nan
    except (TypeError, ValueError):
        return math.nan


def _eps_col_name(df: pd.DataFrame) -> str | None:
    """Pick the EPS column from yfinance df. Tolerates schema drift."""
    if df is None or df.empty:
        return None
    for c in ("Earnings", "Reported EPS"):
        if c in df.columns:
            return c
    return None


def get_quarterly_eps_history(ticker: str, as_of: date, n: int = 4) -> list[float]:
    """Return last n quarterly EPS strictly before as_of, most-recent-first.

    Uses cached yfinance `earnings_dates` (Reported EPS column) — the legacy
    `quarterly_earnings` attribute was deprecated and now returns None.
    Returns [] if yfinance has nothing or fewer than n usable quarters.
    """
    snap = get_snapshot(ticker)
    df = snap.get("earnings_dates")
    col = _eps_col_name(df)
    if col is None:
        return []
    s = df[col].dropna()
    if s.empty:
        return []
    s = s.sort_index(ascending=False)
    # earnings_dates index is tz-aware Timestamp; convert to date.
    s = s[s.index.tz_localize(None).date < as_of if s.index.tz is not None else s.index.date < as_of]
    if len(s) < n:
        return []
    return [_safe_float(v) for v in s.head(n).tolist()]


def get_annual_eps_history(ticker: str, as_of: date, n: int = 4) -> list[float]:
    """Return last n annual EPS strictly before as_of, most-recent-first.

    Derives EPS from cached income_stmt's `Diluted EPS` (fallback `Basic EPS`).
    Returns [] if yfinance has nothing or fewer than n usable years.
    """
    snap = get_snapshot(ticker)
    inc = snap.get("income_stmt")
    if inc is None or inc.empty:
        return []
    eps_row = None
    for key in ("Diluted EPS", "Basic EPS"):
        if key in inc.index:
            eps_row = inc.loc[key]
            break
    if eps_row is None:
        return []
    eps_row = eps_row.dropna()
    if eps_row.empty:
        return []
    # Columns are fiscal-year-end Timestamps, typically descending. Filter then sort.
    eps_row = eps_row[eps_row.index.date < as_of]
    eps_row = eps_row.sort_index(ascending=False)
    if len(eps_row) < n:
        return []
    return [_safe_float(v) for v in eps_row.head(n).tolist()]


def get_piotroski_inputs(ticker: str, as_of: date) -> PiotroskiInputs | None:
    """Build PiotroskiInputs from yfinance annual statements.

    Uses last 2 fiscal years (current vs prior). Returns None if any
    required line item is missing.
    """
    snap = get_snapshot(ticker)
    inc = snap.get("income_stmt")
    bal = snap.get("balance_sheet")
    cf = snap.get("cashflow")
    if inc is None or bal is None or cf is None:
        return None
    if inc.empty or bal.empty or cf.empty:
        return None

    # yfinance frames have columns = fiscal-year-end dates, typically descending.
    # For look-ahead safety we want the two MOST RECENT columns whose period_end < as_of.
    def _valid_cols(df: pd.DataFrame) -> list[pd.Series]:
        cols = list(df.columns)
        # Sort descending by date so [0]=most recent.
        cols_sorted = sorted(cols, key=lambda c: c, reverse=True)
        out: list[pd.Series] = []
        for c in cols_sorted:
            if hasattr(c, "date") and c.date() < as_of:
                out.append(df[c])
                if len(out) == 2:
                    break
        return out

    inc_cols = _valid_cols(inc)
    bal_cols = _valid_cols(bal)
    cf_cols = _valid_cols(cf)
    if len(inc_cols) < 2 or len(bal_cols) < 2 or len(cf_cols) < 2:
        return None
    cur, prev = inc_cols[0], inc_cols[1]
    bal_cur, bal_prev = bal_cols[0], bal_cols[1]
    cf_cur, cf_prev = cf_cols[0], cf_cols[1]

    def _g(s: pd.Series, *keys: str) -> float:
        for k in keys:
            if k in s.index:
                return _safe_float(s[k])
        return math.nan

    inp = PiotroskiInputs(
        net_income=_g(cur, "Net Income", "NetIncome"),
        net_income_prev=_g(prev, "Net Income", "NetIncome"),
        total_assets=_g(bal_cur, "Total Assets"),
        total_assets_prev=_g(bal_prev, "Total Assets"),
        ocf=_g(cf_cur, "Operating Cash Flow", "Total Cash From Operating Activities"),
        ocf_prev=_g(cf_prev, "Operating Cash Flow", "Total Cash From Operating Activities"),
        long_term_debt=_g(bal_cur, "Long Term Debt"),
        long_term_debt_prev=_g(bal_prev, "Long Term Debt"),
        current_assets=_g(bal_cur, "Current Assets", "Total Current Assets"),
        current_liab=_g(bal_cur, "Current Liabilities", "Total Current Liabilities"),
        current_assets_prev=_g(bal_prev, "Current Assets", "Total Current Assets"),
        current_liab_prev=_g(bal_prev, "Current Liabilities", "Total Current Liabilities"),
        shares_outstanding=_g(bal_cur, "Share Issued", "Ordinary Shares Number"),
        shares_outstanding_prev=_g(bal_prev, "Share Issued", "Ordinary Shares Number"),
        gross_profit=_g(cur, "Gross Profit"),
        revenue=_g(cur, "Total Revenue", "Revenue"),
        gross_profit_prev=_g(prev, "Gross Profit"),
        revenue_prev=_g(prev, "Total Revenue", "Revenue"),
    )
    return inp


def get_price_and_book_value(ticker: str, as_of: date) -> dict[str, Any]:
    """Return {sector, price, book_value, pb} as of last close before as_of.

    Price is sourced from existing OHLCV CSVs in `momentum_edge_data/<ticker>.csv`
    when available (no extra network call); otherwise falls back to cached info.
    """
    snap = get_snapshot(ticker)
    info = snap.get("info") or {}
    sector = info.get("sector") or "Unknown"
    book = _safe_float(info.get("bookValue"))

    # Try local OHLCV first (no network), fallback to info.regularMarketPrice
    price = math.nan
    try:
        from pathlib import Path
        csv_path = Path("momentum_edge_data") / f"{ticker}.csv"
        if csv_path.exists():
            px_df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
            px_df = px_df.sort_index()
            px_df = px_df[px_df.index.date < as_of]
            if not px_df.empty and "Close" in px_df.columns:
                price = _safe_float(px_df["Close"].iloc[-1])
    except Exception:
        pass

    if math.isnan(price):
        price = _safe_float(info.get("regularMarketPrice") or info.get("previousClose"))

    pb = price / book if (book and book > 0 and not math.isnan(price)) else math.nan
    return {"sector": sector, "price": price, "book_value": book, "pb": pb}
