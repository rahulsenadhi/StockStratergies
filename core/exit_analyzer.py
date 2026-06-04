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


def build_entry_path(
    ohlcv: pd.DataFrame,
    entry_date: pd.Timestamp,
    entry_price: float,
    max_horizon: int = MAX_HORIZON_DAYS,
) -> pd.DataFrame:
    """Return a DataFrame of the post-entry path with running MFE/MAE.

    Columns: day (1-based offset), ret, mfe, mae — all in percent vs entry_price.
    Rows are the trading days strictly after entry_date, up to max_horizon.
    Returns an empty DataFrame if no forward data or entry_price is invalid.
    """
    cols = ["day", "ret", "mfe", "mae"]
    if (ohlcv is None or ohlcv.empty or entry_price is None
            or not np.isfinite(entry_price) or entry_price <= 0):
        return pd.DataFrame(columns=cols)

    fwd = ohlcv[ohlcv.index > pd.Timestamp(entry_date)].head(max_horizon)
    if fwd.empty:
        return pd.DataFrame(columns=cols)

    close = fwd["Close"].to_numpy(dtype=float)
    high = fwd["High"].to_numpy(dtype=float)
    low = fwd["Low"].to_numpy(dtype=float)

    ret = (close / entry_price - 1.0) * 100.0
    fav = (high / entry_price - 1.0) * 100.0
    adv = (low / entry_price - 1.0) * 100.0
    mfe = np.maximum.accumulate(fav)
    mae = np.minimum.accumulate(adv)

    return pd.DataFrame(
        {"day": np.arange(1, len(fwd) + 1), "ret": ret, "mfe": mfe, "mae": mae}
    )


def build_matrix(
    entries: pd.DataFrame,
    ohlcv: dict,
    max_horizon: int = MAX_HORIZON_DAYS,
) -> tuple[list, np.ndarray, np.ndarray, int]:
    """Build per-entry paths and overall excursion arrays.

    Returns (paths, mfe_arr, mae_arr, skipped):
      paths   - list of per-entry path DataFrames (from build_entry_path)
      mfe_arr - np.array of each entry's overall max-favorable-excursion %
      mae_arr - np.array of each entry's overall max-adverse-excursion %
      skipped - count of entries with no usable forward price data
    """
    paths: list = []
    mfes: list = []
    maes: list = []
    skipped = 0

    for row in entries.itertuples(index=False):
        df = ohlcv.get(row.ticker)
        path = build_entry_path(df, row.entry_date, row.entry_price, max_horizon)
        if path.empty:
            skipped += 1
            continue
        paths.append(path)
        mfes.append(float(path["mfe"].iloc[-1]))
        maes.append(float(path["mae"].iloc[-1]))

    return paths, np.array(mfes), np.array(maes), skipped


def aggregate_curve(paths: list, max_horizon: int = MAX_HORIZON_DAYS) -> pd.DataFrame:
    """Aggregate per-entry paths into a return-by-day curve.

    Columns: day, median, mean, p25, p75, mae (avg adverse), win_rate, n.
    Each day aggregates only the entries that have data for that offset.
    """
    cols = ["day", "median", "mean", "p25", "p75", "mae", "win_rate", "n"]
    if not paths:
        return pd.DataFrame(columns=cols)
    combined = pd.concat(paths, ignore_index=True)
    combined = combined[combined["day"] <= max_horizon]
    rows = []
    for d, grp in combined.groupby("day", sort=True):
        arr = grp["ret"].to_numpy(dtype=float)
        maes = grp["mae"].to_numpy(dtype=float)
        rows.append({
            "day": int(d),
            "median": float(np.median(arr)),
            "mean": float(np.mean(arr)),
            "p25": float(np.percentile(arr, 25)),
            "p75": float(np.percentile(arr, 75)),
            "mae": float(np.mean(maes)),
            "win_rate": float(np.mean(arr > 0)),
            "n": int(len(arr)),
        })
    return pd.DataFrame(rows)


