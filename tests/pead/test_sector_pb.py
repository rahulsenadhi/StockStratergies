import math

import pandas as pd

from pead_sector_pb import compute_sector_medians, attach_sector_median


def test_compute_sector_medians_basic():
    df = pd.DataFrame(
        {
            "sector": ["IT", "IT", "IT", "Energy", "Energy"],
            "pb": [2.0, 4.0, 6.0, 1.0, 3.0],
        }
    )
    medians = compute_sector_medians(df)
    assert medians["IT"] == 4.0
    assert medians["Energy"] == 2.0


def test_compute_sector_medians_skips_nan():
    df = pd.DataFrame(
        {"sector": ["IT", "IT", "IT"], "pb": [2.0, float("nan"), 6.0]}
    )
    medians = compute_sector_medians(df)
    assert medians["IT"] == 4.0


def test_attach_sector_median_fallback_to_universe():
    df = pd.DataFrame(
        {
            "sector": ["IT", "IT", "Unknown"],
            "pb": [2.0, 4.0, 5.0],
            "pb_sector_median": [float("nan")] * 3,
        }
    )
    out = attach_sector_median(df)
    assert out.loc[out["sector"] == "IT", "pb_sector_median"].iloc[0] == 3.0
    # Unknown sector falls back to universe median = median([2,4,5]) = 4.0
    assert out.loc[out["sector"] == "Unknown", "pb_sector_median"].iloc[0] == 4.0
