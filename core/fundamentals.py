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

    Uses yfinance `earnings_dates` (Reported EPS column) — the legacy
    `quarterly_earnings` attribute was deprecated and now returns None.
    Returns [] if yfinance has nothing or fewer than n usable quarters.
    """
    t = yf.Ticker(ticker)
    df = None
    try:
        df = t.earnings_dates
    except Exception:
        return []
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

    Derives EPS from income_stmt's `Diluted EPS` (fallback `Basic EPS`).
    Returns [] if yfinance has nothing or fewer than n usable years.
    """
    t = yf.Ticker(ticker)
    try:
        inc = t.income_stmt
    except Exception:
        return []
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
    t = yf.Ticker(ticker)
    try:
        inc = t.income_stmt
        bal = t.balance_sheet
        cf = t.cashflow
    except Exception:
        return None
    if inc is None or bal is None or cf is None:
        return None
    if inc.empty or bal.empty or cf.empty:
        return None

    # yfinance frames have columns = fiscal-year-end dates, descending.
    def _col(df: pd.DataFrame, i: int) -> pd.Series | None:
        if df.shape[1] <= i:
            return None
        col = df.columns[i]
        if col.date() >= as_of:
            return None
        return df[col]

    cur = _col(inc, 0)
    prev = _col(inc, 1)
    if cur is None or prev is None:
        return None
    bal_cur = _col(bal, 0)
    bal_prev = _col(bal, 1)
    cf_cur = _col(cf, 0)
    cf_prev = _col(cf, 1)
    if bal_cur is None or bal_prev is None or cf_cur is None or cf_prev is None:
        return None

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
    """Return {sector, price, book_value, pb} as of last close before as_of."""
    t = yf.Ticker(ticker)
    info = t.info or {}
    sector = info.get("sector") or "Unknown"
    book = _safe_float(info.get("bookValue"))
    # Pull last close strictly before as_of
    hist = t.history(start=str(as_of.replace(day=1)), end=str(as_of))
    if hist is None or hist.empty:
        return {"sector": sector, "price": math.nan, "book_value": book, "pb": math.nan}
    price = _safe_float(hist["Close"].iloc[-1])
    pb = price / book if (book and book > 0 and not math.isnan(price)) else math.nan
    return {"sector": sector, "price": price, "book_value": book, "pb": pb}