def best_hold_day(curve: pd.DataFrame) -> tuple[int, float, float]:
    """Pick the day maximizing median_return / max(|avg_MAE|, MAE_FLOOR).

    Returns (day, median_return, win_rate). Returns (0, 0.0, 0.0) on empty curve.
    """
    if curve is None or curve.empty:
        return 0, 0.0, 0.0
    denom = np.maximum(np.abs(curve["mae"].to_numpy()), MAE_FLOOR)
    score = curve["median"].to_numpy() / denom
    score = np.where(np.isfinite(score), score, -np.inf)
    if not np.isfinite(score).any():
        return 0, 0.0, 0.0
    idx = int(np.argmax(score))
    row = curve.iloc[idx]
    return int(row["day"]), float(row["median"]), float(row["win_rate"])


def exit_ladder(mfe_arr: np.ndarray, mae_arr: np.ndarray) -> tuple[list, float]:
    """Derive 3 profit targets (from MFE percentiles) + a stop (from MAE).

    Returns (targets, stop_pct):
      targets  - list[Target] at TARGET_PERCENTILES of the MFE distribution,
                 each booking BOOK_FRACTIONS of the position, with the historical
                 hit-rate (fraction of entries whose MFE reached the target).
      stop_pct - negative %; the (100 - STOP_PERCENTILE)th percentile of MAE,
                 i.e. the level STOP_PERCENTILE% of trades stayed above.
    """
    if len(mfe_arr) == 0 or len(mae_arr) == 0:
        return [], 0.0
    targets: list = []
    for pct_rank, book in zip(TARGET_PERCENTILES, BOOK_FRACTIONS):
        tgt = float(np.percentile(mfe_arr, pct_rank))
        hit = float(np.mean(mfe_arr >= tgt))
        targets.append(Target(pct=round(tgt, 1), book_pct=int(book),
                              hit_rate=round(hit, 2)))
    stop = float(np.percentile(mae_arr, 100 - STOP_PERCENTILE))
    return targets, round(stop, 1)


def analyze(
    entries: pd.DataFrame,
    ohlcv: dict,
    strategy: str,
    data_quality: str,
    bucket: str = "ALL",
    max_horizon: int = MAX_HORIZON_DAYS,
) -> Recommendation | None:
    """Compute a single Recommendation, or None if fewer than MIN_SAMPLE usable
    entries have price data."""
    paths, mfe_arr, mae_arr, _skipped = build_matrix(entries, ohlcv, max_horizon)
    if len(paths) < MIN_SAMPLE:
        return None

    curve = aggregate_curve(paths, max_horizon)
    hold_days, hold_med, hold_win = best_hold_day(curve)
    targets, stop = exit_ladder(mfe_arr, mae_arr)

    return Recommendation(
        strategy=strategy,
        bucket=bucket,
        hold_days=hold_days,
        hold_median_return=round(hold_med, 2),
        hold_win_rate=round(hold_win, 2),
        targets=targets,
        stop_pct=stop,
        sample_size=len(paths),
        data_quality=data_quality,
        curve=[{k: round(float(v), 3) for k, v in row.items()}
               for row in curve.to_dict("records")],
    )


def analyze_with_buckets(
    entries: pd.DataFrame,
    ohlcv: dict,
    strategy: str,
    data_quality: str,
    bucket_col: str | None = None,
    max_horizon: int = MAX_HORIZON_DAYS,
) -> dict:
    """Return {'ALL': Recommendation, <bucket>: Recommendation, ...}.

    The 'ALL' key is always attempted. If bucket_col is given, each bucket value
    with >= MIN_SAMPLE entries also gets its own recommendation; smaller buckets
    are skipped (callers fall back to 'ALL'). Buckets that fail the price-data
    threshold inside analyze() are also skipped.
    """
    out: dict = {}
    all_rec = analyze(entries, ohlcv, strategy, data_quality, "ALL", max_horizon)
    if all_rec is not None:
        out["ALL"] = all_rec

    if bucket_col and bucket_col in entries.columns:
        for val, grp in entries.groupby(bucket_col):
            if str(val) == "ALL":
                continue
            if grp[bucket_col].isna().all() or len(grp) < MIN_SAMPLE:
                continue
            rec = analyze(grp, ohlcv, strategy, data_quality, str(val), max_horizon)
            if rec is not None:
                out[str(val)] = rec
    return out
