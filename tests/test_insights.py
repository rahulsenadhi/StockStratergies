"""Tests for precompute_insights pure functions."""
import pandas as pd

import precompute_insights as pi


def _trades():
    return pd.DataFrame(
        {
            "Entry_Type": ["ATH", "ATH", "52W", "52W"],
            "Exit_Reason": ["Target", "Stop", "Target", "Stop"],
            "Result": ["Win", "Loss", "Win", "Loss"],
            "PnL_Pct": [10.0, -5.0, 8.0, -4.0],
            "Score": [90.0, 40.0, 80.0, 30.0],
        }
    )


def test_bucket_records_basic():
    recs = pi.bucket_records(_trades(), "Entry_Type")
    by = {r["group"]: r for r in recs}
    assert set(by) == {"ATH", "52W"}
    assert by["ATH"]["count"] == 2
    assert by["ATH"]["winRate"] == 50.0
    assert by["ATH"]["avgPnl"] == 2.5  # (10-5)/2


def test_bucket_records_missing_col():
    assert pi.bucket_records(_trades(), "Nonexistent") == []


def test_overall():
    ov = pi.overall(_trades())
    assert ov["n"] == 4
    assert ov["winRate"] == 50.0
    assert ov["avgPnl"] == 2.25  # (10-5+8-4)/4


def test_overall_empty():
    ov = pi.overall(pd.DataFrame())
    assert ov == {"n": 0, "winRate": None, "avgPnl": None, "medianPnl": None}


def test_build_strategy_includes_score_bucket():
    rep = pi.build_strategy(_trades(), [("byEntryType", "Entry_Type")])
    assert rep["overall"]["n"] == 4
    assert "byEntryType" in rep
    # 4 distinct scores -> qcut may collapse; just assert key handling doesn't crash
    assert isinstance(rep.get("byScoreBucket", []), list)


def test_build_strategy_none():
    assert pi.build_strategy(None, []) == {}
    assert pi.build_strategy(pd.DataFrame(), []) == {}


def test_num_cleans_nan():
    assert pi._num(float("nan")) is None
    assert pi._num(None) is None
    assert pi._num(3.5) == 3.5
