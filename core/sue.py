"""SUE (Standardised Unexpected Earnings) math — quarterly + annual flavors."""
from __future__ import annotations

import math
import statistics
from typing import Sequence

import pandas as pd


def _clean(prior: Sequence[float]) -> list[float] | None:
    """Return list of 4 finite floats, or None if any nan/missing."""
    if len(prior) != 4:
        return None
    out = [float(x) for x in prior]
    if any(math.isnan(x) or math.isinf(x) for x in out):
        return None
    return out


def quarterly_sue(actual: float, prior: Sequence[float]) -> float:
    """SUE = (actual - mean(prior)) / stdev(prior, ddof=1).

    Expects prior = [t-1, t-2, t-3, t-4] (last 4 reported quarters).
    Returns nan if any input is nan, fewer than 4 priors, or zero std.
    """
    if actual is None or math.isnan(float(actual)):
        return math.nan
    cleaned = _clean(prior)
    if cleaned is None:
        return math.nan
    expected = statistics.fmean(cleaned)
    std = statistics.stdev(cleaned)  # ddof=1
    if std == 0:
        return math.nan
    return (float(actual) - expected) / std


def annual_sue(actual: float, prior: Sequence[float]) -> float:
    """SUE for annual EPS. Same formula, prior = last 4 fiscal years."""
    return quarterly_sue(actual, prior)


def assign_deciles(sues: Sequence[float]) -> list[float]:
    """Rank-based decile assignment (1..10). NaN inputs return NaN.

    Uses pandas.qcut with duplicates='drop' so collisions don't crash.
    If fewer than 10 unique non-nan values, decile labels span 1..k where k<10.
    """
    s = pd.Series(sues, dtype="float64")
    mask = s.notna()
    if mask.sum() == 0:
        return [math.nan] * len(sues)
    ranked = s[mask].rank(method="average")
    n_unique = ranked.nunique()
    bins = min(10, max(1, n_unique))
    labels = list(range(1, bins + 1))
    deciles = pd.qcut(ranked, q=bins, labels=labels, duplicates="drop")
    out = pd.Series([math.nan] * len(sues), dtype="float64")
    out.loc[mask] = deciles.astype("float64").values
    return out.tolist()
