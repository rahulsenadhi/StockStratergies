import pandas as pd
import numpy as np
import pytest

from core import exit_analyzer as ea


def test_constants_and_dataclasses_exist():
    assert ea.MAX_HORIZON_DAYS == 90
    assert ea.TARGET_PERCENTILES == (40, 65, 85)
    assert ea.BOOK_FRACTIONS == (40, 35, 25)
    assert ea.STOP_PERCENTILE == 75
    assert ea.MIN_SAMPLE == 20
    assert ea.MAE_FLOOR == 0.5

    t = ea.Target(pct=6.0, book_pct=40, hit_rate=0.78)
    assert t.pct == 6.0 and t.book_pct == 40

    rec = ea.Recommendation(
        strategy="x", bucket="ALL", hold_days=10, hold_median_return=1.0,
        hold_win_rate=0.5, targets=[t], stop_pct=-8.0, sample_size=30,
        data_quality="ohlcv", curve=[{"day": 1, "median": 0.1}],
    )
    d = rec.to_dict()
    assert d["strategy"] == "x"
    assert d["targets"][0]["pct"] == 6.0
    assert d["sample_size"] == 30


def _ohlcv(dates, highs, lows, closes):
    idx = pd.to_datetime(dates)
    return pd.DataFrame(
        {"Open": closes, "High": highs, "Low": lows, "Close": closes, "Volume": 0},
        index=idx,
    )


def test_build_entry_path_mfe_mae_running():
    # entry on day 0 at 100. Forward 3 days.
    df = _ohlcv(
        ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"],
        highs=[100, 110, 105, 108],
        lows=[100, 98, 90, 102],
        closes=[100, 108, 95, 106],
    )
    path = ea.build_entry_path(df, pd.Timestamp("2024-01-01"), 100.0, max_horizon=3)
    # day offsets 1..3 (strictly after entry_date)
    assert list(path["day"]) == [1, 2, 3]
    # ret = close/entry - 1, in %
    assert path["ret"].tolist() == pytest.approx([8.0, -5.0, 6.0])
    # running MFE uses High: max(110,105,108)/100 -1 -> 10 at d1(110), stays 10
    assert path["mfe"].tolist() == pytest.approx([10.0, 10.0, 10.0])
    # running MAE uses Low: min so far: -2 (98), then -10 (90), then -10
    assert path["mae"].tolist() == pytest.approx([-2.0, -10.0, -10.0])


def test_build_entry_path_short_history():
    df = _ohlcv(["2024-01-01", "2024-01-02"], [100, 101], [100, 99], [100, 100.5])
    path = ea.build_entry_path(df, pd.Timestamp("2024-01-01"), 100.0, max_horizon=90)
    assert list(path["day"]) == [1]   # only one day available after entry


def test_build_matrix_collects_paths_and_excursions():
    df_a = _ohlcv(
        ["2024-01-01", "2024-01-02", "2024-01-03"],
        highs=[100, 112, 108], lows=[100, 99, 95], closes=[100, 110, 104],
    )
    df_b = _ohlcv(
        ["2024-01-01", "2024-01-02", "2024-01-03"],
        highs=[50, 51, 60], lows=[50, 45, 48], closes=[50, 48, 58],
    )
    ohlcv = {"A": df_a, "B": df_b}
    entries = pd.DataFrame({
        "ticker": ["A", "B", "MISSING"],
        "entry_date": pd.to_datetime(["2024-01-01", "2024-01-01", "2024-01-01"]),
        "entry_price": [100.0, 50.0, 10.0],
    })

    paths, mfe_arr, mae_arr, skipped = ea.build_matrix(entries, ohlcv, max_horizon=2)

    assert len(paths) == 2          # MISSING has no price data
    assert skipped == 1
    # per-entry overall MFE (last value of running mfe column):
    #   A: highs over 2 fwd days [112, 108] -> running max [12, 12] -> 12.0
    #   B: highs over 2 fwd days [51, 60]   -> running max [2, 20]  -> 20.0
    assert sorted(np.round(mfe_arr, 2).tolist()) == [12.0, 20.0]
    # per-entry overall MAE (last value of running mae column):
    #   A: lows over 2 fwd days [99, 95] -> running min [-1, -5] -> -5.0
    #   B: lows over 2 fwd days [45, 48] -> running min [-10, -10] -> -10.0
    assert sorted(np.round(mae_arr, 2).tolist()) == [-10.0, -5.0]
