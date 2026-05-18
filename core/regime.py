"""Market regime gate.

Single source for the three-condition Nifty regime filter used by Momentum Edge.
Extracted verbatim from momentum_edge_backtest.py:232 so behavior is identical.

Conditions (all True → BULL → allow new entries):
    C1: benchmark_close  > benchmark_SMA_slow
    C2: benchmark_SMA_fast > benchmark_SMA_slow
    C3: benchmark_close  >= (1 − max_dd_from_high) × benchmark_52W_high

Returns a boolean Series aligned to the benchmark index.
"""

import pandas as pd

DEFAULTS = {
    'regime_sma_fast':         50,
    'regime_sma_slow':         200,
    'regime_52w_period':       252,
    'regime_max_dd_from_high': 0.10,
    'use_regime_filter':       True,
}


def build_series(benchmark: pd.Series | None, cfg: dict | None = None) -> pd.Series | None:
    """Return boolean market_on series. None if filter disabled or benchmark missing."""
    if benchmark is None:
        return None
    c = {**DEFAULTS, **(cfg or {})}
    if not c['use_regime_filter']:
        return None

    sma_fast = benchmark.rolling(c['regime_sma_fast']).mean()
    sma_slow = benchmark.rolling(c['regime_sma_slow']).mean()
    high_52w = benchmark.rolling(c['regime_52w_period']).max()
    floor = (1 - c['regime_max_dd_from_high']) * high_52w
    return (benchmark > sma_slow) & (sma_fast > sma_slow) & (benchmark >= floor)


def label(regime_on: bool | None) -> str:
    """Pretty label for UI banners."""
    if regime_on is None:
        return 'Unknown'
    return 'Bull' if regime_on else 'Bear / Sideways'


def bars_since_flip(series: pd.Series) -> int:
    """How many bars since regime last flipped value. Useful for dashboard banner."""
    if series is None or series.empty:
        return 0
    last = series.iloc[-1]
    s = series.dropna()
    flips = (s != s.shift(1)).cumsum()
    last_group = flips.iloc[-1]
    return int((flips == last_group).sum())
