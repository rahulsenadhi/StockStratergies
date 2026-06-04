"""Canonical KPI contract — single source of truth for the leaderboard (S1).

compute_kpis() reads a strategy's equity (and optional trades) CSV — whatever
column schema it uses — and returns one normalized KPI dict. Annualization is
frequency-inferred so daily and monthly equity curves are both handled.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd


class KpiError(Exception):
    """Raised when a strategy's equity CSV is missing/empty/unusable."""


_EQUITY_COL_CANDIDATES = ["Portfolio_Value", "Equity", "equity"]
_DATE_COL_CANDIDATES = ["Date", "date", "Datetime"]
BENCHMARK_DEFAULT = "^NSEI"
_BENCHMARK_CSV = "data/nse_bse/^NSEI.csv"


def _read_csv(path) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        raise KpiError(f"missing CSV: {path}")
    try:
        df = pd.read_csv(p)
    except Exception as e:  # malformed file
        raise KpiError(f"unreadable CSV {path}: {e}")
    if df.empty:
        raise KpiError(f"empty CSV: {path}")
    return df


def _date_col(df: pd.DataFrame) -> str:
    for c in _DATE_COL_CANDIDATES:
        if c in df.columns:
            return c
    return df.columns[0]


def resolve_equity_col(df: pd.DataFrame, equity_col: str | None = None) -> str:
    if equity_col:
        if equity_col not in df.columns:
            raise KpiError(f"equity_col '{equity_col}' not in {list(df.columns)}")
        return equity_col
    for c in _EQUITY_COL_CANDIDATES:
        if c in df.columns:
            return c
    date_c = _date_col(df)
    for c in df.columns:
        if c != date_c and pd.api.types.is_numeric_dtype(df[c]):
            return c
    raise KpiError(f"no numeric equity column in {list(df.columns)}")


def _equity_series(df: pd.DataFrame, equity_col: str) -> pd.Series:
    dc = _date_col(df)
    s = df[[dc, equity_col]].copy()
    s[dc] = pd.to_datetime(s[dc], errors="coerce")
    s = s.dropna().sort_values(dc).set_index(dc)[equity_col].astype(float)
    if len(s) < 2:
        raise KpiError("equity series has < 2 points")
    return s


def _periods_per_year(idx: pd.DatetimeIndex) -> float:
    spacing = np.median(np.diff(idx.values).astype("timedelta64[D]").astype(float))
    if spacing <= 0:
        return 252.0
    return max(1.0, round(365.25 / spacing))


def _equity_metrics(eq: pd.Series) -> dict:
    initial, final = float(eq.iloc[0]), float(eq.iloc[-1])
    years = max((eq.index[-1] - eq.index[0]).days / 365.25, 1 / 365.25)
    cagr = (final / initial) ** (1 / years) - 1 if initial > 0 else 0.0
    total_return = (final / initial - 1) if initial > 0 else 0.0
    rets = eq.pct_change().dropna()
    ppy = _periods_per_year(eq.index)
    std = float(rets.std())
    vol = std * np.sqrt(ppy) if std > 0 else 0.0
    sharpe = (float(rets.mean()) / std) * np.sqrt(ppy) if std > 0 else 0.0
    peak = eq.cummax()
    max_dd = float(((eq - peak) / peak).min())
    calmar = (cagr / abs(max_dd)) if max_dd != 0 else None
    return {
        "cagr": float(cagr), "total_return": float(total_return),
        "volatility": float(vol), "sharpe": float(sharpe),
        "max_dd": max_dd, "calmar": calmar, "final_equity": final,
    }


# ---------------------------------------------------------------------------
# Task 2: win_rate (multi-source) + alpha vs benchmark
# ---------------------------------------------------------------------------

_PNL_COL_CANDIDATES = ["PnL_Pct", "return_pct", "PnL"]


def _as_fraction(series: pd.Series) -> pd.Series:
    """Treat a clearly-percent column (abs median > 1.5) as percent -> fraction."""
    s = pd.to_numeric(series, errors="coerce").dropna()
    if len(s) and s.abs().median() > 1.5:
        return s / 100.0
    return s


def _win_rate(trades_csv, pnl_col: str | None) -> tuple[float | None, int]:
    if trades_csv is None or not Path(trades_csv).exists():
        return None, 0
    try:
        tdf = pd.read_csv(trades_csv)
    except Exception:
        return None, 0
    if tdf.empty:
        return None, 0
    n = len(tdf)
    col = pnl_col or next((c for c in _PNL_COL_CANDIDATES if c in tdf.columns), None)
    if col is not None:
        vals = _as_fraction(tdf[col])
        if len(vals):
            return float((vals > 0).mean()), n
    if "Result" in tdf.columns:
        res = tdf["Result"].astype(str).str.upper()
        wins = res.isin(["WIN", "W", "TRUE", "PROFIT"])
        if wins.any() or res.isin(["LOSS", "L", "FALSE"]).any():
            return float(wins.mean()), n
    return None, n


def _benchmark_cagr(eq_index, benchmark_loader) -> float | None:
    loader = benchmark_loader or _default_benchmark_loader
    try:
        bench = loader()
    except Exception:
        return None
    if bench is None or len(bench) < 2:
        return None
    bench = bench.reindex(bench.index.union(eq_index)).ffill().reindex(eq_index).dropna()
    if len(bench) < 2 or bench.iloc[0] <= 0:
        return None
    years = max((bench.index[-1] - bench.index[0]).days / 365.25, 1 / 365.25)
    return (float(bench.iloc[-1]) / float(bench.iloc[0])) ** (1 / years) - 1


def _default_benchmark_loader() -> pd.Series | None:
    p = Path(_BENCHMARK_CSV)
    if not p.exists():
        return None
    df = pd.read_csv(p)
    dc = _date_col(df)
    df[dc] = pd.to_datetime(df[dc], errors="coerce")
    return df.dropna(subset=[dc]).set_index(dc)["Close"].astype(float)


def compute_kpis(
    equity_csv,
    trades_csv=None,
    *,
    benchmark: str = BENCHMARK_DEFAULT,
    equity_col: str | None = None,
    benchmark_col: str | None = None,
    pnl_col: str | None = None,
    benchmark_loader: Callable[[], pd.Series] | None = None,
) -> dict:
    """Return the canonical KPI dict for one strategy. Raises KpiError on bad equity."""
    edf = _read_csv(equity_csv)
    ecol = resolve_equity_col(edf, equity_col)
    eq = _equity_series(edf, ecol)
    out = _equity_metrics(eq)

    out["win_rate"], out["num_trades"] = _win_rate(trades_csv, pnl_col)

    if benchmark_col and benchmark_col in edf.columns:
        bench_series = _equity_series(edf, benchmark_col)
        bench_cagr = _benchmark_cagr(eq.index, lambda: bench_series)
    else:
        bench_cagr = _benchmark_cagr(eq.index, benchmark_loader)
    out["alpha"] = (out["cagr"] - bench_cagr) if bench_cagr is not None else None
    return out
