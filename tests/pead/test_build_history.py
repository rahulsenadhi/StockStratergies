from datetime import date
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from pead_build_history import build_history


def _stub_yf_earnings_dates(ticker):
    return pd.DataFrame(
        {"EPS Estimate": [10.0, 9.0], "Reported EPS": [12.0, 11.0]},
        index=pd.to_datetime(["2025-10-20 18:00:00", "2025-07-22 18:00:00"]),
    )


@patch("pead_build_history.fetch_announcements_range", lambda s, e, period: [])
@patch("pead_build_history._yf_earnings_dates", _stub_yf_earnings_dates)
@patch("pead_build_history.build_event",
       lambda ticker, result_date, period_type, eps_actual: {
           "ticker": ticker, "sector": "IT", "result_date": result_date,
           "period_type": period_type, "eps_actual": eps_actual,
           "eps_history": [9, 10, 11, 10], "eps_expected": 10.0,
           "sue": 1.5, "piotroski": 7.0, "pb": 1.0,
           "price_at_result": 100.0, "book_value": 100.0,
           "pb_sector_median": float("nan"), "sue_decile": float("nan"),
           "qualifies_long": False, "qualifies_short": False,
       })
def test_build_history_falls_back_to_yfinance(tmp_path: Path):
    out = tmp_path / "historical_events.parquet"
    n = build_history(
        universe=["INFY.NS"],
        start=date(2025, 1, 1),
        end=date(2026, 1, 1),
        output_path=out,
    )
    assert n == 2
    df = pd.read_parquet(out)
    assert len(df) == 2
    assert df["ticker"].iloc[0] == "INFY.NS"
