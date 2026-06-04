"""Hold-period & exit-ladder analyzer.

Pure functions (no Streamlit, no network). Given a strategy's historical entries
and an OHLCV price panel, computes:
  - the risk-adjusted best holding duration,
  - a 3-tier scale-out ladder (profit targets + booking %),
  - a stop level,
from the historical post-entry return / MFE / MAE distributions.

All inputs use the standard `entries` DataFrame contract:
    columns: ticker (str), entry_date (Timestamp), entry_price (float),
             optional bucket (str)
The price panel is a dict ticker -> OHLCV DataFrame (Date index, columns
Open/High/Low/Close/Volume), as produced by core.data_io.load_ohlcv or
core.rotation_trades.build_pseudo_ohlcv (close-only -> High==Low==Close).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal

import numpy as np
import pandas as pd

MAX_HORIZON_DAYS = 90          # trading days of post-entry path to study
TARGET_PERCENTILES = (40, 65, 85)   # MFE percentiles -> profit targets
BOOK_FRACTIONS = (40, 35, 25)       # % of position booked at each target
assert sum(BOOK_FRACTIONS) == 100, "BOOK_FRACTIONS must sum to 100"
STOP_PERCENTILE = 75           # % of trades that should stay above the stop
MIN_SAMPLE = 20                # min entries for a recommendation / bucket
MAE_FLOOR = 0.5                # % floor on denominator of risk-adjusted score


@dataclass
class Target:
    pct: float
    book_pct: int
    hit_rate: float


@dataclass
class Recommendation:
    strategy: str
    bucket: str
    hold_days: int
    hold_median_return: float
    hold_win_rate: float
    targets: list[Target]
    stop_pct: float
    sample_size: int
    data_quality: Literal["ohlcv", "close"]
    curve: list[dict]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["targets"] = [asdict(t) if isinstance(t, Target) else t for t in self.targets]
        return d
