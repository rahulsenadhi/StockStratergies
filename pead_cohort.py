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


def compute_cohort_deciles(events: pd.DataFrame, window_td: int = 5,
                           allow_future: bool = True) -> pd.DataFrame:
    """Assign SUE decile per event using a rolling cohort window.

    NOTE: window_td is approximated as calendar days here (5 td ≈ 7 cal days).

    allow_future=True: cohort = [rd-window, rd+window]. Use for HISTORICAL
        backtest where all events are already known.
    allow_future=False: cohort = [rd-window, rd]. Use for LIVE signal
        generation to avoid look-ahead bias.
    """
    events = events.copy()
    events["sue_decile"] = float("nan")
    cal_window = timedelta(days=window_td + 2)  # 5 td ≈ 7 cal days
    for idx, row in events.iterrows():
        rd = row["result_date"]
        lower = rd - cal_window
        upper = rd + cal_window if allow_future else rd
        mask = (events["result_date"] >= lower) & (events["result_date"] <= upper)
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
