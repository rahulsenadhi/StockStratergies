# tests/test_incremental.py
import datetime as dt
import pandas as pd
import pytest
from core import incremental as inc


def _write_csv(path, dates):
    pd.DataFrame({
        "Date": dates, "Open": 1.0, "High": 1.0, "Low": 1.0,
        "Close": 1.0, "Volume": 10,
    }).to_csv(path, index=False)


def test_last_stored_date_missing(tmp_path):
    assert inc.last_stored_date(tmp_path / "nope.csv") is None


def test_last_stored_date_empty(tmp_path):
    p = tmp_path / "e.csv"
    p.write_text("")
    assert inc.last_stored_date(p) is None


def test_last_stored_date_returns_max(tmp_path):
    p = tmp_path / "t.csv"
    _write_csv(p, ["2024-01-01", "2024-01-03", "2024-01-02"])
    assert inc.last_stored_date(p) == dt.date(2024, 1, 3)


def test_trading_days_between_same_day_zero():
    assert inc.trading_days_between(dt.date(2024, 1, 8), dt.date(2024, 1, 8)) == 0


def test_trading_days_between_weekend_zero():
    # Fri 2024-01-05 stored, today Sat 2024-01-06 -> 0 trading days behind
    assert inc.trading_days_between(dt.date(2024, 1, 5), dt.date(2024, 1, 6)) == 0


def test_trading_days_between_counts_business_days():
    # Mon stored, Thu today -> Tue, Wed, Thu = 3
    assert inc.trading_days_between(dt.date(2024, 1, 8), dt.date(2024, 1, 11)) == 3
