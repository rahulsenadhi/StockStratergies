"""Tests for precompute_pead_screener.to_records."""
import math

import pandas as pd

import precompute_pead_screener as ps


def test_to_records_camelcases_and_cleans():
    df = pd.DataFrame(
        {
            "ticker": ["AAA.NS"],
            "sector": ["Energy"],
            "result_date": ["2026-03-31"],
            "sue": [1.23],
            "piotroski": [7.0],
            "pb": [float("nan")],
            "qualifies_long": [True],
        }
    )
    rec = ps.to_records(df)
    assert len(rec) == 1
    r = rec[0]
    assert r["ticker"] == "AAA.NS"
    assert r["sector"] == "Energy"
    assert r["resultDate"] == "2026-03-31"
    assert r["sue"] == 1.23
    assert r["piotroski"] == 7.0
    assert r["pb"] is None  # NaN -> None
    assert r["qualifiesLong"] is True


def test_to_records_only_emits_present_columns():
    df = pd.DataFrame({"ticker": ["X"], "sue": [0.5]})
    r = ps.to_records(df)[0]
    assert set(r.keys()) == {"ticker", "sue"}
    assert "pb" not in r


def test_clean_handles_nan_and_numpy():
    assert ps._clean(float("nan")) is None
    assert ps._clean(None) is None
    import numpy as np

    assert ps._clean(np.int64(5)) == 5
    assert isinstance(ps._clean(np.float64(1.5)), float)
