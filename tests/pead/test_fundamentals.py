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


def _make_quarterly_df():
    return pd.DataFrame(
        {
            "Earnings": [100, 110, 95, 120, 130, 140, 125, 150],
        },
        index=pd.to_datetime(
            ["2024-03-31", "2024-06-30", "2024-09-30", "2024-12-31",
             "2025-03-31", "2025-06-30", "2025-09-30", "2025-12-31"]
        ),
    )


@patch("core.fundamentals.yf.Ticker")
def test_get_quarterly_eps_history_returns_last_4(mock_ticker):
    mock_t = MagicMock()
    mock_t.quarterly_earnings = _make_quarterly_df()
    mock_ticker.return_value = mock_t

    hist = get_quarterly_eps_history("RELIANCE.NS", as_of=date(2026, 1, 15))
    assert hist == [150, 125, 140, 130]   # most-recent-first


@patch("core.fundamentals.yf.Ticker")
def test_get_quarterly_eps_history_filters_post_asof(mock_ticker):
    mock_t = MagicMock()
    mock_t.quarterly_earnings = _make_quarterly_df()
    mock_ticker.return_value = mock_t

    hist = get_quarterly_eps_history("RELIANCE.NS", as_of=date(2025, 4, 1))
    # Only 2024 quarters before 2025-04-01 -> [2024-12-31, ..., 2024-03-31]
    assert hist == [120, 95, 110, 100]


@patch("core.fundamentals.yf.Ticker")
def test_get_quarterly_eps_history_empty(mock_ticker):
    mock_t = MagicMock()
    mock_t.quarterly_earnings = pd.DataFrame()
    mock_ticker.return_value = mock_t

    hist = get_quarterly_eps_history("ZZZ.NS", as_of=date(2026, 1, 1))
    assert hist == []


@patch("core.fundamentals.yf.Ticker")
def test_get_price_and_book_value(mock_ticker):
    mock_t = MagicMock()
    mock_t.info = {"sector": "Energy", "bookValue": 500.0}
    mock_t.history.return_value = pd.DataFrame(
        {"Close": [2500.0]},
        index=pd.to_datetime(["2026-04-20"]),
    )
    mock_ticker.return_value = mock_t

    info = get_price_and_book_value("RELIANCE.NS", as_of=date(2026, 4, 21))
    assert info["sector"] == "Energy"
    assert info["price"] == 2500.0
    assert info["book_value"] == 500.0
    assert math.isclose(info["pb"], 5.0)
