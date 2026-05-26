"""Sector-level P/B median computation + attachment to events."""
from __future__ import annotations

import math
import pandas as pd


def compute_sector_medians(df: pd.DataFrame) -> dict[str, float]:
    """Return {sector: median P/B}. Skips NaN P/Bs."""
    cleaned = df.dropna(subset=["pb"])
    return cleaned.groupby("sector")["pb"].median().to_dict()


def attach_sector_median(events: pd.DataFrame) -> pd.DataFrame:
    """Fill events['pb_sector_median']. Falls back to universe median for unknown sectors."""
    events = events.copy()
    medians = compute_sector_medians(events)
    medians.pop("Unknown", None)  # Unknown sentinel always falls back
    universe_med = events["pb"].dropna().median() if events["pb"].notna().any() else math.nan
    events["pb_sector_median"] = events["sector"].map(medians).fillna(universe_med)
    return events
