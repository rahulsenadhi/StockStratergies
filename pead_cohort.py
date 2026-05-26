"""Cohort decile assignment + qualifies_long/short flags.

For each event, decile is computed within events whose result_date is in
[result_date - window_td, result_date + window_td]. This handles spec
section §5 rolling cohort.
"""
from __future__ import annotations

import math
from datetime import timedelta

import pandas as pd

from core.sue import assign_deciles


def compute_cohort_deciles(events: pd.DataFrame, window_td: int = 5) -> pd.DataFrame:
    """Assign SUE decile per event using a ±window_td trading-day cohort.

    NOTE: window_td is approximated as calendar days here (5 td ≈ 7 cal days).
    For backtest accuracy we use trading-day arithmetic; for live live_signals
    the look-ahead window collapses naturally to [d-window, d].
    """
    events = events.copy()
    events["sue_decile"] = float("nan")
    cal_window = timedelta(days=window_td + 2)  # 5 td ≈ 7 cal days
    for idx, row in events.iterrows():
        rd = row["result_date"]
        mask = (events["result_date"] >= rd - cal_window) & (
            events["result_date"] <= rd + cal_window
        )
        cohort = events.loc[mask, "sue"].tolist()
        deciles = assign_deciles(cohort)
        cohort_idx = events.loc[mask].index.tolist()
        pos = cohort_idx.index(idx)
        events.at[idx, "sue_decile"] = deciles[pos]
    return events


def mark_qualifies(events: pd.DataFrame) -> pd.DataFrame:
    """Apply entry rules from spec §2.

    qualifies_long  = decile == 10 AND piotroski >= 7 AND pb <= pb_sector_median
    qualifies_short = decile ==  1 AND piotroski <= 3                  (diagnostic)
    """
    events = events.copy()
    top = events["sue_decile"] == 10
    bot = events["sue_decile"] == 1
    pio_ok = events["piotroski"] >= 7
    pio_bad = events["piotroski"] <= 3
    pb_ok = events["pb"] <= events["pb_sector_median"]
    events["qualifies_long"] = (top & pio_ok & pb_ok).fillna(False)
    events["qualifies_short"] = (bot & pio_bad).fillna(False)
    return events
