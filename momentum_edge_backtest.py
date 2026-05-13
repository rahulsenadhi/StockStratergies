"""
Momentum Edge Strategy — Backtester
220-EMA shakeout-recovery ATH breakout strategy across full NSE + BSE universe.

Run order:
  Step 1 (once): python build_universe.py
  Step 2:        python nse_bse_downloader.py
  Step 3:        python momentum_edge_backtest.py
"""

import sys
import warnings
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# ═══════════════════════════════════════════════════════════════════════════════
#  CONFIG
# ═══════════════════════════════════════════════════════════════════════════════

CFG = {
    # ── Universe ──────────────────────────────────────────────────────────────
    # 'NIFTY500'      → uses data from momentum_edge_data/ (legacy, fast testing)
    # 'FULL_NSE_BSE'  → uses data from ./data/ (full universe, complete run)
    'backtest_universe':   'FULL_NSE_BSE',
    'data_folder_legacy':  'momentum_edge_data',
    'data_folder_full':    './data/nse_bse',
    'universe_file':       './data/universe/combined_universe.csv',

    # ── Capital & sizing ──────────────────────────────────────────────────────
    'initial_capital':     10_00_000,   # ₹10 lakh starting capital
    'max_position_value':   1_00_000,   # ₹1 lakh per position (10%)
    'max_positions':        10,         # hold at most 10 stocks simultaneously

    # ── Market regime filter ──────────────────────────────────────────────────
    'use_regime_filter':          True,        # block new entries in bear market
    'benchmark_ticker':           '^NSEI',     # Nifty 50 index
    'benchmark_file_full':        './data/nse_bse/^NSEI.csv',
    'benchmark_file_legacy':      './data/^NSEI.csv',
    # Three-condition regime gate (all must be TRUE for market_on):
    #   C1: NIFTY_close > NIFTY_SMA_200
    #   C2: NIFTY_SMA_50 > NIFTY_SMA_200
    #   C3: NIFTY_close >= (1 - regime_max_dd_from_high) × NIFTY_52W_high
    'regime_sma_fast':            50,          # NIFTY_SMA_50
    'regime_sma_slow':            200,         # NIFTY_SMA_200
    'regime_52w_period':          252,         # REGIME_LOOKBACK_52W
    'regime_max_dd_from_high':    0.10,        # REGIME_MAX_DRAWDOWN_FROM_HIGH

    # ── Indicator periods ─────────────────────────────────────────────────────
    'sma50_period':        50,
    'sma150_period':       150,
    'ema220_period':       220,
    'high52w_period':      252,
    'low52w_period':       252,
    'vol_avg_period':      20,
    'ema_dip_lookback':    90,          # stock must have dipped within 90 bars
    'choppiness_period':   14,
    'choppiness_threshold':61.8,
    'momentum_period':     126,         # 6-month momentum (≈126 trading days)

    # ── Entry filters ─────────────────────────────────────────────────────────
    'min_price_vs_low':    1.25,        # close >= 1.25 × 52-week low
    'vol_filter':          True,
    'vol_threshold':       1.5,         # breakout volume > 1.5× 20-day avg
    'vol_lookback_days':   50,          # VOLUME_LOOKBACK_DAYS (50-day avg for additional check)
    'vol_multiplier':      1.5,         # VOLUME_MULTIPLIER (used with 50-day avg)

    # ── Recovery filter ───────────────────────────────────────────────────────
    'prefer_fast_recovery':True,        # skip Slow (>60d) recovery setups
    'max_recovery_days':   90,          # ignore reclaims that took > 90 days

    # ── Exit rules ────────────────────────────────────────────────────────────
    'stop_loss_pct':       0.15,        # hard stop: 15% below entry

    # ── Minimum bars ─────────────────────────────────────────────────────────
    # B1 FIX: spec requires 300 days minimum data, not 260
    'min_bars':            300,

    # ── Liquidity filter ──────────────────────────────────────────────────────
    # B5 FIX: skip stocks where avg daily volume < 100,000 (last 30 days)
    'min_avg_volume':      100_000,

    # ── Output paths ─────────────────────────────────────────────────────────
    'trades_out':          'momentum_edge_trades.csv',
    'equity_out':          'momentum_edge_equity.csv',
    'chart_out':           'momentum_edge_chart.png',

    # ── Debug ─────────────────────────────────────────────────────────────────
    'diagnostic_mode':     True,
}

# ═══════════════════════════════════════════════════════════════════════════════
#  DATA LOADING
# ═══════════════════════════════════════════════════════════════════════════════

def _load_csv(path: Path) -> pd.DataFrame | None:
    """Load a single OHLCV CSV. Returns None on any failure."""
    try:
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        # B7 FIX: plain date strings have no timezone; utc=True was wrong.
        # If already tz-aware (rare), strip with tz_convert; otherwise just parse.
        idx = pd.to_datetime(df.index, errors='coerce')
        if idx.tz is not None:
            idx = idx.tz_convert(None)
        df.index = idx
        df.index.name = 'Date'
        needed = [c for c in ['Open', 'High', 'Low', 'Close', 'Volume'] if c in df.columns]
        if len(needed) < 5:
            return None
        df = df[needed].copy()
        df = df.dropna(subset=['Close'])
        df.sort_index(inplace=True)
        return df if len(df) >= 10 else None
    except Exception:
        return None


