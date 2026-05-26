from datetime import date

import pandas as pd
import pytest

from pead_backtest import run_backtest


def _synth_price_panel():
    dates = pd.bdate_range("2026-01-01", "2026-12-31")
    px = pd.DataFrame(
        {
            "INFY.NS": [1500 + i for i in range(len(dates))],   # rising
            "WIPRO.NS": [400 - i * 0.1 for i in range(len(dates))],  # falling
        },
        index=dates,
    )
    return px


def _synth_events():
    return pd.DataFrame([
        {"ticker": "INFY.NS", "result_date": date(2026, 1, 20), "period_type": "Q",
         "sue": 2.5, "piotroski": 8, "pb": 1.0, "pb_sector_median": 2.0,
         "sue_decile": 10, "qualifies_long": True},
        {"ticker": "INFY.NS", "result_date": date(2026, 4, 20), "period_type": "Q",
         "sue": 0.0, "piotroski": 5, "pb": 1.0, "pb_sector_median": 2.0,
         "sue_decile": 5, "qualifies_long": False},
    ])


def test_run_backtest_basic_60d_exit():
    closes = _synth_price_panel()
    opens = closes.shift(-1).fillna(closes)
    events = _synth_events()
    result = run_backtest(
        events=events, closes=closes, opens=opens,
        start=date(2026, 1, 1), end=date(2026, 6, 30),
        initial_cash=1_000_000,
    )
    trades = result["trades"]
    assert len(trades) == 1
    t = trades.iloc[0]
    assert t["ticker"] == "INFY.NS"
    # Entry day = result_date + 1 trading day = 2026-01-21
    assert t["entry_date"] == pd.Timestamp("2026-01-21").date()
    # Exit day = min(entry+60td, next_result_date-1td) = next_result-1td
    # next_result = 2026-04-20 → exit = 2026-04-17 (last bday before)
    assert t["exit_reason"] == "NEXT_EARNINGS"


def test_run_backtest_no_qualifying_skip():
    closes = _synth_price_panel()
    opens = closes.shift(-1).fillna(closes)
    events = pd.DataFrame([
        {"ticker": "INFY.NS", "result_date": date(2026, 1, 20), "period_type": "Q",
         "sue": 0.0, "piotroski": 5, "pb": 1.0, "pb_sector_median": 2.0,
         "sue_decile": 5, "qualifies_long": False},
    ])
    result = run_backtest(
        events=events, closes=closes, opens=opens,
        start=date(2026, 1, 1), end=date(2026, 6, 30),
        initial_cash=1_000_000,
    )
    assert len(result["trades"]) == 0
