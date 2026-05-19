"""Vectorized indicator helpers shared across strategies.

All functions return pandas Series aligned to the input index. No look-ahead.
For strategy signal logic, callers should `.shift(1)` themselves — these helpers
compute the raw indicator at bar T.
"""

import numpy as np
import pandas as pd


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(period).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def true_range(df: pd.DataFrame) -> pd.Series:
    """Wilder True Range. df must contain High, Low, Close."""
    high, low, close = df['High'], df['Low'], df['Close']
    prev_c = close.shift(1)
    return pd.concat([
        high - low,
        (high - prev_c).abs(),
        (low - prev_c).abs(),
    ], axis=1).max(axis=1)


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    return true_range(df).rolling(period).mean()


def choppiness(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Choppiness Index: 100 × log10(SUM(TR,n) / (n-bar High − n-bar Low)) / log10(n).

    ~38 = trending, ~100 = choppy. Common threshold 61.8.
    """
    tr = true_range(df)
    atr_sum = tr.rolling(period).sum()
    high_max = df['High'].rolling(period).max()
    low_min = df['Low'].rolling(period).min()
    hl_range = (high_max - low_min).replace(0, np.nan)
    return 100 * np.log10(atr_sum / hl_range) / np.log10(period)


def rolling_high(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(period).max()


def rolling_low(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(period).min()


def all_time_high(series: pd.Series) -> pd.Series:
    return series.expanding().max()


def momentum_pct(close: pd.Series, period: int = 126) -> pd.Series:
    """N-period return (e.g., 126 ≈ 6-month momentum)."""
    return close.pct_change(period)


def rolling_volatility(close: pd.Series, period: int = 20) -> pd.Series:
    """Annualized rolling std of daily returns. √252 scaler."""
    returns = close.pct_change()
    return returns.rolling(period).std() * np.sqrt(252)


def relative_strength(
    stock_close: pd.Series,
    benchmark_close: pd.Series,
    period: int = 126,
) -> pd.Series:
    """RS = (stock N-period return − benchmark N-period return) / benchmark vol.

    Used by Nifty Rotation. Volatility-normalized to compare across regimes.
    """
    stock_ret = stock_close.pct_change(period)
    bench_ret = benchmark_close.reindex(stock_close.index).ffill().pct_change(period)
    bench_vol = benchmark_close.reindex(stock_close.index).ffill().pct_change().rolling(period).std()
    return (stock_ret - bench_ret) / bench_vol.replace(0, np.nan)


def dip_flag(close: pd.Series, ema_line: pd.Series, lookback: int) -> pd.Series:
    """True at bar T if close was below ema_line at any point in the last `lookback` bars."""
    below = (close < ema_line).astype(int)
    return below.rolling(lookback).max().astype(bool)


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Wilder RSI. Returns 0-100. Overbought >70, oversold <30."""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def macd(close: pd.Series, fast: int = 12, slow: int = 26,
         signal: int = 9) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Returns (macd_line, signal_line, histogram). Histogram = macd - signal."""
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    sig_line  = macd_line.ewm(span=signal, adjust=False).mean()
    hist      = macd_line - sig_line
    return macd_line, sig_line, hist


def bollinger(close: pd.Series, period: int = 20,
              num_std: float = 2.0) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Returns (middle_band, upper_band, lower_band). Middle = SMA, bands = ±k·σ."""
    mid = close.rolling(period).mean()
    std = close.rolling(period).std()
    upper = mid + num_std * std
    lower = mid - num_std * std
    return mid, upper, lower


def adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Wilder ADX. <20 = weak trend, 20-25 = developing, >25 = strong, >40 = very strong."""
    high, low, close = df['High'], df['Low'], df['Close']
    up_move   = high.diff()
    down_move = -low.diff()
    plus_dm   = pd.Series(
        np.where((up_move > down_move) & (up_move > 0), up_move, 0.0),
        index=df.index,
    )
    minus_dm  = pd.Series(
        np.where((down_move > up_move) & (down_move > 0), down_move, 0.0),
        index=df.index,
    )
    tr = true_range(df)
    # Wilder smoothing via EMA with alpha=1/period
    atr_w  = tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    plus_di  = 100 * plus_dm.ewm(alpha=1 / period, adjust=False, min_periods=period).mean() / atr_w.replace(0, np.nan)
    minus_di = 100 * minus_dm.ewm(alpha=1 / period, adjust=False, min_periods=period).mean() / atr_w.replace(0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """On-Balance Volume. Cumulative volume signed by close direction."""
    direction = np.sign(close.diff()).fillna(0)
    return (direction * volume).cumsum()


def all_indicators(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Compute the common indicator bundle. Returns a new DataFrame indexed like df.

    Reads from cfg with sensible defaults so partial cfg dicts work.
    Does NOT apply min_bars / liquidity filters — caller's job.
    """
    close = df['Close']
    volume = df['Volume']

    ind = pd.DataFrame(index=df.index)
    ind['open']   = df['Open']
    ind['close']  = close
    ind['volume'] = volume

    sma50_p  = cfg.get('sma50_period', 50)
    sma150_p = cfg.get('sma150_period', 150)
    ema220_p = cfg.get('ema220_period', 220)
    high_p   = cfg.get('high52w_period', 252)
    low_p    = cfg.get('low52w_period', 252)
    chop_p   = cfg.get('choppiness_period', 14)
    mom_p    = cfg.get('momentum_period', 126)
    volavg_p = cfg.get('vol_avg_period', 20)
    vollb_p  = cfg.get('vol_lookback_days', 50)
    dip_p    = cfg.get('ema_dip_lookback', 90)

    ind['sma50']     = sma(close, sma50_p)
    ind['sma150']    = sma(close, sma150_p)
    ind['ema220']    = ema(close, ema220_p)
    ind['high52w']   = rolling_high(close, high_p)
    ind['low52w']    = rolling_low(close, low_p)
    ind['ath']       = all_time_high(close)
    ind['vol_avg20'] = sma(volume, volavg_p)
    ind['vol_avg50'] = sma(volume, vollb_p)
    ind['choppiness']  = choppiness(df, chop_p)
    ind['momentum_6m'] = momentum_pct(close, mom_p)
    ind['had_ema_dip'] = dip_flag(close, ind['ema220'], dip_p)

    return ind
