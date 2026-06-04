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