def load_ohlcv(cfg: dict) -> dict[str, pd.DataFrame]:
    """
    Load all stock OHLCV CSVs based on BACKTEST_UNIVERSE config.
    'FULL_NSE_BSE' → ./data/*.csv (from nse_bse_downloader.py)
    'NIFTY500'     → momentum_edge_data/*.csv (legacy)
    """
    universe = cfg.get('backtest_universe', 'NIFTY500')

    if universe == 'FULL_NSE_BSE':
        folder = Path(cfg['data_folder_full'])
    else:
        folder = Path(cfg['data_folder_legacy'])

    if not folder.exists():
        raise FileNotFoundError(
            f"Data folder '{folder}' not found.\n"
            f"Run: python {'nse_bse_downloader.py' if universe == 'FULL_NSE_BSE' else 'momentum_edge_downloader.py'}"
        )

    # Determine which symbols to load
    symbol_whitelist = None
    universe_file = Path(cfg.get('universe_file', ''))
    if universe == 'FULL_NSE_BSE' and universe_file.exists():
        try:
            u = pd.read_csv(universe_file)
            if 'Symbol' in u.columns:
                symbol_whitelist = set(u['Symbol'].str.strip().tolist())
        except Exception:
            pass

    # Skip benchmark / summary files
    skip_stems = {'^NSEI', 'NIFTYBEES.NS', 'me_summary', 'download_status'}

    ohlcv = {}
    csv_files = sorted(folder.glob('*.csv'))
    total = len(csv_files)
    loaded = 0

    for csv_file in csv_files:
        stem = csv_file.stem
        if stem in skip_stems:
            continue
        if symbol_whitelist is not None and stem not in symbol_whitelist:
            continue
        df = _load_csv(csv_file)
        if df is not None and len(df) >= cfg['min_bars']:
            ohlcv[stem] = df
            loaded += 1
        if loaded % 500 == 0 and loaded > 0:
            print(f'  Loaded {loaded}/{total} symbols…', end='\r', flush=True)

    print(f'  Loaded {loaded} symbols from {folder}/' + ' ' * 20)
    return ohlcv


def load_benchmark(cfg: dict) -> pd.Series | None:
    """Load Nifty 50 (or NiftyBees) Close series for regime filter and benchmark."""
    universe = cfg.get('backtest_universe', 'NIFTY500')
    paths_to_try = [
        Path(cfg.get('benchmark_file_full', '')),
        Path(cfg.get('benchmark_file_legacy', '')),
        Path(cfg['data_folder_full']) / '^NSEI.csv',
        Path(cfg['data_folder_legacy']) / 'NIFTYBEES.NS.csv',
    ]
    for path in paths_to_try:
        if path.exists():
            df = _load_csv(path)
            if df is not None:
                col = 'Close' if 'Close' in df.columns else df.columns[0]
                return df[col].dropna()
    return None


# ═══════════════════════════════════════════════════════════════════════════════
#  MARKET REGIME FILTER
# ═══════════════════════════════════════════════════════════════════════════════

def build_regime_series(benchmark: pd.Series | None, cfg: dict) -> pd.Series | None:
    """
    Returns a boolean Series (market_on) indexed by date.
    True  = BULL → allow new entries
    False = BEAR → block new entries (existing positions still managed)

    market_on = True only when ALL three conditions hold on day T:
      C1: NIFTY_close_T  > NIFTY_SMA_200_T
      C2: NIFTY_SMA_50_T > NIFTY_SMA_200_T
      C3: NIFTY_close_T  >= (1 - regime_max_dd_from_high) × NIFTY_52W_high_T
    """
    if benchmark is None or not cfg.get('use_regime_filter', True):
        return None
    sma_fast = benchmark.rolling(cfg['regime_sma_fast']).mean()
    sma_slow = benchmark.rolling(cfg['regime_sma_slow']).mean()
    high_52w = benchmark.rolling(cfg['regime_52w_period']).max()
    floor    = (1 - cfg['regime_max_dd_from_high']) * high_52w
    c1 = benchmark > sma_slow
    c2 = sma_fast  > sma_slow
    c3 = benchmark >= floor
    return (c1 & c2 & c3)


