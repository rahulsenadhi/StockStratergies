import math
from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from core.fundamentals import (
    get_quarterly_eps_history,
    get_annual_eps_history,
    get_piotroski_inputs,
    get_price_and_book_value,
)


def _make_earnings_dates_df():
    """Mirrors yfinance Ticker.earnings_dates: index = announce ts, col = Reported EPS."""
    return pd.DataFrame(
        {
            "EPS Estimate": [None] * 8,
            "Reported EPS": [100, 110, 95, 120, 130, 140, 125, 150],
            "Surprise(%)": [None] * 8,
        },
        index=pd.to_datetime(
            ["2024-03-31", "2024-06-30", "2024-09-30", "2024-12-31",
             "2025-03-31", "2025-06-30", "2025-09-30", "2025-12-31"]
        ),
    )


def _snap(**kw):
    base = {"earnings_dates": None, "income_stmt": None, "balance_sheet": None,
            "cashflow": None, "info": {}, "fetched_at": date.today()}
    base.update(kw)
    return base


@patch("core.fundamentals.get_snapshot")
def test_get_quarterly_eps_history_returns_last_4(mock_get):
    mock_get.return_value = _snap(earnings_dates=_make_earnings_dates_df())
    hist = get_quarterly_eps_history("RELIANCE.NS", as_of=date(2026, 1, 15))
    assert hist == [150, 125, 140, 130]


@patch("core.fundamentals.get_snapshot")
def test_get_quarterly_eps_history_filters_post_asof(mock_get):
    mock_get.return_value = _snap(earnings_dates=_make_earnings_dates_df())
    hist = get_quarterly_eps_history("RELIANCE.NS", as_of=date(2025, 4, 1))
    assert hist == [130, 120, 95, 110]


@patch("core.fundamentals.get_snapshot")
def test_get_quarterly_eps_history_empty(mock_get):
    mock_get.return_value = _snap(earnings_dates=pd.DataFrame())
    hist = get_quarterly_eps_history("ZZZ.NS", as_of=date(2026, 1, 1))
    assert hist == []


@patch("core.fundamentals.get_snapshot")
def test_get_price_and_book_value(mock_get):
    mock_get.return_value = _snap(info={
        "sector": "Energy",
        "bookValue": 500.0,
        "regularMarketPrice": 2500.0,
    })
    info = get_price_and_book_value("ZZZ_NOLOCAL.NS", as_of=date(2026, 4, 21))
    assert info["sector"] == "Energy"
    assert info["price"] == 2500.0
    assert info["book_value"] == 500.0
    assert math.isclose(info["pb"], 5.0)
