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


def test_refresh_tickers_skips_current_and_appends_gap(tmp_path):
    folder = tmp_path / "ds"
    folder.mkdir()
    _write_csv(folder / "CUR.csv", ["2024-06-04"])      # current -> skip
    _write_csv(folder / "OLD.csv", ["2024-05-30"])      # gap

    calls = []

    def fake_fetch(ticker, start, end):
        calls.append(ticker)
        return _raw(["2024-05-31", "2024-06-03", "2024-06-04"])

    status = inc.refresh_tickers(
        ["CUR", "OLD"], folder, dt.date(2024, 6, 4), fake_fetch, max_workers=1)

    assert status["CUR"] == "skipped"
    assert status["OLD"].startswith("gap_appended")
    assert calls == ["OLD"]                              # CUR never hit the network


def test_refresh_tickers_new_ticker_full(tmp_path):
    folder = tmp_path / "ds"
    folder.mkdir()
    dates = pd.bdate_range("2024-01-01", periods=120).strftime("%Y-%m-%d").tolist()

    status = inc.refresh_tickers(
        ["NEW"], folder, dt.date(2024, 6, 20),
        lambda t, s, e: _raw(dates), max_workers=1)

    assert status["NEW"].startswith("full")
    assert (folder / "NEW.csv").exists()


def test_refresh_tickers_new_ticker_below_min_rows_discarded(tmp_path):
    folder = tmp_path / "ds"
    folder.mkdir()
    status = inc.refresh_tickers(
        ["TINY"], folder, dt.date(2024, 6, 20),
        lambda t, s, e: _raw(["2024-06-18", "2024-06-19"]),  # 2 rows < MIN_ROWS
        max_workers=1, min_rows_new=100)
    assert status["TINY"] == "failed(min_rows)"
    assert not (folder / "TINY.csv").exists()


def test_refresh_tickers_one_failure_isolated(tmp_path):
    folder = tmp_path / "ds"
    folder.mkdir()
    _write_csv(folder / "A.csv", ["2024-05-30"])
    _write_csv(folder / "B.csv", ["2024-05-30"])

    def fake_fetch(ticker, start, end):
        if ticker == "A":
            raise RuntimeError("boom")
        return _raw(["2024-05-31", "2024-06-04"])

    status = inc.refresh_tickers(
        ["A", "B"], folder, dt.date(2024, 6, 4), fake_fetch, max_workers=1)
    assert status["A"].startswith("failed")
    assert status["B"].startswith("gap_appended")        # B unaffected


def test_refresh_tickers_empty_return_is_skip_noop(tmp_path):
    folder = tmp_path / "ds"
    folder.mkdir()
    _write_csv(folder / "A.csv", ["2024-05-30"])
    before = (folder / "A.csv").read_bytes()
    status = inc.refresh_tickers(
        ["A"], folder, dt.date(2024, 6, 4),
        lambda t, s, e: pd.DataFrame(), max_workers=1)     # empty fetch
    assert status["A"] == "failed(empty)"
    assert (folder / "A.csv").read_bytes() == before       # untouched
