"""Backtest KPIs and SUE-decile diagnostic."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd


def _max_drawdown(equity: pd.Series) -> float:
    peak = equity.cummax()
    dd = (equity - peak) / peak
    return float(dd.min())


def compute_kpis(equity_curve: pd.DataFrame, trades: pd.DataFrame) -> dict[str, float]:
    eq = equity_curve["equity"].astype(float)
    days = (equity_curve["date"].iloc[-1] - equity_curve["date"].iloc[0]).days
    years = max(days / 365.25, 1e-6)
    final = eq.iloc[-1]
    initial = eq.iloc[0]
    cagr = (final / initial) ** (1 / years) - 1
    returns = eq.pct_change().dropna()
    sharpe = (returns.mean() / returns.std()) * np.sqrt(252) if returns.std() > 0 else 0
    downside = returns[returns < 0]
    sortino = (returns.mean() / downside.std()) * np.sqrt(252) if len(downside) and downside.std() > 0 else 0
    mdd = _max_drawdown(eq)

    if trades.empty:
        win_rate = 0.0
        avg_win = avg_loss = best = worst = 0.0
        avg_hold = 0
    else:
        wins = trades[trades["return_pct"] > 0]
        losses = trades[trades["return_pct"] <= 0]
        win_rate = len(wins) / len(trades)
        avg_win = float(wins["return_pct"].mean()) if len(wins) else 0.0
        avg_loss = float(losses["return_pct"].mean()) if len(losses) else 0.0
        best = float(trades["return_pct"].max())
        worst = float(trades["return_pct"].min())
        avg_hold = float(trades.get("hold_days", pd.Series([0])).mean())

    return {
        "cagr": float(cagr),
        "sharpe": float(sharpe),
        "sortino": float(sortino),
        "max_dd": float(mdd),
        "win_rate": float(win_rate),
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "best_trade": best,
        "worst_trade": worst,
        "avg_hold_days": avg_hold,
        "num_trades": int(len(trades)),
    }


def compute_decile_spread(events: pd.DataFrame) -> pd.Series:
    """Avg `fwd_60d_return` per SUE decile. Caller pre-computes fwd_60d_return."""
    df = events.dropna(subset=["sue_decile", "fwd_60d_return"])
    return df.groupby("sue_decile")["fwd_60d_return"].mean()


def attach_fwd_60d(events: pd.DataFrame, closes: pd.DataFrame, hold_td: int = 60) -> pd.DataFrame:
    """Append fwd_60d_return column for decile diagnostic.

    For each event, look up close at result_date+1td and result_date+1td+hold_td.
    """
    events = events.copy()
    idx = closes.index
    rets: list[float] = []
    for _, row in events.iterrows():
        tk = row["ticker"]
        if tk not in closes.columns:
            rets.append(math.nan)
            continue
        rd = pd.Timestamp(row["result_date"])
        pos = idx.searchsorted(rd, side="right")
        if pos + hold_td >= len(idx):
            rets.append(math.nan)
            continue
        entry_px = closes.iloc[pos][tk]
        exit_px = closes.iloc[pos + hold_td][tk]
        if pd.isna(entry_px) or pd.isna(exit_px) or entry_px <= 0:
            rets.append(math.nan)
            continue
        rets.append((exit_px - entry_px) / entry_px * 100.0)
    events["fwd_60d_return"] = rets
    return events
