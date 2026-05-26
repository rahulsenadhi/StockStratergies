from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from pead_events_store import append_events, load_events


def test_append_and_load_events(tmp_path: Path):
    path = tmp_path / "events.parquet"
    rows = [
        {"ticker": "A.NS", "result_date": date(2026, 1, 1), "period_type": "Q",
         "sue": 1.5, "piotroski": 8, "pb": 2.0, "sector": "IT",
         "eps_actual": 10.0, "eps_expected": 8.0,
         "pb_sector_median": 3.0, "sue_decile": 10.0,
         "qualifies_long": True, "qualifies_short": False},
    ]
    append_events(path, rows)
    df = load_events(path)
    assert len(df) == 1
    assert df.iloc[0]["ticker"] == "A.NS"


def test_append_dedup_by_ticker_date_period(tmp_path: Path):
    path = tmp_path / "events.parquet"
    base = {"ticker": "A.NS", "result_date": date(2026, 1, 1), "period_type": "Q",
            "sue": 1.5, "piotroski": 8, "pb": 2.0, "sector": "IT",
            "eps_actual": 10.0, "eps_expected": 8.0,
            "pb_sector_median": 3.0, "sue_decile": 10.0,
            "qualifies_long": True, "qualifies_short": False}
    append_events(path, [base])
    append_events(path, [base])     # duplicate
    df = load_events(path)
    assert len(df) == 1


def test_append_updates_existing(tmp_path: Path):
    path = tmp_path / "events.parquet"
    base = {"ticker": "A.NS", "result_date": date(2026, 1, 1), "period_type": "Q",
            "sue": 1.5, "piotroski": 8, "pb": 2.0, "sector": "IT",
            "eps_actual": 10.0, "eps_expected": 8.0,
            "pb_sector_median": 3.0, "sue_decile": 10.0,
            "qualifies_long": True, "qualifies_short": False}
    append_events(path, [base])
    updated = dict(base, sue=2.0)
    append_events(path, [updated])
    df = load_events(path)
    assert len(df) == 1
    assert df.iloc[0]["sue"] == 2.0
