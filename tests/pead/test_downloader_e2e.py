import json
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from pead_downloader import run_incremental


def _stub_fetch_announcements(period):
    if period != "Quarterly":
        return []
    return [
        {"symbol": "RELIANCE", "broadcastDate": "21-Apr-2026 18:30:00",
         "fromDate": "01-Jan-2026", "toDate": "31-Mar-2026"},
        {"symbol": "INFY", "broadcastDate": "21-Apr-2026 16:00:00",
         "fromDate": "01-Jan-2026", "toDate": "31-Mar-2026"},
    ]


def _stub_build_event(ticker, result_date, period_type, eps_actual):
    return {
        "ticker": ticker, "sector": "IT",
        "result_date": result_date, "period_type": period_type,
        "eps_actual": eps_actual, "eps_history": [10, 11, 9, 10],
        "eps_expected": 10.0, "sue": 2.5,
        "piotroski": 8.0, "pb": 1.5,
        "price_at_result": 1500.0, "book_value": 1000.0,
        "pb_sector_median": float("nan"),
        "sue_decile": float("nan"),
        "qualifies_long": False, "qualifies_short": False,
    }


def _stub_get_actual_eps(ticker, result_date, period_type):
    return 15.0  # any positive value


@patch("pead_downloader.fetch_announcements", _stub_fetch_announcements)
@patch("pead_downloader.build_event", _stub_build_event)
@patch("pead_downloader.get_actual_eps", _stub_get_actual_eps)
@patch("pead_downloader.filter_universe", lambda c, **kw: c)
def test_run_incremental_writes_files(tmp_path: Path):
    cfg = {
        "events_path": tmp_path / "events.parquet",
        "live_signals_path": tmp_path / "live_signals.csv",
        "raw_dir": tmp_path / "raw",
        "status_path": tmp_path / "last_run_status.json",
        "universe": ["RELIANCE.NS", "INFY.NS"],
        "today": date(2026, 4, 22),
    }
    run_incremental(cfg)

    assert (tmp_path / "events.parquet").exists()
    df = pd.read_parquet(tmp_path / "events.parquet")
    assert len(df) == 2
    assert (tmp_path / "live_signals.csv").exists()
    status = json.loads((tmp_path / "last_run_status.json").read_text())
    assert status["declared_count"] == 2
