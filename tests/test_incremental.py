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


def test_plan_fetch_no_file_is_full(tmp_path):
    plan = inc.plan_fetch(tmp_path / "new.csv", dt.date(2024, 6, 4))
    assert plan.kind == "full"
    assert plan.end == dt.date(2024, 6, 5)          # today + 1 (exclusive)
    assert plan.start == dt.date(2024, 6, 4) - dt.timedelta(days=inc.FULL_LOOKBACK_DAYS)


def test_plan_fetch_current_is_skip(tmp_path):
    p = tmp_path / "t.csv"
    _write_csv(p, ["2024-06-04"])
    plan = inc.plan_fetch(p, dt.date(2024, 6, 4))
    assert plan.kind == "skip"


def test_plan_fetch_gap(tmp_path):
    p = tmp_path / "t.csv"
    _write_csv(p, ["2024-05-30"])                   # Thu
    plan = inc.plan_fetch(p, dt.date(2024, 6, 4))   # Tue (gap exists)
    assert plan.kind == "gap"
    assert plan.start == dt.date(2024, 5, 31)       # last + 1
    assert plan.end == dt.date(2024, 6, 5)          # today + 1


def test_plan_fetch_weekend_is_skip(tmp_path):
    p = tmp_path / "t.csv"
    _write_csv(p, ["2024-06-07"])                   # Fri
    plan = inc.plan_fetch(p, dt.date(2024, 6, 8))   # Sat -> 0 trading days -> skip
    assert plan.kind == "skip"


def _raw(dates, close=100.0):
    return pd.DataFrame({
        "Date": dates, "Open": close, "High": close, "Low": close,
        "Close": close, "Volume": 5,
    })


def test_standardize_drops_nan_close_and_dupes():
    df = _raw(["2024-01-01", "2024-01-01", "2024-01-02"])
    df.loc[2, "Close"] = float("nan")
    out = inc.standardize(df)
    assert list(out["Date"]) == [dt.date(2024, 1, 1)]


def test_standardize_missing_cols_returns_none():
    assert inc.standardize(pd.DataFrame({"Date": ["2024-01-01"], "Close": [1.0]})) is None


def test_merge_save_new_file(tmp_path):
    p = tmp_path / "t.csv"
    added = inc.merge_save(_raw(["2024-01-01", "2024-01-02"]), p)
    assert added == 2
    assert inc.last_stored_date(p) == dt.date(2024, 1, 2)


def test_merge_save_appends_and_dedups(tmp_path):
    p = tmp_path / "t.csv"
    inc.merge_save(_raw(["2024-01-01", "2024-01-02"]), p)
    added = inc.merge_save(_raw(["2024-01-02", "2024-01-03"]), p)   # 02 overlaps
    assert added == 1
    df = pd.read_csv(p)
    assert list(pd.to_datetime(df["Date"]).dt.strftime("%Y-%m-%d")) == \
        ["2024-01-01", "2024-01-02", "2024-01-03"]


def test_merge_save_idempotent_no_rewrite(tmp_path):
    p = tmp_path / "t.csv"
    inc.merge_save(_raw(["2024-01-01", "2024-01-02"]), p)
    before = p.read_bytes()
    added = inc.merge_save(_raw(["2024-01-01", "2024-01-02"]), p)   # same data
    assert added == 0
    assert p.read_bytes() == before        # byte-identical, no write


def test_merge_save_empty_returns_negative(tmp_path):
    p = tmp_path / "t.csv"
    assert inc.merge_save(pd.DataFrame(), p) == -1
    assert not p.exists()
