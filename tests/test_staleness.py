# tests/test_staleness.py
import datetime as dt
import pandas as pd
from core import staleness


def _write(path, last):
    pd.DataFrame({
        "Date": [last], "Open": 1.0, "High": 1.0, "Low": 1.0,
        "Close": 1.0, "Volume": 1,
    }).to_csv(path, index=False)


def test_staleness_empty_folder(tmp_path):
    info = staleness.dataset_staleness(tmp_path, today=dt.date(2024, 6, 4))
    assert info == {"latest_date": None, "days_behind": None}


def test_staleness_up_to_date(tmp_path):
    _write(tmp_path / "A.csv", "2024-06-04")
    info = staleness.dataset_staleness(tmp_path, today=dt.date(2024, 6, 4))
    assert info["latest_date"] == dt.date(2024, 6, 4)
    assert info["days_behind"] == 0


def test_staleness_three_days_behind(tmp_path):
    _write(tmp_path / "A.csv", "2024-05-30")          # Thu
    info = staleness.dataset_staleness(tmp_path, today=dt.date(2024, 6, 4))  # Tue
    assert info["days_behind"] == 3                   # Fri, Mon, Tue


def test_staleness_uses_newest_across_files(tmp_path):
    _write(tmp_path / "A.csv", "2024-05-30")
    _write(tmp_path / "B.csv", "2024-06-04")
    info = staleness.dataset_staleness(tmp_path, today=dt.date(2024, 6, 4))
    assert info["latest_date"] == dt.date(2024, 6, 4)
    assert info["days_behind"] == 0


def test_staleness_ignores_benchmark_caret(tmp_path):
    _write(tmp_path / "^NSEI.csv", "2024-06-04")
    _write(tmp_path / "A.csv", "2024-05-30")
    info = staleness.dataset_staleness(tmp_path, today=dt.date(2024, 6, 4))
    assert info["latest_date"] == dt.date(2024, 5, 30)   # benchmark skipped
