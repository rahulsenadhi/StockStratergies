from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from pead_universe import filter_universe


@patch("pead_universe.yf.Ticker")
def test_filter_universe_keeps_liquid_large(mock_ticker):
    mock_t = MagicMock()
    mock_t.info = {"marketCap": 80_000_00_00_000, "firstTradeDateEpochUtc": 1_000_000_000}
    mock_t.quarterly_earnings = pd.DataFrame(
        {"Earnings": [1, 2, 3, 4, 5]},
        index=pd.to_datetime(["2024-03", "2024-06", "2024-09", "2024-12", "2025-03"]),
    )
    mock_ticker.return_value = mock_t

    kept = filter_universe(["RELIANCE.NS"])
    assert "RELIANCE.NS" in kept


@patch("pead_universe.yf.Ticker")
def test_filter_universe_drops_small_cap(mock_ticker):
    mock_t = MagicMock()
    mock_t.info = {"marketCap": 100_00_00_000, "firstTradeDateEpochUtc": 1_000_000_000}
    mock_t.quarterly_earnings = pd.DataFrame(
        {"Earnings": [1, 2, 3, 4]},
        index=pd.to_datetime(["2024-03", "2024-06", "2024-09", "2024-12"]),
    )
    mock_ticker.return_value = mock_t

    kept = filter_universe(["TINYCAP.NS"], min_mcap_cr=5000)
    assert "TINYCAP.NS" not in kept


@patch("pead_universe.yf.Ticker")
def test_filter_universe_drops_insufficient_history(mock_ticker):
    mock_t = MagicMock()
    mock_t.info = {"marketCap": 80_000_00_00_000, "firstTradeDateEpochUtc": 1_000_000_000}
    mock_t.quarterly_earnings = pd.DataFrame(
        {"Earnings": [1, 2]},
        index=pd.to_datetime(["2025-09", "2025-12"]),
    )
    mock_ticker.return_value = mock_t

    kept = filter_universe(["NEWCO.NS"])
    assert "NEWCO.NS" not in kept
