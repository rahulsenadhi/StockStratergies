from unittest.mock import patch

import pandas as pd
import pytest

from pead_universe import filter_universe


def _snap(mcap, first_ts=1_000_000_000, n_q=5, n_annual_cols=3):
    ed = pd.DataFrame(
        {"Reported EPS": [1.0] * n_q},
        index=pd.to_datetime([f"2024-{m:02d}" for m in range(1, n_q + 1)]),
    )
    annual_cols = [pd.Timestamp(f"202{i}-03-31") for i in range(n_annual_cols)]
    annual = pd.DataFrame(
        {c: [100] for c in annual_cols}, index=["Net Income"]
    )
    return {
        "info": {"marketCap": mcap, "firstTradeDateEpochUtc": first_ts},
        "earnings_dates": ed,
        "income_stmt": annual,
        "balance_sheet": annual,
        "cashflow": annual,
        "fetched_at": None,
    }


@patch("pead_universe.get_snapshot")
def test_filter_universe_keeps_liquid_large(mock_snap):
    mock_snap.return_value = _snap(mcap=80_000_00_00_000)
    kept = filter_universe(["RELIANCE.NS"])
    assert "RELIANCE.NS" in kept


@patch("pead_universe.get_snapshot")
def test_filter_universe_drops_small_cap(mock_snap):
    mock_snap.return_value = _snap(mcap=100_00_00_000)
    kept = filter_universe(["TINYCAP.NS"], min_mcap_cr=5000)
    assert "TINYCAP.NS" not in kept


@patch("pead_universe.get_snapshot")
def test_filter_universe_drops_insufficient_eps_history(mock_snap):
    mock_snap.return_value = _snap(mcap=80_000_00_00_000, n_q=2)
    kept = filter_universe(["NEWCO.NS"])
    assert "NEWCO.NS" not in kept


@patch("pead_universe.get_snapshot")
def test_filter_universe_drops_insufficient_piotroski(mock_snap):
    mock_snap.return_value = _snap(mcap=80_000_00_00_000, n_annual_cols=1)
    kept = filter_universe(["THINFIN.NS"])
    assert "THINFIN.NS" not in kept


@patch("pead_universe.get_snapshot")
def test_filter_universe_can_disable_piotroski_check(mock_snap):
    mock_snap.return_value = _snap(mcap=80_000_00_00_000, n_annual_cols=1)
    kept = filter_universe(["THINFIN.NS"], require_piotroski=False)
    assert "THINFIN.NS" in kept