# ═══════════════════════════════════════════════════════════════════════════════
#  INDICATOR HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _compute_choppiness(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Choppiness Index: 100 × log10(SUM(TR, n) / (n-bar High − n-bar Low)) / log10(n)
    Range ~38 (trending) to ~100 (choppy). Threshold 61.8 separates clean from noisy.
    """
    high, low, close = df['High'], df['Low'], df['Close']
    prev_c = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_c).abs(),
        (low  - prev_c).abs(),
    ], axis=1).max(axis=1)
    atr_sum  = tr.rolling(period).sum()
    high_max = high.rolling(period).max()
    low_min  = low.rolling(period).min()
    hl_range = (high_max - low_min).replace(0, np.nan)
    return 100 * np.log10(atr_sum / hl_range) / np.log10(period)


def _compute_recovery_speed(close: pd.Series, ema220: pd.Series,
                             lookback: int = 90) -> tuple[str, int]:
    """
    Returns (label, days) from the dip low to first EMA220 reclaim.
    Labels: 'Fast' (≤30d), 'Normal' (31-60d), 'Slow' (61-90d), 'No Reclaim' (-1).
    """
    if len(close) < 2:
        return 'No Reclaim', -1

    c = close.values[-lookback:]
    e = ema220.values[-lookback:]
    m = len(c)

    if m < 2 or c[-1] < e[-1]:
        return 'No Reclaim', -1

    # Find last bar where close was below EMA (end of most recent dip)
    dip_end = -1
    for j in range(m - 2, -1, -1):
        if c[j] < e[j]:
            dip_end = j
            break
    if dip_end == -1:
        return 'No Reclaim', -1

    # Walk back to find start of that contiguous dip episode
    dip_start = dip_end
    for j in range(dip_end - 1, -1, -1):
        if c[j] < e[j]:
            dip_start = j
        else:
            break

    # Index of lowest close inside dip episode
    dip_low_idx = dip_start + int(np.argmin(c[dip_start: dip_end + 1]))

    # First bar after dip low where close >= EMA
    reclaim_idx = -1
    for j in range(dip_low_idx + 1, m):
        if c[j] >= e[j]:
            reclaim_idx = j
            break
    if reclaim_idx == -1:
        return 'No Reclaim', -1

    days = reclaim_idx - dip_low_idx
    if days <= 30:
        return 'Fast', days
    elif days <= 60:
        return 'Normal', days
    else:
        return 'Slow', days


# ═══════════════════════════════════════════════════════════════════════════════
#  INDICATOR ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

def compute_indicators(df: pd.DataFrame, cfg: dict) -> pd.DataFrame | None:
    """
    Compute all strategy indicators. Returns None if stock has too few bars.

    LOOK-AHEAD BIAS PREVENTION: all _s columns are .shift(1) of their base.
    Signal logic must ONLY read _s columns.
    """
    if len(df) < cfg['min_bars']:
        return None

    close  = df['Close']
    volume = df['Volume']

    # B5 FIX: absolute liquidity filter — skip stocks with avg daily vol < 100,000 (last 30d)
    min_vol = cfg.get('min_avg_volume', 100_000)
    if volume.iloc[-30:].mean() < min_vol:
        return None

    ind = pd.DataFrame(index=df.index)
    ind['open']   = df['Open']
    ind['close']  = close
    ind['volume'] = volume

    # Moving averages
    ind['sma50']  = close.rolling(cfg['sma50_period']).mean()
    ind['sma150'] = close.rolling(cfg['sma150_period']).mean()
    ind['ema220'] = close.ewm(span=cfg['ema220_period'], adjust=False).mean()

    # 52-week high/low (close-based only, no look-ahead from High/Low columns)
    ind['high52w'] = close.rolling(cfg['high52w_period']).max()
    ind['low52w']  = close.rolling(cfg['low52w_period']).min()

    # All-time high — entry_type label only; breakout check uses high52w_s (see B2 fix)
    ath = close.expanding().max()
    ind['ath']      = ath
    ind['ath_prev'] = ath.shift(1)   # ATH through yesterday
    # Bug 5 fix: ATH = today's close exceeds yesterday's all-time high (true new ATH breakout)
    # 52W_HIGH_FALLBACK = only broke the 52-week high, ATH is higher
    ind['entry_type'] = np.where(
        close > ind['ath_prev'], 'ATH', '52W_HIGH_FALLBACK'
    )

    ind['vol_avg20'] = volume.rolling(cfg['vol_avg_period']).mean()
    ind['vol_avg50'] = volume.rolling(cfg['vol_lookback_days']).mean()

    # 90-day EMA dip flag
    dip_flag           = (close < ind['ema220']).astype(int)
    ind['had_ema_dip'] = dip_flag.rolling(cfg['ema_dip_lookback']).max().astype(bool)

    # Choppiness Index
    ind['choppiness'] = _compute_choppiness(df, cfg['choppiness_period'])

    # 6-month momentum (for scoring)
    ind['momentum_6m'] = close.pct_change(cfg['momentum_period'])

    # ── Shifted columns (signal logic uses ONLY these) ─────────────────────────
    ind['close_s']        = close.shift(1)
    ind['volume_s']       = volume.shift(1)
    ind['sma50_s']        = ind['sma50'].shift(1)
    ind['sma150_s']       = ind['sma150'].shift(1)
    ind['ema220_s']       = ind['ema220'].shift(1)
    ind['high52w_s']      = ind['high52w'].shift(1)
    ind['low52w_s']       = ind['low52w'].shift(1)
    ind['vol_avg20_s']    = ind['vol_avg20'].shift(1)
    ind['vol_avg50_s']    = ind['vol_avg50'].shift(1)
    ind['had_ema_dip_s']  = ind['had_ema_dip'].shift(1)
    ind['choppiness_s']   = ind['choppiness'].shift(1)
    ind['momentum_6m_s']  = ind['momentum_6m'].shift(1)
    # B2 FIX: breakout_ref_s removed — was ath.shift(2), i.e., double-shifted.
    # check_volume_and_breakout now uses row['close'] (today) vs row['high52w_s'] (yesterday's 52W high),
    # which correctly implements: Close[T] > 52W_High[T-1] per spec.

    # Drop rows where core indicators are not yet computed
    required = ['ema220', 'sma150', 'sma50', 'close']
    ind = ind.dropna(subset=required)
    if len(ind) < 260:
        return None

    return ind


# ═══════════════════════════════════════════════════════════════════════════════
#  FILTER PIPELINE  (F1–F6)
# ═══════════════════════════════════════════════════════════════════════════════

def check_filters(row: pd.Series, cfg: dict) -> tuple[bool, int]:
    """
    Apply all 6 entry filters. Returns (passed_all, last_filter_passed).
    Uses _s (shifted) columns to prevent look-ahead bias.
    """
    # Guard: all required shifted columns must be present and non-NaN
    required_s = ('sma50_s', 'sma150_s', 'ema220_s', 'low52w_s', 'vol_avg20_s')
    for col in required_s:
        if pd.isna(row.get(col)):
            return False, 0

    # F1: SMA150 > EMA220 — long-term trend is bullish
    if not (row['sma150_s'] > row['ema220_s']):
        return False, 1

    # F2: Close > SMA50 — short-term strength
    if not (row['close_s'] > row['sma50_s']):
        return False, 2

    # F3: SMA50 > SMA150 — short-term MA above long-term MA
    if not (row['sma50_s'] > row['sma150_s']):
        return False, 3

    # F4: Close >= 1.25× 52-week low — not a beaten-down stock
    if not (row['close_s'] >= cfg['min_price_vs_low'] * row['low52w_s']):
        return False, 4

    # F5: Had EMA dip in last 90 days — shakeout confirmed
    if not bool(row.get('had_ema_dip_s', False)):
        return False, 5

    # F6: Choppiness < 61.8 — clean trending chart
    chop = row.get('choppiness_s')
    if chop is not None and not pd.isna(chop):
        if chop > cfg['choppiness_threshold']:
            return False, 6

    return True, 6


def check_volume_and_breakout(row: pd.Series, cfg: dict) -> bool:
    """
    Signal checks after filters pass.

    B2 FIX: Breakout uses row['close'] (today's close, day T) vs row['high52w_s']
    (yesterday's 52W high, day T-1). This matches spec: Close[T] > 52W_High[T-1].
    The old code used close_s (T-1) vs breakout_ref_s (ath.shift(2) = T-2) — one day stale.

    B10 FIX: Strict > comparison (spec says Close > 52W_High.shift(1), not >=).
    """
    # Volume confirmation — today's volume vs shifted averages
    if cfg.get('vol_filter', True):
        vol_avg_s = row.get('vol_avg20_s', 0)
        vol_today = row.get('volume', row.get('volume_s'))   # prefer today's volume
        if vol_avg_s <= 0 or pd.isna(vol_today):
            return False
        # Existing 20-day check (unchanged)
        if vol_today < cfg['vol_threshold'] * vol_avg_s:
            return False
        # Additional 50-day check (vol_today >= VOLUME_MULTIPLIER × avg_vol_50)
        vol_avg50_s = row.get('vol_avg50_s')
        if vol_avg50_s is not None and not pd.isna(vol_avg50_s) and vol_avg50_s > 0:
            if vol_today < cfg.get('vol_multiplier', 1.5) * vol_avg50_s:
                return False

    # B2 FIX: use today's close vs yesterday's 52W high (spec: Close[T] > 52W_High[T-1])
    high52w_s = row.get('high52w_s')
    close_now  = row.get('close')
    if pd.isna(high52w_s) or pd.isna(close_now):
        return False
    # B10 FIX: strictly greater than (spec uses >, not >=)
    if close_now <= high52w_s:
        return False

    # Must also be above EMA220 on today's close (not shifted)
    ema220_now = row.get('ema220')
    if pd.isna(ema220_now) or close_now < ema220_now:
        return False

    return True


# ═══════════════════════════════════════════════════════════════════════════════
#  SEQUENTIAL SIGNAL VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════

def validate_sequential_signals(ind: pd.DataFrame, cfg: dict) -> tuple[bool, str, int]:
    """
    Validate that all 4 signals occurred in chronological order:
      Signal 1: Stock was near ATH before the dip (within 10%)
      Signal 2: Stock dipped below EMA220 (the flush)
      Signal 3: Sharp recovery above EMA220 within 90 days
      Signal 4: Current bar is breaking ATH/52W high with volume

    Returns (valid, recovery_label, recovery_days).
    Signal 4 is checked per-bar in run_backtest; this validates signals 1-3.
    """
    close  = ind['close']
    ema220 = ind['ema220']
    max_rec = cfg.get('max_recovery_days', 90)

    if len(close) < 2:
        return False, 'No Reclaim', -1

    c = close.values
    e = ema220.values
    n = len(c)

    # Signal 2: find most recent dip below EMA220
    dip_end = -1
    for j in range(n - 2, -1, -1):
        if c[j] < e[j]:
            dip_end = j
            break
    if dip_end == -1:
        return False, 'No Reclaim', -1

    # Find start of that contiguous dip episode
    dip_start = dip_end
    for j in range(dip_end - 1, -1, -1):
        if c[j] < e[j]:
            dip_start = j
        else:
            break

    # Signal 1: verify stock was near ATH BEFORE the dip
    pre_dip_close = c[:dip_start]
    if len(pre_dip_close) < 5:
        return False, 'No Reclaim', -1
    pre_dip_ath = pre_dip_close.max()
    dip_low     = c[dip_start: dip_end + 1].min()
    if pre_dip_ath <= 0:
        return False, 'No Reclaim', -1
    if dip_low > pre_dip_ath * 1.1:  # never actually dipped (gap down from ATH check)
        pass  # it's fine — just ensure it was within 10% before the dip
    if pre_dip_ath <= 0 or (pre_dip_close[-1] < pre_dip_ath * 0.90):
        return False, 'No Reclaim', -1

    # Signal 3: recovery above EMA220 within max_recovery_days
    dip_low_idx = dip_start + int(np.argmin(c[dip_start: dip_end + 1]))
    reclaim_idx = -1
    for j in range(dip_low_idx + 1, n):
        if c[j] >= e[j]:
            reclaim_idx = j
            break
    if reclaim_idx == -1:
        return False, 'No Reclaim', -1

    recovery_days = reclaim_idx - dip_low_idx
    if recovery_days > max_rec:
        return False, 'Slow', recovery_days

    if recovery_days <= 30:
        label = 'Fast'
    elif recovery_days <= 60:
        label = 'Normal'
    else:
        label = 'Slow'

    if cfg.get('prefer_fast_recovery', True) and label == 'Slow':
        return False, label, recovery_days

    return True, label, recovery_days


# ═══════════════════════════════════════════════════════════════════════════════
#  SCORING (100-point formula)
# ═══════════════════════════════════════════════════════════════════════════════

def score_signal_v2(row: pd.Series, rec_label: str,
                    all_momentum: list[float]) -> float:
    """
    100-point scoring system:
      A: 6-Month Momentum rank (40 pts) — ranked vs all qualifying stocks
      B: ATH Proximity           (30 pts) — how close price is to ATH
      C: Volume Strength         (20 pts) — vol ratio on breakout day
      D: Recovery Speed          (10 pts) — Fast/Normal/Slow

    all_momentum: list of 6-month momentum values for ALL qualifying stocks
                  (used to compute percentile rank for Score A)
    """
    # Score A — 6-month momentum percentile rank
    mom = row.get('momentum_6m_s', 0) or 0
    if all_momentum:
        rank_pct = sum(1 for m in all_momentum if m <= mom) / len(all_momentum)
    else:
        rank_pct = 0.5
    if rank_pct >= 0.90:
        score_a = 40
    elif rank_pct >= 0.75:
        score_a = 30
    elif rank_pct >= 0.50:
        score_a = 20
    else:
        score_a = 10

    # Score B — ATH proximity (capped at 1.0 so score_b cannot exceed 30)
    ath = row.get('ath_prev', 0) or row.get('breakout_ref_s', 0) or 0
    close_s = row.get('close_s', 0) or 0
    # B8 FIX: min(..., 1.0) prevents stocks already above ATH from scoring > 30
    ath_proximity = min((close_s / ath), 1.0) if ath > 0 else 0
    score_b = ath_proximity * 30

    # Score C — volume ratio (capped at 20)
    vol_avg = row.get('vol_avg20_s', 0) or 0
    vol_s   = row.get('volume_s', 0) or 0
    vol_ratio = (vol_s / vol_avg) if vol_avg > 0 else 0
    score_c = min(vol_ratio * 10, 20)

    # Score D — recovery speed
    recovery_pts = {'Fast': 10, 'Normal': 5, 'Slow': 2}
    score_d = recovery_pts.get(rec_label, 2)

    return round(score_a + score_b + score_c + score_d, 2)


# ═══════════════════════════════════════════════════════════════════════════════
#  BACKTEST SIMULATION
# ═══════════════════════════════════════════════════════════════════════════════

def run_backtest(indicators: dict[str, pd.DataFrame],
                 regime_series: pd.Series | None,
                 cfg: dict) -> tuple[list, list]:
    """
    Day-by-day portfolio simulation across full universe.

    Execution model (realistic, no look-ahead):
      • Signal generated at today's CLOSE
      • Entry executed at NEXT day's OPEN
      • Hard stop exits at TODAY's CLOSE (immediate)
      • EMA break exits at NEXT day's OPEN (queued)
    """
    all_tickers = list(indicators.keys())
    all_dates   = sorted(set(d for ind in indicators.values() for d in ind.index))

    initial_capital  = cfg['initial_capital']
    max_pos_value    = cfg['max_position_value']
    max_pos          = cfg['max_positions']
    cash             = float(initial_capital)

    positions    = {}   # ticker → {entry_price, shares, entry_date, exit_queued, ...}
    entry_queue  = {}   # ticker → signal metadata
    waitlist     = []   # [(score, ticker, metadata)] — when portfolio is full
    trades       = []
    equity_curve = []

    # B6 FIX: Pre-compute the FIRST DATE each ticker's sequential pattern becomes valid.
    # Old code validated using FULL history (look-ahead bias — a 2025 dip-recovery
    # would incorrectly pass a 2022 simulation date).
    # New approach: walk forward date-by-date for each ticker, record first valid date.
    # This is O(n_tickers × n_dates) but done once and gives correct per-date validity.
    print('  Pre-computing sequential signal first-valid-dates…', flush=True)
    seq_first_valid: dict[str, tuple] = {}   # ticker → (first_valid_date, label, days)

    for t_idx, ticker in enumerate(all_tickers):
        ind = indicators[ticker]
        prev_valid = False
        for date in ind.index:
            ind_slice = ind.loc[:date]
            valid, label, days = validate_sequential_signals(ind_slice, cfg)
            if valid and not prev_valid:
                seq_first_valid[ticker] = (date, label, days)
                break
            prev_valid = valid
        if (t_idx + 1) % 200 == 0:
            print(f'    Validated {t_idx+1}/{len(all_tickers)}…', end='\r', flush=True)
    print(f'    Done. Sequential pattern found in {len(seq_first_valid)} of {len(all_tickers)} stocks.')

    for i, date in enumerate(all_dates):

        # ── 1. Execute exits queued from previous close ────────────────────────
        for ticker in list(positions.keys()):
            pos = positions[ticker]
            if not pos['exit_queued']:
                continue
            ind = indicators.get(ticker)
            if ind is None or date not in ind.index:
                continue
            row     = ind.loc[date]
            exit_px = row['open'] if not pd.isna(row['open']) else row['close']
            _record_trade(trades, pos, ticker, exit_px, date)
            cash += exit_px * pos['shares']
            del positions[ticker]

        # ── 2. Execute entries queued from previous close ──────────────────────
        for ticker, q_info in list(entry_queue.items()):
            if len(positions) >= max_pos:
                waitlist.append((q_info['score'], ticker, q_info))
                del entry_queue[ticker]
                continue
            ind = indicators.get(ticker)
            if ind is None or date not in ind.index:
                del entry_queue[ticker]
                continue
            row      = ind.loc[date]
            entry_px = row['open'] if not pd.isna(row['open']) else row['close']
            if entry_px <= 0:
                del entry_queue[ticker]
                continue
            alloc  = min(max_pos_value, cash)
            if alloc < entry_px:
                del entry_queue[ticker]
                continue
            # B4 FIX: integer shares per spec — int((capital × 0.10) // entry_price)
            shares = int(alloc // entry_px)
            if shares == 0:
                del entry_queue[ticker]
                continue
            cash  -= shares * entry_px
            positions[ticker] = {
                'entry_date':     date,
                'entry_price':    entry_px,
                'shares':         shares,
                'exit_queued':    False,
                'exit_reason':    None,
                'entry_type':     q_info['entry_type'],
                'recovery_label': q_info['recovery_label'],
                'recovery_days':  q_info['recovery_days'],
                'score':          q_info['score'],
            }
            del entry_queue[ticker]

        # ── 2b. Fill empty slots from waitlist ─────────────────────────────────
        while waitlist and len(positions) < max_pos and len(entry_queue) == 0:
            waitlist.sort(key=lambda x: -x[0])
            _, wl_ticker, wl_info = waitlist.pop(0)
            if wl_ticker not in positions:
                entry_queue[wl_ticker] = wl_info

        # ── 3. Mark portfolio to market ────────────────────────────────────────
        holdings_value = sum(
            pos['shares'] * indicators[t].loc[date]['close']
            for t, pos in positions.items()
            if t in indicators and date in indicators[t].index
        )
        equity_curve.append({
            'Date':      date,
            'Equity':    round(cash + holdings_value, 2),
            'Cash':      round(cash, 2),
            'Positions': len(positions),
        })

        # ── 4. Check exit signals at today's close ─────────────────────────────
        immediate_exits = []
        for ticker, pos in positions.items():
            if pos['exit_queued']:
                continue
            ind = indicators.get(ticker)
            if ind is None or date not in ind.index:
                continue
            row = ind.loc[date]
            # Hard stop — exits at current close (immediate, no queue)
            if row['close'] < pos['entry_price'] * (1 - cfg['stop_loss_pct']):
                immediate_exits.append(
                    (ticker, row['close'], f"{int(cfg['stop_loss_pct']*100)}% Hard Stop")
                )
            # B3 FIX: compare today's close against TODAY's EMA220 (row['ema220']),
            # not yesterday's (row['ema220_s']). ema220_s was one day stale.
            elif row['close'] < row['ema220']:
                pos['exit_queued'] = True
                pos['exit_reason'] = '220 EMA Break'

        for ticker, exit_px, reason in immediate_exits:
            pos = positions.pop(ticker, None)
            if pos:
                _record_trade(trades, pos, ticker, exit_px, date, override_reason=reason)
                cash += exit_px * pos['shares']

        # ── 5. Check regime filter ─────────────────────────────────────────────
        if cfg.get('use_regime_filter', True) and regime_series is not None:
            # Get regime for today (use last known if today not in series)
            if date in regime_series.index:
                is_bull = bool(regime_series.loc[date])
            else:
                prior = regime_series[regime_series.index <= date]
                is_bull = bool(prior.iloc[-1]) if len(prior) > 0 else True
            if not is_bull:
                continue  # BEAR MARKET: no new entries

        # ── 6. Check entry signals at today's close ────────────────────────────
        if i >= len(all_dates) - 1:
            continue
        open_slots = max_pos - len(positions) - len(entry_queue)
        if open_slots <= 0:
            continue

        # Collect 6M momentum values for ranking
        all_mom = []
        pre_candidates = []
        for ticker in all_tickers:
            if ticker in positions or ticker in entry_queue:
                continue
            ind = indicators.get(ticker)
            if ind is None or date not in ind.index:
                continue
            row = ind.loc[date]

            # F1-F6 filters
            passed, _ = check_filters(row, cfg)
            if not passed:
                continue

            # B6 FIX: sequential check — only valid on/after first-valid-date
            seq_entry = seq_first_valid.get(ticker)
            if seq_entry is None or date < seq_entry[0]:
                continue
            _, rec_label, rec_days = seq_entry

            # Volume + breakout
            if not check_volume_and_breakout(row, cfg):
                continue

            mom = row.get('momentum_6m_s') or 0
            all_mom.append(mom)
            pre_candidates.append((ticker, row, rec_label, rec_days))

        # Score and select top candidates
        candidates = []
        for ticker, row, rec_label, rec_days in pre_candidates:
            score = score_signal_v2(row, rec_label, all_mom)
            entry_type = str(row.get('entry_type', 'ATH'))
            candidates.append((score, ticker, rec_label, rec_days, entry_type))

        candidates.sort(key=lambda x: -x[0])

        for score, ticker, rec_label, rec_days, entry_type in candidates[:open_slots]:
            entry_queue[ticker] = {
                'signal_date':    date,
                'score':          score,
                'entry_type':     entry_type,
                'recovery_label': rec_label,
                'recovery_days':  rec_days,
            }

    return trades, equity_curve


def _record_trade(trades: list, pos: dict, ticker: str,
                  exit_px: float, date, override_reason: str = None):
    """Append a closed trade to the trades list."""
    pnl_pct   = (exit_px / pos['entry_price'] - 1) * 100
    hold_days = (date - pos['entry_date']).days
    trades.append({
        'Ticker':         ticker,
        'Entry_Date':     pos['entry_date'].date(),
        'Entry_Price':    round(pos['entry_price'], 2),
        'Exit_Date':      date.date(),
        'Exit_Price':     round(exit_px, 2),
        'Exit_Reason':    override_reason or pos.get('exit_reason', '—'),
        'Shares':         round(pos['shares'], 4),
        'PnL_Pct':        round(pnl_pct, 2),
        'Holding_Days':   hold_days,
        'Result':         'Win' if pnl_pct > 0 else 'Loss',
        'Entry_Type':     pos.get('entry_type', 'ATH'),
        'Recovery_Speed': pos.get('recovery_label', '—'),
        'Recovery_Days':  pos.get('recovery_days', -1),
        'Score':          round(pos.get('score', 0), 2),
    })


# ═══════════════════════════════════════════════════════════════════════════════
#  METRICS
# ═══════════════════════════════════════════════════════════════════════════════

def calculate_metrics(equity_curve: list, trades: list, cfg: dict,
                      benchmark: pd.Series | None) -> dict:
    """Compute CAGR, Sharpe, max drawdown, win rate, and benchmark comparison."""
    eq_df  = pd.DataFrame(equity_curve).set_index('Date')
    equity = eq_df['Equity']
    cap    = cfg['initial_capital']

    total_return = (equity.iloc[-1] / cap - 1) * 100
    n_days       = (equity.index[-1] - equity.index[0]).days
    n_years      = n_days / 365.25
    cagr         = ((equity.iloc[-1] / cap) ** (1 / n_years) - 1) * 100 if n_years > 0 else 0

    daily_ret = equity.pct_change().dropna()
    vol       = daily_ret.std() * (252 ** 0.5) * 100
    sharpe    = (daily_ret.mean() / daily_ret.std() * (252 ** 0.5)) if daily_ret.std() > 0 else 0

    roll_max  = equity.cummax()
    drawdown  = (equity - roll_max) / roll_max * 100
    max_dd    = drawdown.min()

    wins      = [t for t in trades if t['Result'] == 'Win']
    win_rate  = len(wins) / len(trades) * 100 if trades else 0
    avg_gain  = np.mean([t['PnL_Pct'] for t in wins]) if wins else 0
    losses    = [t for t in trades if t['Result'] == 'Loss']
    avg_loss  = np.mean([t['PnL_Pct'] for t in losses]) if losses else 0
    avg_hold  = np.mean([t['Holding_Days'] for t in trades]) if trades else 0

    bench_return = bench_cagr = None
    if benchmark is not None and len(benchmark) > 1:
        b = benchmark.reindex(equity.index).ffill().dropna()
        if len(b) > 1:
            bench_return = (b.iloc[-1] / b.iloc[0] - 1) * 100
            b_years      = (b.index[-1] - b.index[0]).days / 365.25
            bench_cagr   = ((b.iloc[-1] / b.iloc[0]) ** (1 / b_years) - 1) * 100 if b_years > 0 else 0

    return {
        'total_return':  round(total_return, 2),
        'cagr':          round(cagr, 2),
        'volatility':    round(vol, 2),
        'sharpe':        round(sharpe, 2),
        'max_drawdown':  round(max_dd, 2),
        'win_rate':      round(win_rate, 1),
        'num_trades':    len(trades),
        'avg_gain':      round(avg_gain, 2),
        'avg_loss':      round(avg_loss, 2),
        'avg_hold_days': round(avg_hold, 1),
        'bench_return':  round(bench_return, 2) if bench_return is not None else None,
        'bench_cagr':    round(bench_cagr, 2) if bench_cagr is not None else None,
        'start_date':    str(equity.index[0].date()),
        'end_date':      str(equity.index[-1].date()),
        'final_equity':  round(float(equity.iloc[-1]), 2),
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  OUTPUTS
# ═══════════════════════════════════════════════════════════════════════════════

def save_outputs(trades: list, equity_curve: list, metrics: dict,
                 benchmark: pd.Series | None, cfg: dict):
    """Save trades CSV, equity CSV, and performance chart PNG."""
    trades_df = pd.DataFrame(trades)
    if not trades_df.empty:
        trades_df.to_csv(cfg['trades_out'], index=False)
        print(f'  Trades saved  → {cfg["trades_out"]}  ({len(trades_df)} trades)')

    eq_df = pd.DataFrame(equity_curve)
    eq_df.to_csv(cfg['equity_out'], index=False)
    print(f'  Equity saved  → {cfg["equity_out"]}')

    eq_series = eq_df.set_index('Date')['Equity']
    initial   = cfg['initial_capital']

    fig, axes = plt.subplots(2, 1, figsize=(14, 9),
                              gridspec_kw={'height_ratios': [3, 1]},
                              facecolor='#0e1117')
    ax1, ax2 = axes

    ax1.set_facecolor('#0e1117')
    ax1.plot(eq_series.index, eq_series.values / initial * 100 - 100,
             color='#00c8ff', linewidth=1.8, label='Momentum Edge')
    ax1.axhline(0, color='#444', linewidth=0.8, linestyle='--')

    if benchmark is not None:
        b = benchmark.reindex(eq_series.index).ffill().dropna()
        if len(b) > 0:
            b_norm = b / b.iloc[0] * 100 - 100
            ax1.plot(b_norm.index, b_norm.values, color='#ff9800',
                     linewidth=1.2, alpha=0.8, label='Nifty 50')

    ax1.fill_between(eq_series.index, eq_series.values / initial * 100 - 100,
                     0, alpha=0.08, color='#00c8ff')
    ax1.set_title('Momentum Edge — Portfolio Performance (NSE + BSE Universe)',
                  color='#e0e0e0', fontsize=14, pad=12, fontweight='bold')
    ax1.set_ylabel('Return (%)', color='#aaa')
    ax1.tick_params(colors='#888')
    ax1.spines[:].set_color('#333')
    ax1.legend(facecolor='#1a1a2e', labelcolor='#ddd', framealpha=0.8)
    ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f'{y:+.0f}%'))

    roll_max = eq_series.cummax()
    dd       = (eq_series - roll_max) / roll_max * 100

    ax2.set_facecolor('#0e1117')
    ax2.fill_between(dd.index, dd.values, 0, color='#ff3d3d', alpha=0.55)
    ax2.plot(dd.index, dd.values, color='#ff3d3d', linewidth=0.8)
    ax2.set_ylabel('Drawdown (%)', color='#aaa')
    ax2.tick_params(colors='#888')
    ax2.spines[:].set_color('#333')
    ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f'{y:.0f}%'))

    for ax in axes:
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=30, color='#888')
        ax.grid(True, color='#222', linewidth=0.5)

    plt.tight_layout(pad=1.5)
    plt.savefig(cfg['chart_out'], dpi=130, bbox_inches='tight', facecolor='#0e1117')
    plt.close()
    print(f'  Chart saved   → {cfg["chart_out"]}')


# ═══════════════════════════════════════════════════════════════════════════════
#  DIAGNOSTIC REPORT
# ═══════════════════════════════════════════════════════════════════════════════

def print_diagnostic_report(indicators: dict[str, pd.DataFrame],
                             regime_series: pd.Series | None,
                             cfg: dict, W: int = 50):
    """Print filter funnel counts and portfolio status."""
    if not cfg.get('diagnostic_mode', False):
        return

    border = '═' * W
    mid    = '─' * W

    total_syms      = len(indicators)
    universe_mode   = cfg.get('backtest_universe', 'NIFTY500')

    # Regime check on latest available date
    if regime_series is not None and len(regime_series) > 0:
        regime = 'BULL 🟢' if bool(regime_series.iloc[-1]) else 'BEAR 🔴'
    elif not cfg.get('use_regime_filter', True):
        regime = 'DISABLED'
    else:
        regime = 'NO DATA'

    # B9 FIX: dead code removed — per-filter cumulative counting replaced with clean cascade.
    # Count stocks passing each filter on their LAST available row.
    f_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0}
    seq_valid_count = 0
    signal_count    = 0

    for ticker, ind in indicators.items():
        if ind is None or ind.empty:
            continue
        row = ind.iloc[-1]
        s = row
        required_s = ('sma50_s', 'sma150_s', 'ema220_s', 'low52w_s', 'vol_avg20_s')
        if any(pd.isna(s.get(c)) for c in required_s):
            continue
        f1 = s['sma150_s'] > s['ema220_s']
        f2 = f1 and s['close_s'] > s['sma50_s']
        f3 = f2 and s['sma50_s'] > s['sma150_s']
        f4 = f3 and s['close_s'] >= cfg['min_price_vs_low'] * s['low52w_s']
        f5 = f4 and bool(s.get('had_ema_dip_s', False))
        chop  = s.get('choppiness_s')
        f6_ok = chop is None or pd.isna(chop) or chop <= cfg['choppiness_threshold']
        f6 = f5 and f6_ok
        for fi, passed in enumerate([f1, f2, f3, f4, f5, f6], start=1):
            if passed:
                f_counts[fi] += 1

    latest_date = max(ind.index[-1] for ind in indicators.values() if not ind.empty)
    for ticker, entry in seq_first_valid.items() if 'seq_first_valid' in dir() else []:
        if entry[0] <= latest_date:
            seq_valid_count += 1
            ind = indicators.get(ticker)
            if ind is not None and not ind.empty:
                if check_volume_and_breakout(ind.iloc[-1], cfg):
                    signal_count += 1

    print('\n╔' + border + '╗')
    print(f'║{"  MOMENTUM EDGE DIAGNOSTIC REPORT":^{W}}║')
    print('╠' + border + '╣')
    print(f'║  Universe: {universe_mode:<{W-12}}║')
    print(f'║  Total symbols loaded        : {total_syms:<{W-34}}║')
    print(f'║  Market Regime (SMA50/200)   : {regime:<{W-34}}║')
    print('╠' + border + '╣')
    print(f'║{"  FILTER FUNNEL:":^{W}}║')
    labels = [
        (1, 'F1 SMA150 > EMA220 (trend align)'),
        (2, 'F2 Close > SMA50 (short-term str)'),
        (3, 'F3 SMA50 > SMA150 (MA alignment)'),
        (4, 'F4 Price > 1.25x 52W low         '),
        (5, 'F5 Dipped below EMA220 (90 days) '),
        (6, 'F6 Choppiness < 61.8 (clean chart)'),
    ]
    for fn, label in labels:
        print(f'║  Passed {label}: {f_counts[fn]:<{W-43}}║')
    print('╠' + border + '╣')
    print(f'║{"  SIGNAL FUNNEL:":^{W}}║')
    print(f'║  Passed sequential check     : {seq_valid_count:<{W-34}}║')
    print(f'║  Total signals (w/ vol+bk)   : {signal_count:<{W-34}}║')
    print('╚' + border + '╝')
    print()


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    W = 60
    sep = '─' * W

    print('\n' + '═' * W)
    print('  MOMENTUM EDGE BACKTEST — NSE + BSE Universe')
    print('═' * W)
    print(f'  Universe mode : {CFG["backtest_universe"]}')
    print(f'  Capital       : ₹{CFG["initial_capital"]:,.0f}')
    print(f'  Position size : ₹{CFG["max_position_value"]:,.0f} per stock  '
          f'(max {CFG["max_positions"]} concurrent)')
    print(f'  Regime filter : {"ON" if CFG["use_regime_filter"] else "OFF"}')
    print(sep)

    # ── Load data ──────────────────────────────────────────────────────────────
    print('\n[1/5] Loading OHLCV data…')
    ohlcv = load_ohlcv(CFG)
    if not ohlcv:
        print('ERROR: No data loaded. Run nse_bse_downloader.py first.')
        return

    print('\n[2/5] Loading benchmark (Nifty 50)…')
    benchmark = load_benchmark(CFG)
    if benchmark is not None:
        print(f'  Benchmark loaded: {len(benchmark)} rows')
    else:
        print('  WARNING: Benchmark not found. Regime filter disabled.')

    regime_series = build_regime_series(benchmark, CFG)

    # Current regime status
    if regime_series is not None and len(regime_series) > 0:
        is_bull = bool(regime_series.iloc[-1])
        regime_str = '🟢 BULL' if is_bull else '🔴 BEAR'
        print(f'  Current regime: {regime_str} (SMA50 > SMA200, close > SMA200, < 10% off 52W high)')
        if not is_bull:
            print('  ⚠️ BEAR MARKET REGIME — No new signals will be generated')

    # ── Compute indicators ─────────────────────────────────────────────────────
    print(f'\n[3/5] Computing indicators for {len(ohlcv)} stocks…')
    indicators  = {}
    skipped_min = 0
    for t_idx, (ticker, df) in enumerate(ohlcv.items()):
        ind = compute_indicators(df, CFG)
        if ind is None:
            skipped_min += 1
        else:
            indicators[ticker] = ind
        if (t_idx + 1) % 500 == 0:
            print(f'  Processed {t_idx+1}/{len(ohlcv)}…', end='\r', flush=True)

    print(f'  Computed: {len(indicators)} stocks  |  Skipped (insufficient data): {skipped_min}')

    # ── Diagnostic report ──────────────────────────────────────────────────────
    print_diagnostic_report(indicators, regime_series, CFG)

    # ── Run backtest ───────────────────────────────────────────────────────────
    print(f'[4/5] Running backtest over {len(indicators)} stocks…')
    trades, equity_curve = run_backtest(indicators, regime_series, CFG)
    print(f'  Trades generated: {len(trades)}')

    if not trades:
        print('\nWARNING: No trades were generated.')
        print('Possible causes:')
        print('  • All stocks failing sequential signal validation')
        print('  • Bear market regime blocking entries for the full period')
        print('  • Data quality issues — check failed_symbols.csv')
        print('  • Run with diagnostic_mode=True to see filter funnel')
        return

    # ── Calculate metrics ──────────────────────────────────────────────────────
    metrics = calculate_metrics(equity_curve, trades, CFG, benchmark)

    # ── Print results ──────────────────────────────────────────────────────────
    print('\n' + sep)
    print('  BACKTEST RESULTS')
    print(sep)
    print(f'  Period        : {metrics["start_date"]} → {metrics["end_date"]}')
    print(f'  Final equity  : ₹{metrics["final_equity"]:,.0f}')
    print(f'  Total return  : {metrics["total_return"]:+.2f}%')
    print(f'  CAGR          : {metrics["cagr"]:+.2f}%', end='')
    if metrics['bench_cagr'] is not None:
        print(f'  vs Nifty: {metrics["bench_cagr"]:+.2f}%')
    else:
        print()
    print(f'  Max drawdown  : {metrics["max_drawdown"]:.2f}%')
    print(f'  Sharpe ratio  : {metrics["sharpe"]:.2f}')
    print(f'  Win rate      : {metrics["win_rate"]:.1f}%  ({metrics["num_trades"]} trades)')
    print(f'  Avg gain      : {metrics["avg_gain"]:+.2f}%  |  Avg loss: {metrics["avg_loss"]:+.2f}%')
    print(f'  Avg hold      : {metrics["avg_hold_days"]:.0f} days')
    print(sep)

    # ── Save outputs ───────────────────────────────────────────────────────────
    print('\n[5/5] Saving outputs…')
    save_outputs(trades, equity_curve, metrics, benchmark, CFG)
    print('\nDone. Run: streamlit run momentum_edge_dashboard.py')


if __name__ == '__main__':
    main()
