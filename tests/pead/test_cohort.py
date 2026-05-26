import math
from datetime import date, timedelta

import pandas as pd
import pytest

from pead_cohort import compute_cohort_deciles, mark_qualifies


def _make_events(n=30, ref_date=date(2026, 4, 20)):
    rows = []
    for i in range(n):
        rows.append(
            {
                "ticker": f"T{i}.NS",
                "sector": "IT" if i < 15 else "Energy",
                "result_date": ref_date + timedelta(days=(i % 5) - 2),
                "sue": float(i),  # 0..n-1
                "piotroski": 8 if i % 2 == 0 else 4,
                "pb": 1.0,
                "pb_sector_median": 2.0,
            }
        )
    return pd.DataFrame(rows)


def test_compute_cohort_deciles_window_5td():
    df = _make_events()
    out = compute_cohort_deciles(df, window_td=5)
    # SUE=29 should be in top decile (10)
    assert out.loc[out["sue"] == 29.0, "sue_decile"].iloc[0] == 10
    # SUE=0 should be in decile 1
    assert out.loc[out["sue"] == 0.0, "sue_decile"].iloc[0] == 1


def test_mark_qualifies_long():
    df = _make_events()
    df = compute_cohort_deciles(df, window_td=5)
    df = mark_qualifies(df)
    long_only = df[df["qualifies_long"]]
    # Must satisfy: decile==10 AND piotroski>=7 AND pb<=pb_sector_median
    for _, row in long_only.iterrows():
        assert row["sue_decile"] == 10
        assert row["piotroski"] >= 7
        assert row["pb"] <= row["pb_sector_median"]


def test_mark_qualifies_short_diagnostic():
    df = _make_events()
    df = compute_cohort_deciles(df, window_td=5)
    df = mark_qualifies(df)
    short_only = df[df["qualifies_short"]]
    for _, row in short_only.iterrows():
        assert row["sue_decile"] == 1
        assert row["piotroski"] <= 3
