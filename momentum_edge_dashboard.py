"""
Momentum Edge Strategy — Live Screener Dashboard
Scans full NSE + BSE universe. Shows market regime, filter funnel, and live signals.
Click any row in the signal table to see a full price chart + criteria breakdown.

Run: streamlit run momentum_edge_dashboard.py --server.port 8503
"""

import calendar
import os
import warnings
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from core.refresh_ui import render_staleness_banner

warnings.filterwarnings('ignore')

# ═══════════════════════════════════════════════════════════════════════════════
#  CONFIG
# ═══════════════════════════════════════════════════════════════════════════════

DATA_FOLDER_FULL   = './data/nse_bse'
DATA_FOLDER_LEGACY = 'momentum_edge_data'
UNIVERSE_FILE      = './data/universe/combined_universe.csv'
TRADES_FILE        = 'momentum_edge_trades.csv'
EQUITY_FILE        = 'momentum_edge_equity.csv'
BENCHMARK_FILE     = './data/nse_bse/^NSEI.csv'
BENCHMARK_LEGACY   = './data/^NSEI.csv'        # fallback: Monthly Rotation benchmark

# Indicator periods (must match backtest CFG)
SMA50_P          = 50
SMA150_P         = 150
EMA220_P         = 220
HIGH52_P         = 252
LOW52_P          = 252
VOLAVG_P         = 20
DIP_LB           = 90
CHOP_P           = 14
CHOP_THRESH      = 61.8
MOM_P            = 126
MIN_PRICE_VS_LOW = 1.25
VOL_THRESH       = 1.5
VOL_LOOKBACK     = 50    # VOLUME_LOOKBACK_DAYS
VOL_MULTIPLIER   = 1.5   # VOLUME_MULTIPLIER — used with 50-day avg
NEAR_BK_PCT      = 0.03
MIN_BARS         = 252    # spec: 252 trading days minimum
MIN_CLOSE_PRICE  = 50.0   # spec: configurable — skip penny stocks below ₹50
MIN_AVG_VOL      = 100_000   # match backtest: skip stocks with avg daily vol < 100K
RECENT_DAYS      = 7     # scan back this many trading days for recent breakouts

# ═══════════════════════════════════════════════════════════════════════════════
#  PAGE CONFIG + CSS
# ═══════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title='Momentum Edge Screener',
    page_icon='📈',
    layout='wide',
    initial_sidebar_state='expanded',
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

/* ── Base ───────────────────────────────────────────────────────────────── */
html, body, [data-testid="stApp"] {
    background-color: #060B14 !important;
    color: #D4DBE8 !important;
    font-family: 'Inter', 'Segoe UI', sans-serif;
    font-size: 14px;
}
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #080E1C 0%, #060B14 100%) !important;
    border-right: 1px solid rgba(255,255,255,0.06) !important;
}
[data-testid="stSidebar"] * { color: #8A9DC0 !important; }
[data-testid="stSidebar"] .stCheckbox label { color: #A0B0CC !important; font-size: 12px !important; }
[data-testid="stSidebar"] .stSlider label, [data-testid="stSidebar"] .stSelectbox label {
    color: #7C90B0 !important; font-size: 11px !important;
}

/* ── Regime banners ─────────────────────────────────────────────────────── */
.regime-bull {
    background: linear-gradient(135deg, rgba(0,212,128,0.12) 0%, rgba(0,212,128,0.04) 100%);
    border: 1px solid rgba(0,212,128,0.35);
    border-left: 4px solid #00D480;
    border-radius: 12px;
    padding: 16px 20px;
    margin-bottom: 20px;
    position: relative;
    overflow: hidden;
}
.regime-bull::before {
    content: '';
    position: absolute; top: 0; left: 0; right: 0; height: 1px;
    background: linear-gradient(90deg, #00D480, transparent);
}
.regime-bull-title { font-size: 15px; font-weight: 700; color: #00D480; letter-spacing: -0.01em; }
.regime-bear {
    background: linear-gradient(135deg, rgba(255,61,90,0.12) 0%, rgba(255,61,90,0.04) 100%);
    border: 1px solid rgba(255,61,90,0.35);
    border-left: 4px solid #FF3D5A;
    border-radius: 12px;
    padding: 16px 20px;
    margin-bottom: 20px;
    position: relative;
    overflow: hidden;
}
.regime-bear::before {
    content: '';
    position: absolute; top: 0; left: 0; right: 0; height: 1px;
    background: linear-gradient(90deg, #FF3D5A, transparent);
}
.regime-bear-title { font-size: 15px; font-weight: 700; color: #FF3D5A; letter-spacing: -0.01em; }
.regime-sub {
    font-size: 12px; font-weight: 400; color: #64748B;
    margin-top: 5px; line-height: 1.5;
}
.regime-pills { display: flex; gap: 8px; margin-top: 10px; flex-wrap: wrap; }
.regime-pill {
    font-size: 10px; font-weight: 600; padding: 3px 10px;
    border-radius: 999px; letter-spacing: 0.03em;
}
.pill-ok   { background: rgba(0,212,128,0.15); color: #00D480; border: 1px solid rgba(0,212,128,0.3); }
.pill-fail { background: rgba(255,61,90,0.15);  color: #FF3D5A; border: 1px solid rgba(255,61,90,0.3); }

/* ── Metric / stat cards ────────────────────────────────────────────────── */
.me-card {
    background: linear-gradient(145deg, #0D1626 0%, #0A1220 100%);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 14px;
    padding: 18px 16px 14px 16px;
    text-align: center;
    position: relative;
    overflow: hidden;
    transition: border-color 0.2s;
}
.me-card::before {
    content: '';
    position: absolute; top: 0; left: 20%; right: 20%; height: 1px;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.12), transparent);
}
.me-card .label {
    font-size: 10px; font-weight: 600; color: #4A5A7A;
    text-transform: uppercase; letter-spacing: 0.08em;
    margin-bottom: 8px;
}
.me-card .value {
    font-size: 28px; font-weight: 800; line-height: 1.0;
    font-family: 'JetBrains Mono', monospace;
    letter-spacing: -0.02em;
}
.me-card .sub { font-size: 11px; color: #3A4A66; margin-top: 6px; line-height: 1.4; }
.me-card-accent {
    position: absolute; bottom: 0; left: 0; right: 0; height: 2px;
    border-radius: 0 0 14px 14px;
}

/* ── Section header ─────────────────────────────────────────────────────── */
.sec-hdr {
    font-size: 11px; font-weight: 700; color: #4F7BFF;
    text-transform: uppercase; letter-spacing: 0.1em;
    display: flex; align-items: center; gap: 8px;
    padding-bottom: 8px; margin: 22px 0 12px 0;
    border-bottom: 1px solid rgba(79,123,255,0.15);
}
.sec-hdr::before {
    content: '';
    display: inline-block; width: 3px; height: 14px;
    background: #4F7BFF; border-radius: 2px; flex-shrink: 0;
}

/* ── Funnel bars ─────────────────────────────────────────────────────────── */
.funnel-bar {
    background: rgba(13,22,38,0.8);
    border: 1px solid rgba(255,255,255,0.05);
    border-radius: 8px;
    padding: 8px 12px;
    margin-bottom: 5px;
    position: relative;
    overflow: hidden;
}
.funnel-fill {
    position: absolute; top: 0; left: 0; bottom: 0;
    border-radius: 8px;
    opacity: 0.12;
}
.funnel-label { font-size: 11px; color: #7A8BA8; position: relative; }
.funnel-count { font-size: 12px; font-weight: 700; color: #C8D4E8; font-family: 'JetBrains Mono', monospace; position: relative; }
.funnel-pct   { font-size: 10px; color: #3A4A66; font-family: 'JetBrains Mono', monospace; position: relative; }

/* ── Signal badges ─────────────────────────────────────────────────────── */
.badge-buy {
    background: rgba(0,212,128,0.12); color: #00D480;
    border: 1px solid rgba(0,212,128,0.3);
    border-radius: 999px; padding: 2px 10px;
    font-size: 10px; font-weight: 700; letter-spacing: 0.04em;
    white-space: nowrap;
}
.badge-watch {
    background: rgba(245,183,49,0.12); color: #F5B731;
    border: 1px solid rgba(245,183,49,0.3);
    border-radius: 999px; padding: 2px 10px;
    font-size: 10px; font-weight: 700; letter-spacing: 0.04em;
    white-space: nowrap;
}
.badge-forming {
    background: rgba(79,123,255,0.12); color: #7C9CFF;
    border: 1px solid rgba(79,123,255,0.25);
    border-radius: 999px; padding: 2px 10px;
    font-size: 10px; font-weight: 700; letter-spacing: 0.04em;
    white-space: nowrap;
}
.badge-bear {
    background: rgba(255,61,90,0.12); color: #FF5C7A;
    border: 1px solid rgba(255,61,90,0.25);
    border-radius: 999px; padding: 2px 10px;
    font-size: 10px; font-weight: 700; letter-spacing: 0.04em;
    white-space: nowrap;
}

/* ── Explain / info box ─────────────────────────────────────────────────── */
.explain-box {
    background: rgba(79,123,255,0.05);
    border: 1px solid rgba(79,123,255,0.15);
    border-radius: 10px;
    padding: 12px 16px;
    font-size: 12px; color: #6A7A9A; line-height: 1.8;
    margin-bottom: 16px;
}
.explain-box b { color: #9AB0D0; font-weight: 600; }

/* ── Detail panel header ────────────────────────────────────────────────── */
.detail-header {
    background: linear-gradient(135deg, rgba(79,123,255,0.1) 0%, rgba(79,123,255,0.03) 100%);
    border: 1px solid rgba(79,123,255,0.25);
    border-left: 4px solid #4F7BFF;
    border-radius: 12px;
    padding: 16px 20px;
    margin-bottom: 18px;
    position: relative;
    overflow: hidden;
}
.detail-header::before {
    content: '';
    position: absolute; top: 0; left: 0; right: 0; height: 1px;
    background: linear-gradient(90deg, rgba(79,123,255,0.6), transparent);
}

/* ── Criteria cards ─────────────────────────────────────────────────────── */
.crit-ok {
    background: linear-gradient(135deg, rgba(0,212,128,0.07) 0%, rgba(0,212,128,0.02) 100%);
    border: 1px solid rgba(0,212,128,0.2);
    border-left: 3px solid #00D480;
    border-radius: 10px;
    padding: 12px 14px;
    margin-bottom: 8px;
    min-height: 76px;
}
.crit-fail {
    background: linear-gradient(135deg, rgba(255,61,90,0.07) 0%, rgba(255,61,90,0.02) 100%);
    border: 1px solid rgba(255,61,90,0.18);
    border-left: 3px solid #FF3D5A;
    border-radius: 10px;
    padding: 12px 14px;
    margin-bottom: 8px;
    min-height: 76px;
}
.crit-icon  { font-size: 14px; margin-bottom: 4px; }
.crit-label { font-size: 11px; font-weight: 600; color: #C8D4E8; line-height: 1.4; }
.crit-detail {
    font-size: 10px; color: #4A5A7A; margin-top: 5px;
    font-family: 'JetBrains Mono', monospace; line-height: 1.6;
}

/* ── Page header ────────────────────────────────────────────────────────── */
.page-title {
    font-size: 26px; font-weight: 800; color: #E8EDF5;
    letter-spacing: -0.03em; line-height: 1.1;
}
.page-sub {
    font-size: 13px; color: #3A4A6A; margin-top: 4px; line-height: 1.5;
}
.page-sub b { color: #4F7BFF; font-weight: 600; }

/* ── Streamlit native element tweaks ────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    background: rgba(13,22,38,0.6) !important;
    border-radius: 10px !important;
    padding: 4px !important;
    border: 1px solid rgba(255,255,255,0.06) !important;
    gap: 2px !important;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 7px !important;
    font-size: 12px !important; font-weight: 600 !important;
    color: #4A5A7A !important; padding: 6px 14px !important;
    transition: all 0.15s !important;
}
.stTabs [aria-selected="true"] {
    background: rgba(79,123,255,0.2) !important;
    color: #7C9CFF !important;
}
.stDataFrame { border-radius: 10px !important; overflow: hidden !important; }
.stButton > button {
    background: linear-gradient(135deg, #1A2A4A, #0F1E38) !important;
    border: 1px solid rgba(79,123,255,0.3) !important;
    color: #7C9CFF !important;
    border-radius: 8px !important;
    font-weight: 600 !important; font-size: 13px !important;
    transition: all 0.15s !important;
}
.stButton > button:hover {
    background: linear-gradient(135deg, #1E3260, #152A50) !important;
    border-color: rgba(79,123,255,0.6) !important;
}
[data-testid="stButton"] [kind="primary"] > button {
    background: linear-gradient(135deg, #2A4AFF, #1A35CC) !important;
    border-color: transparent !important;
    color: #fff !important;
}
hr { border-color: rgba(255,255,255,0.06) !important; }
.stWarning  { background: rgba(245,183,49,0.08)  !important; border: 1px solid rgba(245,183,49,0.25)  !important; border-radius: 10px !important; }
.stInfo     { background: rgba(79,123,255,0.08)  !important; border: 1px solid rgba(79,123,255,0.25)  !important; border-radius: 10px !important; }
.stSuccess  { background: rgba(0,212,128,0.08)   !important; border: 1px solid rgba(0,212,128,0.25)   !important; border-radius: 10px !important; }
.stError    { background: rgba(255,61,90,0.08)   !important; border: 1px solid rgba(255,61,90,0.25)   !important; border-radius: 10px !important; }
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  DATA HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _load_csv(path: Path) -> pd.DataFrame | None:
    try:
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        # B7 FIX: plain date strings have no timezone; utc=True raises on tz-naive
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


@st.cache_data(ttl=3600, show_spinner=False)
def load_universe_data() -> dict[str, pd.DataFrame]:
    """Load all stock CSVs in parallel. Legacy folder takes priority."""
    symbol_whitelist = None
    ufile = Path(UNIVERSE_FILE)
    if ufile.exists():
        try:
            u = pd.read_csv(ufile)
            if 'Symbol' in u.columns:
                symbol_whitelist = set(u['Symbol'].str.strip().tolist())
        except Exception:
            pass

    skip_stems = {'^NSEI', 'NIFTYBEES.NS', 'me_summary', 'download_status', 'failed_symbols'}

    def _try_load(csv_file: Path) -> tuple[str, object]:
        stem = csv_file.stem
        if stem in skip_stems:
            return stem, None
        if symbol_whitelist and stem not in symbol_whitelist:
            return stem, None
        df = _load_csv(csv_file)
        if df is not None and len(df) >= MIN_BARS:
            return stem, df
        return stem, None

    # Collect all candidate files (legacy priority)
    seen: set[str] = set()
    file_pairs: list[tuple[Path, int]] = []   # (path, priority)  0=legacy, 1=full
    for folder, pri in [(Path(DATA_FOLDER_LEGACY), 0), (Path(DATA_FOLDER_FULL), 1)]:
        if not folder.exists():
            continue
        for f in sorted(folder.glob('*.csv')):
            if f.stem not in seen:
                file_pairs.append((f, pri))
                seen.add(f.stem)

    ohlcv: dict[str, pd.DataFrame] = {}
    workers = min(32, (os.cpu_count() or 4) * 2)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for stem, df in pool.map(lambda p: _try_load(p[0]), file_pairs):
            if df is not None:
                ohlcv[stem] = df
    return ohlcv


@st.cache_data(ttl=3600, show_spinner=False)
def load_benchmark_data() -> pd.Series | None:
    candidates = [
        BENCHMARK_FILE,
        BENCHMARK_LEGACY,
        'momentum_edge_data/NIFTYBEES.NS.csv',
    ]
    for p in candidates:
        path = Path(p)
        if path.exists():
            df = _load_csv(path)
            if df is not None:
                return df['Close'].dropna()
    return None


def load_backtest_data() -> tuple[pd.DataFrame | None, pd.DataFrame | None]:
    trades_df = equity_df = None
    try:
        if Path(TRADES_FILE).exists():
            t = pd.read_csv(TRADES_FILE)
            if not t.empty:
                trades_df = t
    except Exception:
        pass
    try:
        if Path(EQUITY_FILE).exists():
            e = pd.read_csv(EQUITY_FILE)
            if not e.empty:
                equity_df = e
    except Exception:
        pass
    return trades_df, equity_df


# ═══════════════════════════════════════════════════════════════════════════════
#  INDICATOR COMPUTATION
# ═══════════════════════════════════════════════════════════════════════════════

def _compute_choppiness(df: pd.DataFrame) -> float | None:
    period = CHOP_P
    if len(df) < period + 1:
        return None
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
    chop_series = 100 * np.log10(atr_sum / hl_range) / np.log10(period)
    val = chop_series.iloc[-2] if len(chop_series) >= 2 else np.nan
    return None if pd.isna(val) else float(val)


def _compute_recovery(close_s: pd.Series, ema220_s: pd.Series) -> tuple[str, int]:
    c = close_s.values[-DIP_LB:]
    e = ema220_s.values[-DIP_LB:]
    m = len(c)
    if m < 2 or c[-1] < e[-1]:
        return 'No Reclaim', -1
    dip_end = -1
    for j in range(m - 2, -1, -1):
        if c[j] < e[j]:
            dip_end = j
            break
    if dip_end == -1:
        return 'No Reclaim', -1
    dip_start = dip_end
    for j in range(dip_end - 1, -1, -1):
        if c[j] < e[j]:
            dip_start = j
        else:
            break
    dip_low_idx = dip_start + int(np.argmin(c[dip_start: dip_end + 1]))
    for j in range(dip_low_idx + 1, m):
        if c[j] >= e[j]:
            days = j - dip_low_idx
            if days <= 30:
                return 'Fast', days
            elif days <= 60:
                return 'Normal', days
            else:
                return 'Slow', days
    return 'No Reclaim', -1


def _compute_cycle_state(close_arr: np.ndarray,
                         ema220_arr: np.ndarray,
                         resistance_arr: np.ndarray) -> str:
    n = len(close_arr)
    if n < 2:
        return 'NORMAL'
    # Pre-compute event arrays (vectorized, no Python loop overhead)
    valid      = ~(np.isnan(close_arr) | np.isnan(ema220_arr))
    below_ema  = valid & (close_arr < ema220_arr)
    # First-cross: today > resistance AND yesterday <= resistance
    above_res  = np.zeros(n, dtype=bool)
    with np.errstate(invalid='ignore'):
        above_res[1:] = (
            ~np.isnan(resistance_arr[1:]) &
            (close_arr[1:] > resistance_arr[1:]) &
            (close_arr[:-1] <= resistance_arr[1:])
        )
    state = 'NORMAL'
    for i in range(1, n):
        if not valid[i]:
            continue
        if below_ema[i]:
            state = 'FLUSHED'
        elif state == 'FLUSHED' and above_res[i]:
            state = 'POST_BREAKOUT'
    return state


@st.cache_data(ttl=3600, show_spinner=False)
def compute_signals(filters_active: dict, min_score: int,
                    exchange_filter: str) -> tuple[pd.DataFrame, pd.DataFrame, dict, bool, object]:
    ohlcv     = load_universe_data()
    benchmark = load_benchmark_data()

    funnel = {'total': 0, 'sufficient_data': 0,
              'f1': 0, 'f2': 0, 'f3': 0, 'f4': 0, 'f5': 0, 'f6': 0,
              'vol_bk': 0, 'final': 0}
    funnel['total'] = len(ohlcv)

    # Regime: 3-condition gate matching backtest build_regime_series()
    is_bull_today = True
    if benchmark is not None and len(benchmark) >= 200:
        _sma50  = benchmark.rolling(50).mean()
        _sma200 = benchmark.rolling(200).mean()
        _high52 = benchmark.rolling(252).max()
        _b = benchmark.iloc[-1]
        is_bull_today = bool(
            _b > _sma200.iloc[-1]
            and _sma50.iloc[-1] > _sma200.iloc[-1]
            and _b >= 0.90 * _high52.iloc[-1]
        )

    rows        = []
    recent_rows = []

    for ticker, df in ohlcv.items():
        if len(df) < MIN_BARS:
            continue
        if df['Close'].iloc[-1] < MIN_CLOSE_PRICE:
            continue
        if df['Volume'].iloc[-30:].mean() < MIN_AVG_VOL:
            continue
        funnel['sufficient_data'] += 1

        exch = 'NSE' if ticker.endswith('.NS') else 'BSE'
        if exchange_filter == 'NSE Only' and exch != 'NSE':
            continue
        if exchange_filter == 'BSE Only' and exch != 'BSE':
            continue

        close  = df['Close']
        volume = df['Volume']

        sma50  = close.rolling(SMA50_P).mean()
        sma150 = close.rolling(SMA150_P).mean()
        ema220 = close.ewm(span=EMA220_P, adjust=False).mean()
        high52 = close.rolling(HIGH52_P).max()
        low52  = close.rolling(LOW52_P).min()
        vol20      = volume.rolling(VOLAVG_P).mean()
        vol50      = volume.rolling(VOL_LOOKBACK).mean()
        resistance = close.shift(1).rolling(HIGH52_P).max()   # yesterday's 252-day max
        ath        = close.expanding().max()

        # 1-2-3 state machine: determines whether this cycle's breakout already fired
        cycle_state = _compute_cycle_state(
            close.values.astype(float),
            ema220.values.astype(float),
            resistance.values.astype(float),
        )
        dip_flag   = (close < ema220).astype(int)
        had_dip    = dip_flag.rolling(DIP_LB).max().astype(bool)
        mom_6m     = close.pct_change(MOM_P)

        def _s(series):
            return series.iloc[-2] if len(series) >= 2 else np.nan

        # T-1 scalars (only close_s needed for breakout first-cross; F5 window ends T-1)
        close_s   = _s(close)
        vol20_s   = _s(vol20);   vol50_s  = _s(vol50)
        had_dip_s = bool(_s(had_dip))
        ath_prev  = _s(ath);     high52_s = _s(high52)
        mom_s     = _s(mom_6m)
        res_today = float(resistance.iloc[-1]) if not pd.isna(resistance.iloc[-1]) else np.nan

        # Day-T scalars (F1–F4 use current bar per spec)
        close_now  = float(close.iloc[-1])
        ema220_now = float(ema220.iloc[-1])
        sma50_now  = float(sma50.iloc[-1])
        sma150_now = float(sma150.iloc[-1])
        low52_now  = float(low52.iloc[-1])
        vol_today  = float(volume.iloc[-1])

        if any(pd.isna(v) for v in [close_now, ema220_now, sma50_now, sma150_now, low52_now]):
            continue

        # ── Recent breakout scan (POST_BREAKOUT stocks only) ──────────────────
        if cycle_state == 'POST_BREAKOUT':
            close_arr = close.values.astype(float)
            res_arr   = resistance.values.astype(float)
            n_arr     = len(close_arr)
            for k in range(0, min(RECENT_DAYS + 4, n_arr - 1)):
                idx      = n_arr - 1 - k
                idx_prev = idx - 1
                if idx_prev < 0:
                    break
                r  = res_arr[idx]
                c  = close_arr[idx]
                cp = close_arr[idx_prev]
                if np.isnan(r) or np.isnan(c) or np.isnan(cp):
                    continue
                if c > r and cp <= r:
                    if k <= RECENT_DAYS and close_now > ema220_now and close_now > c * 0.92:
                        vol50_s_r = _s(vol50)
                        vol_r = (float(vol_today) / float(vol50_s_r)) if (not pd.isna(vol50_s_r) and vol50_s_r > 0) else 0
                        mom_s_r = _s(mom_6m)
                        ext_pct = (close_now / c - 1) * 100
                        recent_rows.append({
                            'Ticker':        ticker,
                            'Exchange':      exch,
                            'Signal':        'Recent Breakout',
                            'Action':        'REVIEW',
                            'Score':         0.0,
                            'Days Ago':      k,
                            'Entry Type':    'ATH' if (not pd.isna(ath_prev) and c > float(ath_prev)) else '52W High',
                            'Recovery':      'N/A',
                            'Rec Days':      -1,
                            'Chart Qual':    'N/A',
                            'Choppiness':    None,
                            'Close (₹)':     round(close_now, 2),
                            '52W High (₹)':  round(float(res_arr[n_arr - 1]), 2) if not np.isnan(res_arr[n_arr - 1]) else None,
                            'Dist 52W%':     round(ext_pct, 1),
                            'Bk Price (₹)':  round(float(c), 2),
                            '% Extended':    round(ext_pct, 1),
                            '220 EMA (₹)':   round(ema220_now, 2),
                            'Vol Ratio':     round(vol_r, 2),
                            'Stop Loss (₹)': round(close_now * 0.85, 2),
                            'Mom 6M%':       round(float(mom_s_r) * 100 if not pd.isna(mom_s_r) else 0, 1),
                        })
                    break
            continue  # never show POST_BREAKOUT in main screener

        # ── Filters (F1–F4 on day T per spec; F5 window T-1→T-89 per spec) ───────
        if filters_active.get('f1', True):
            if not (sma150_now > ema220_now):
                continue
        funnel['f1'] += 1

        if filters_active.get('f2', True):
            if not (close_now > sma50_now):
                continue
        funnel['f2'] += 1

        if filters_active.get('f3', True):
            if not (sma50_now > sma150_now):
                continue
        funnel['f3'] += 1

        if filters_active.get('f4', True):
            if not (close_now >= MIN_PRICE_VS_LOW * low52_now):
                continue
        funnel['f4'] += 1

        if filters_active.get('f5', True):
            if not had_dip_s:
                continue
        funnel['f5'] += 1

        chop = _compute_choppiness(df)
        if filters_active.get('f6', True):
            if chop is not None and chop > CHOP_THRESH:
                continue
        funnel['f6'] += 1

        rec_label, rec_days = 'N/A', -1

        # ── Volume + breakout ─────────────────────────────────────────────────
        vol_ok = True
        if filters_active.get('vol', True):
            if pd.isna(vol50_s) or vol50_s <= 0 or pd.isna(vol_today):
                vol_ok = False
            else:
                vol_ok = vol_today >= VOL_MULTIPLIER * vol50_s

        # ── Breakout / near-breakout classification ───────────────────────────
        # resistance_today = yesterday's 252-day rolling max  (the level to beat)
        bk_ref = res_today if not pd.isna(res_today) else high52_s
        entry_type = 'ATH' if (not pd.isna(ath_prev) and close_now > float(ath_prev)) else '52W High'

        # BREAKOUT: today's close first-crosses above resistance
        is_breakout = (
            not pd.isna(res_today)
            and close_now > res_today              # above resistance today
            and close_s <= res_today               # was at-or-below yesterday
            and close_now > ema220_now             # still above long-term trend
        )

        # Distance gates for near-breakout
        dist_to_res = (res_today - close_now) / res_today if (not pd.isna(res_today) and res_today > 0) else 1.0
        dist_from_220 = (close_now / ema220_now - 1) if ema220_now > 0 else 0.0

        is_near_bk = (
            not is_breakout
            and not pd.isna(res_today)
            and 0 < dist_to_res <= 0.02            # within 2% below resistance
            and vol_ok                             # spec 7.1: F1-F7 all true incl vol
            and cycle_state != 'POST_BREAKOUT'     # state machine: breakout already fired this cycle
        )

        if is_breakout and vol_ok:
            funnel['vol_bk'] += 1

        if is_breakout and vol_ok:
            signal = 'Breakout Today'
        elif is_near_bk:
            signal = 'Near Breakout'
        elif funnel['f6'] > 0:
            signal = 'Watch Zone'
        else:
            signal = 'Watchlist'

        if filters_active.get('regime', True) and not is_bull_today:
            action = 'BEAR MARKET'
        elif signal == 'Breakout Today':
            action = 'BUY NOW'
        elif signal == 'Near Breakout':
            action = 'WATCH'
        else:
            action = 'FORMING'

        vol_ratio = (float(vol_today) / float(vol50_s)) if (not pd.isna(vol50_s) and vol50_s > 0) else 0
        ath_prox  = min((float(close_now) / float(bk_ref)), 1.0) if (bk_ref and bk_ref > 0) else 0
        mom_pct   = float(mom_s) if not pd.isna(mom_s) else 0
        score = round(ath_prox * 30 + min(vol_ratio * 10, 20) + min(mom_pct * 100, 20), 1)

        dist_ath  = ((close_now / float(bk_ref)) - 1) * 100 if bk_ref and bk_ref > 0 else 0
        stop_loss = close_now * 0.85

        rows.append({
            'Ticker':       ticker,
            'Exchange':     exch,
            'Signal':       signal,
            'Action':       action,
            'Score':        score,
            'Entry Type':   entry_type,
            'Recovery':     rec_label,
            'Rec Days':     rec_days,
            'Chart Qual':   'Clean ✅' if (chop is not None and chop < CHOP_THRESH) else 'Choppy ⚠️',
            'Choppiness':   round(chop, 1) if chop is not None else None,
            'Close (₹)':    round(close_now, 2),
            '52W High (₹)': round(float(bk_ref), 2) if bk_ref else None,
            'Dist 52W%':    round(dist_ath, 1),
            'Bk Price (₹)': None,
            '% Extended':   None,
            '220 EMA (₹)':  round(ema220_now, 2),
            'Vol Ratio':    round(vol_ratio, 2),
            'Stop Loss (₹)':round(stop_loss, 2),
            'Mom 6M%':      round(mom_pct * 100, 1),
            'Days Ago':     0,
        })

    df_out = pd.DataFrame(rows)
    if not df_out.empty:
        sig_rank = {'Breakout Today': 0, 'Near Breakout': 1, 'Watch Zone': 2, 'Watchlist': 3}
        df_out['_rank'] = df_out['Signal'].map(sig_rank).fillna(4)
        df_out = df_out.sort_values(['_rank', 'Score'], ascending=[True, False])
        df_out = df_out.drop(columns=['_rank'])
        df_out = df_out[df_out['Score'] >= min_score]
        funnel['final'] = len(df_out)

    df_recent = pd.DataFrame(recent_rows)
    if not df_recent.empty:
        df_recent = df_recent.sort_values('Days Ago')

    # Find the latest date across all loaded CSVs so we can warn if data is stale
    latest_date = None
    for df_d in ohlcv.values():
        d = df_d.index[-1]
        if latest_date is None or d > latest_date:
            latest_date = d

    return df_out, df_recent, funnel, is_bull_today, latest_date


# ═══════════════════════════════════════════════════════════════════════════════
#  CHART HELPERS  (funnel + equity — unchanged)
# ═══════════════════════════════════════════════════════════════════════════════

def _chart_funnel(funnel: dict, is_bull: bool) -> go.Figure:
    labels = ['Universe', 'Has Data', 'F1 Trend', 'F2 Price', 'F3 MA Align',
              'F4 vs Low', 'F5 Dip', 'F6 Clean', 'Vol+Breakout']
    keys   = ['total', 'sufficient_data', 'f1', 'f2', 'f3', 'f4', 'f5', 'f6',
              'vol_bk']
    values = [funnel.get(k, 0) for k in keys]
    colors = ['#3a4060'] * len(values)
    colors[-1] = '#00c853' if is_bull else '#ff3d3d'
    colors[-2] = '#7c9cff'

    fig = go.Figure(go.Funnel(
        y=labels, x=values,
        textinfo='value+percent initial',
        textfont=dict(color='#e0e0e0', size=11),
        connector=dict(line=dict(color='#1e2235', width=1)),
        marker=dict(color=colors, line=dict(color='#0e1117', width=1)),
    ))
    fig.update_layout(
        height=340, margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor='#0e1117', plot_bgcolor='#0e1117',
        font=dict(color='#e0e0e0', family='Inter'),
    )
    return fig


def _chart_equity(equity_df: pd.DataFrame) -> go.Figure:
    if equity_df is None or 'Equity' not in equity_df.columns:
        fig = go.Figure()
        fig.update_layout(height=200, paper_bgcolor='#0e1117',
                          annotations=[dict(text='No backtest data', x=0.5, y=0.5,
                                           showarrow=False, font=dict(color='#5a6480'))])
        return fig

    eq = equity_df.copy()
    if 'Date' in eq.columns:
        eq['Date'] = pd.to_datetime(eq['Date'])
        eq = eq.set_index('Date')

    initial = eq['Equity'].iloc[0]
    ret_pct = (eq['Equity'] / initial - 1) * 100

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=eq.index, y=ret_pct,
        mode='lines', name='Portfolio',
        line=dict(color='#00c8ff', width=2),
        fill='tozeroy', fillcolor='rgba(0,200,255,0.05)',
    ))
    fig.add_hline(y=0, line_color='#333', line_dash='dash', line_width=0.8)
    fig.update_layout(
        height=220, margin=dict(l=0, r=0, t=10, b=0),
        paper_bgcolor='#0e1117', plot_bgcolor='#0e1117',
        font=dict(color='#e0e0e0', family='Inter', size=11),
        xaxis=dict(gridcolor='#1e2235', showgrid=True),
        yaxis=dict(gridcolor='#1e2235', showgrid=True,
                   ticksuffix='%', tickformat='+.0f'),
        showlegend=False,
        hovermode='x unified',
    )
    return fig


def _action_badge(action: str) -> str:
    badges = {
        'BUY NOW':     '<span class="badge-buy">🟢 BUY NOW</span>',
        'WATCH':       '<span class="badge-watch">🟡 WATCH</span>',
        'FORMING':     '<span class="badge-forming">🔵 FORMING</span>',
        'BEAR MARKET': '<span class="badge-bear">⛔ BEAR MARKET</span>',
    }
    return badges.get(action, action)


# ═══════════════════════════════════════════════════════════════════════════════
#  INTERACTIVE SIGNAL TABLE  (replaces static Plotly Table)
# ═══════════════════════════════════════════════════════════════════════════════

def _format_signals_for_display(signals: pd.DataFrame) -> pd.DataFrame:
    """Return a display-formatted copy of signals for st.dataframe."""
    display_cols = [
        'Ticker', 'Exchange', 'Signal', 'Action', 'Score',
        'Close (₹)', '52W High (₹)', 'Dist 52W%', '220 EMA (₹)',
        'Vol Ratio', 'Mom 6M%', 'Recovery', 'Stop Loss (₹)', 'Entry Type', 'Chart Qual',
    ]
    disp = signals[[c for c in display_cols if c in signals.columns]].copy().reset_index(drop=True)

    for c in ('Close (₹)', '52W High (₹)', '220 EMA (₹)', 'Stop Loss (₹)'):
        if c in disp.columns:
            disp[c] = disp[c].apply(lambda x: f'₹{x:,.2f}' if pd.notna(x) else '—')
    if 'Dist 52W%' in disp.columns:
        disp['Dist 52W%'] = disp['Dist 52W%'].apply(lambda x: f'{x:+.1f}%')
    if 'Vol Ratio' in disp.columns:
        disp['Vol Ratio'] = disp['Vol Ratio'].apply(lambda x: f'{x:.2f}×')
    if 'Mom 6M%' in disp.columns:
        disp['Mom 6M%'] = disp['Mom 6M%'].apply(lambda x: f'{x:+.1f}%')
    if 'Score' in disp.columns:
        disp['Score'] = disp['Score'].apply(lambda x: f'{x:.0f}/100')
    return disp


def _render_signal_table(signals: pd.DataFrame, table_key: str) -> str | None:
    """
    Render signals as a clickable st.dataframe.
    Returns the Ticker string of the selected row, or None.
    Requires Streamlit >= 1.35 for on_select support.
    """
    if signals.empty:
        st.info('No signals match current filters.')
        return None

    disp = _format_signals_for_display(signals)
    signals_reset = signals.reset_index(drop=True)

    try:
        event = st.dataframe(
            disp,
            width='stretch',
            height=min(620, max(160, 35 * len(disp) + 40)),
            on_select='rerun',
            selection_mode='single-row',
            key=table_key,
        )
        if event.selection and event.selection.rows:
            idx = event.selection.rows[0]
            if idx < len(signals_reset):
                return str(signals_reset.iloc[idx]['Ticker'])
    except TypeError:
        # Fallback for older Streamlit: display without selection
        st.dataframe(disp, width='stretch', key=table_key)

    return None


# ═══════════════════════════════════════════════════════════════════════════════
#  DETAIL VIEW — STATS BAR
# ═══════════════════════════════════════════════════════════════════════════════

def _render_stats_bar(df: pd.DataFrame) -> None:
    """5-metric stats bar: price, change, 52W high/low, avg vol."""
    close  = df['Close']
    volume = df['Volume']

    close_now  = float(close.iloc[-1])
    close_prev = float(close.iloc[-2]) if len(close) >= 2 else close_now
    pct_chg    = (close_now / close_prev - 1) * 100
    high52     = float(close.rolling(HIGH52_P).max().iloc[-1])
    low52      = float(close.rolling(LOW52_P).min().iloc[-1])
    vol_avg30  = float(volume.iloc[-30:].mean())
    vol_str    = (f'{vol_avg30 / 1_000_000:.1f}M' if vol_avg30 >= 1_000_000
                  else f'{vol_avg30 / 1_000:.0f}K')

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.metric('Current Price', f'₹{close_now:,.2f}')
    with c2:
        chg_label = f'{pct_chg:+.2f}%'
        delta_col = 'normal'   # green if positive, red if negative
        st.metric("Today's Change", chg_label, delta=chg_label, delta_color=delta_col)
    with c3:
        st.metric('52-Week High', f'₹{high52:,.2f}')
    with c4:
        st.metric('52-Week Low', f'₹{low52:,.2f}')
    with c5:
        st.metric('Avg Volume (30d)', vol_str)


# ═══════════════════════════════════════════════════════════════════════════════
#  DETAIL VIEW — PRICE CHART WITH OVERLAYS
# ═══════════════════════════════════════════════════════════════════════════════

def _build_detail_chart(ticker: str, df: pd.DataFrame,
                        trades_df: pd.DataFrame | None) -> go.Figure:
    """
    Candlestick chart for the last 252 trading days with:
    - SMA 50 (blue), SMA 150 (orange), EMA 220 (red dotted)
    - 52W High (green dashed) and 52W Low (red dashed) horizontal lines
    - BUY markers (green triangles up) and EXIT markers (red triangles down)
      pulled from trades_df if available
    """
    close  = df['Close']

    # Compute indicators over full history, display last 252 bars
    sma50  = close.rolling(SMA50_P).mean()
    sma150 = close.rolling(SMA150_P).mean()
    ema220 = close.ewm(span=EMA220_P, adjust=False).mean()
    high52 = float(close.rolling(HIGH52_P).max().iloc[-1])
    low52  = float(close.rolling(LOW52_P).min().iloc[-1])

    df_w      = df.tail(252).copy()
    idx       = df_w.index
    sma50_w   = sma50.loc[idx]
    sma150_w  = sma150.loc[idx]
    ema220_w  = ema220.loc[idx]

    fig = go.Figure()

    # ── Candlestick ────────────────────────────────────────────────────────────
    fig.add_trace(go.Candlestick(
        x=idx,
        open=df_w['Open'], high=df_w['High'],
        low=df_w['Low'],   close=df_w['Close'],
        name='Price',
        increasing_line_color='#00c853',
        increasing_fillcolor='rgba(0,200,83,0.35)',
        decreasing_line_color='#ff3d3d',
        decreasing_fillcolor='rgba(255,61,61,0.35)',
    ))

    # ── Moving averages ────────────────────────────────────────────────────────
    fig.add_trace(go.Scatter(
        x=idx, y=sma50_w,
        name='SMA 50', mode='lines',
        line=dict(color='#4c9fff', width=1.5),
    ))
    fig.add_trace(go.Scatter(
        x=idx, y=sma150_w,
        name='SMA 150', mode='lines',
        line=dict(color='#ff9800', width=1.5),
    ))
    fig.add_trace(go.Scatter(
        x=idx, y=ema220_w,
        name='EMA 220', mode='lines',
        line=dict(color='#ff5252', width=2, dash='dot'),
    ))

    # ── 52W high/low horizontal lines ─────────────────────────────────────────
    fig.add_hline(
        y=high52, line_color='rgba(0,200,83,0.65)', line_dash='dash', line_width=1.3,
        annotation_text=f'52W High  ₹{high52:,.2f}',
        annotation_position='bottom right',
        annotation_font=dict(color='#00c853', size=10),
    )
    fig.add_hline(
        y=low52, line_color='rgba(255,61,61,0.65)', line_dash='dash', line_width=1.3,
        annotation_text=f'52W Low  ₹{low52:,.2f}',
        annotation_position='top right',
        annotation_font=dict(color='#ff5252', size=10),
    )

    # ── Trade markers from backtest ────────────────────────────────────────────
    if trades_df is not None and not trades_df.empty:
        # Flexible column detection for different backtest output schemas
        def _find_col(options: list[str]) -> str | None:
            return next((c for c in options if c in trades_df.columns), None)

        ticker_col    = _find_col(['Ticker', 'ticker', 'Symbol', 'symbol'])
        entry_date_c  = _find_col(['EntryDate', 'entry_date', 'Entry Date', 'entry'])
        exit_date_c   = _find_col(['ExitDate',  'exit_date',  'Exit Date',  'exit'])
        entry_price_c = _find_col(['EntryPrice', 'entry_price', 'Entry Price'])
        exit_price_c  = _find_col(['ExitPrice',  'exit_price',  'Exit Price'])

        if ticker_col:
            t = trades_df[trades_df[ticker_col].astype(str) == ticker].copy()

            if not t.empty and entry_date_c:
                entry_dates  = pd.to_datetime(t[entry_date_c], errors='coerce')
                window_start = pd.Timestamp(idx[0])
                mask = entry_dates >= window_start

                if mask.any():
                    ed = entry_dates[mask]
                    if entry_price_c:
                        ep = t.loc[mask, entry_price_c].astype(float).values
                    else:
                        # Fallback: low of the matching bar × 0.98
                        ep = []
                        for d in ed:
                            bar = df_w[df_w.index >= d]
                            ep.append(float(bar['Low'].iloc[0]) * 0.98 if not bar.empty else np.nan)

                    fig.add_trace(go.Scatter(
                        x=ed, y=ep, mode='markers',
                        name='BUY Signal',
                        marker=dict(symbol='triangle-up', size=14,
                                    color='#00e676',
                                    line=dict(color='#ffffff', width=1)),
                        hovertemplate='BUY  ₹%{y:,.2f}<br>%{x}<extra></extra>',
                    ))

            if not t.empty and exit_date_c:
                exit_dates   = pd.to_datetime(t[exit_date_c], errors='coerce')
                window_start = pd.Timestamp(idx[0])
                mask = exit_dates >= window_start

                if mask.any():
                    xd = exit_dates[mask]
                    if exit_price_c:
                        xp = t.loc[mask, exit_price_c].astype(float).values
                    else:
                        xp = []
                        for d in xd:
                            bar = df_w[df_w.index >= d]
                            xp.append(float(bar['High'].iloc[0]) * 1.02 if not bar.empty else np.nan)

                    fig.add_trace(go.Scatter(
                        x=xd, y=xp, mode='markers',
                        name='EXIT Signal',
                        marker=dict(symbol='triangle-down', size=14,
                                    color='#ff1744',
                                    line=dict(color='#ffffff', width=1)),
                        hovertemplate='EXIT  ₹%{y:,.2f}<br>%{x}<extra></extra>',
                    ))

    # ── Layout ─────────────────────────────────────────────────────────────────
    fig.update_layout(
        height=450,
        paper_bgcolor='#0e1117',
        plot_bgcolor='#12172a',
        xaxis=dict(
            gridcolor='#1e2235', showgrid=True,
            rangeslider=dict(visible=False),
            tickformat='%d %b %y',
            tickfont=dict(size=10),
        ),
        yaxis=dict(
            gridcolor='#1e2235', showgrid=True,
            tickprefix='₹', tickformat=',.0f',
            tickfont=dict(size=10),
        ),
        legend=dict(
            orientation='h', y=1.02, x=0,
            font=dict(size=11, color='#8892a4'),
            bgcolor='rgba(0,0,0,0)',
        ),
        font=dict(color='#e0e0e0', family='Inter'),
        margin=dict(l=70, r=30, t=50, b=30),
        hovermode='x unified',
    )
    return fig


# ═══════════════════════════════════════════════════════════════════════════════
#  DETAIL VIEW — CRITERIA PANEL
# ═══════════════════════════════════════════════════════════════════════════════

def _render_criteria_panel(df: pd.DataFrame) -> None:
    """
    Render 6 strategy filter conditions (F1–F6) as a 2×3 grid of ✅/❌ cards,
    then the Breakout Trigger as a separate full-width row.
    All filter values use yesterday's close (no look-ahead), matching the backtest.
    """
    close  = df['Close']
    volume = df['Volume']

    sma50  = close.rolling(SMA50_P).mean()
    sma150 = close.rolling(SMA150_P).mean()
    ema220 = close.ewm(span=EMA220_P, adjust=False).mean()
    high52 = close.rolling(HIGH52_P).max()
    low52  = close.rolling(LOW52_P).min()
    vol20  = volume.rolling(VOLAVG_P).mean()
    vol50  = volume.rolling(VOL_LOOKBACK).mean()

    def _sv(series) -> float:
        return float(series.iloc[-2]) if len(series) >= 2 else np.nan

    close_s  = _sv(close)
    sma50_s  = _sv(sma50)
    sma150_s = _sv(sma150)
    ema220_s = _sv(ema220)
    low52_s  = _sv(low52)
    high52_s = _sv(high52)
    vol20_s  = _sv(vol20)
    vol50_s  = _sv(vol50)
    close_now  = float(close.iloc[-1])
    ema220_now = float(ema220.iloc[-1])
    vol_today  = float(volume.iloc[-1])

    # F5: find last dip date within lookback window (using shifted window = yesterday's data)
    dip_mask   = close < ema220
    dip_recent = dip_mask.iloc[-DIP_LB-1:-1]   # yesterday's lookback window
    had_dip    = bool(dip_recent.any())
    last_dip_str = '—'
    if had_dip:
        dip_dates = dip_recent[dip_recent].index
        if len(dip_dates) > 0:
            last_dip_str = pd.Timestamp(dip_dates[-1]).strftime('%d %b %Y')

    # F6: Choppiness Index (actual backtest F6 — not the breakout!)
    chop_val  = _compute_choppiness(df)
    chop_ok   = chop_val is not None and chop_val < CHOP_THRESH
    chop_str  = f'{chop_val:.1f}' if chop_val is not None else '—'

    threshold_4 = MIN_PRICE_VS_LOW * low52_s if not pd.isna(low52_s) else np.nan

    # Breakout trigger (separate from F1–F6 filters)
    # resistance = yesterday's 252-day rolling max (same definition as compute_signals)
    resistance_p  = close.shift(1).rolling(HIGH52_P).max()
    res_today_cp  = float(resistance_p.iloc[-1]) if not pd.isna(resistance_p.iloc[-1]) else float('nan')
    close_prev_cp = float(close.iloc[-2]) if len(close) >= 2 else float('nan')

    vol_ratio      = (vol_today / vol20_s) if vol20_s > 0 and not pd.isna(vol20_s) else 0
    vol_ratio50    = (vol_today / vol50_s) if (not pd.isna(vol50_s) and vol50_s > 0) else None
    vol_ok_20      = vol_ratio >= VOL_THRESH
    vol_ok_50      = (vol_ratio50 is None) or (vol_ratio50 >= VOL_MULTIPLIER)
    vol_ok_now     = vol_ok_20 and vol_ok_50
    is_bk_today    = (
        not np.isnan(res_today_cp)
        and close_now > res_today_cp
        and close_prev_cp <= res_today_cp
        and close_now > ema220_now
        and vol_ok_now
    )

    conditions = [
        (
            sma150_s > ema220_s,
            'F1 — SMA 150 > EMA 220',
            'Long-term trend is bullish',
            f'SMA150 = ₹{sma150_s:,.2f}   EMA220 = ₹{ema220_s:,.2f}',
        ),
        (
            close_s > sma50_s,
            'F2 — Close > SMA 50',
            'Short-term price above MA',
            f'Close = ₹{close_s:,.2f}   SMA50 = ₹{sma50_s:,.2f}',
        ),
        (
            sma50_s > sma150_s,
            'F3 — SMA 50 > SMA 150',
            'Moving average stack aligned',
            f'SMA50 = ₹{sma50_s:,.2f}   SMA150 = ₹{sma150_s:,.2f}',
        ),
        (
            (not pd.isna(threshold_4)) and close_s >= threshold_4,
            'F4 — Close ≥ 1.25 × 52W Low',
            'Stock well above its yearly low',
            f'Close = ₹{close_s:,.2f}   Min = ₹{threshold_4:,.2f}   52W Low = ₹{low52_s:,.2f}',
        ),
        (
            had_dip,
            f'F5 — Dipped below EMA 220 (last {DIP_LB}d)',
            'The shakeout dip occurred — confirms the setup',
            f'Last dip date: {last_dip_str}',
        ),
        (
            chop_ok,
            'F6 — Choppiness < 61.8',
            'Clean trending chart, not sideways noise',
            f'Choppiness Index = {chop_str}   (threshold = {CHOP_THRESH})',
        ),
    ]

    # Render F1–F6 as 2 rows × 3 columns
    for row_start in (0, 3):
        cols = st.columns(3)
        for i, col in enumerate(cols):
            ci = row_start + i
            if ci >= len(conditions):
                break
            ok, label, subtitle, detail = conditions[ci]
            css_cls = 'crit-ok' if ok else 'crit-fail'
            icon    = '✅' if ok else '❌'
            with col:
                st.markdown(
                    f'<div class="{css_cls}">'
                    f'  <div class="crit-icon">{icon}</div>'
                    f'  <div class="crit-label">{label}</div>'
                    f'  <div style="font-size:10px;color:#6e7891;margin-top:2px;">{subtitle}</div>'
                    f'  <div class="crit-detail">{detail}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    # Breakout Trigger — separate row, checked on today's close (this fires the buy signal)
    st.markdown('<div style="margin-top:10px;"></div>', unsafe_allow_html=True)
    bk_css  = 'crit-ok' if is_bk_today else 'crit-fail'
    bk_icon = '✅' if is_bk_today else '❌'
    vol50_str  = f'{vol_ratio50:.2f}×' if vol_ratio50 is not None else 'N/A'
    res_str    = f'₹{res_today_cp:,.2f}' if not np.isnan(res_today_cp) else '—'
    bk_detail  = (
        f'Close = ₹{close_now:,.2f}   Resistance (prev 52W max) = {res_str}   '
        f'Prev close = ₹{close_prev_cp:,.2f}   EMA220 = ₹{ema220_now:,.2f}   '
        f'Vol/20d = {vol_ratio:.2f}× (need ≥{VOL_THRESH}×)   '
        f'Vol/50d = {vol50_str} (need ≥{VOL_MULTIPLIER}×)'
    )
    st.markdown(
        f'<div class="{bk_css}" style="border-left-color:#f9c200;border-color:rgba(249,194,0,0.3);background:rgba(249,194,0,0.05);">'
        f'  <div class="crit-icon">{bk_icon}</div>'
        f'  <div class="crit-label">🚀 Breakout Trigger — Close > 52W High + Volume confirmed</div>'
        f'  <div style="font-size:10px;color:#6e7891;margin-top:2px;">'
        f'    This is what actually triggers the BUY signal. All 6 filters above must also pass.'
        f'  </div>'
        f'  <div class="crit-detail">{bk_detail}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  DETAIL VIEW — ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════════════════

def _render_stock_detail(ticker: str, signals_df: pd.DataFrame,
                         trades_df: pd.DataFrame | None) -> None:
    """Full detail panel: header → stats bar → chart → criteria grid."""
    ohlcv = load_universe_data()
    df = ohlcv.get(ticker)
    if df is None:
        st.warning(f'No OHLCV data found for **{ticker}**. Try re-running the downloader.')
        return

    # Locate this ticker's signal row for action/signal labels
    match = signals_df[signals_df['Ticker'] == ticker]
    sig_row = match.iloc[0] if not match.empty else None

    action_html = _action_badge(sig_row['Action']) if sig_row is not None else ''
    signal_txt  = sig_row['Signal']   if sig_row is not None else '—'
    score_txt   = f"{sig_row['Score']:.0f}/100" if sig_row is not None else '—'
    recovery    = sig_row['Recovery'] if sig_row is not None else '—'

    # Header strip
    st.markdown(
        f'<div class="detail-header">'
        f'  <span style="font-size:20px;font-weight:900;color:#e4e8f0;">{ticker}</span>'
        f'  &nbsp;&nbsp;{action_html}&nbsp;&nbsp;'
        f'  <span style="font-size:12px;color:#5a6480;">'
        f'    Signal: <b style="color:#8892a4;">{signal_txt}</b>'
        f'    &nbsp;·&nbsp; Score: <b style="color:#8892a4;">{score_txt}</b>'
        f'    &nbsp;·&nbsp; Recovery: <b style="color:#8892a4;">{recovery}</b>'
        f'  </span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── Stats bar ──────────────────────────────────────────────────────────────
    _render_stats_bar(df)
    st.markdown('<br>', unsafe_allow_html=True)

    # ── Price chart ────────────────────────────────────────────────────────────
    st.markdown('<div class="sec-hdr">Price Chart — Last 1 Year</div>', unsafe_allow_html=True)
    st.markdown(
        '<div style="font-size:11px;color:#5a6480;margin-bottom:8px;">'
        'Blue = SMA 50 &nbsp;·&nbsp; Orange = SMA 150 &nbsp;·&nbsp;'
        ' Red dotted = EMA 220 &nbsp;·&nbsp; Green dashed = 52W High &nbsp;·&nbsp;'
        ' Red dashed = 52W Low &nbsp;·&nbsp; ▲ Buy signal &nbsp;·&nbsp; ▼ Exit signal'
        '</div>',
        unsafe_allow_html=True,
    )
    fig = _build_detail_chart(ticker, df, trades_df)
    st.plotly_chart(fig, width='stretch')

    # ── Criteria panel ─────────────────────────────────────────────────────────
    st.markdown('<div class="sec-hdr">Strategy Conditions</div>', unsafe_allow_html=True)
    st.markdown(
        '<div style="font-size:11px;color:#5a6480;margin-bottom:10px;">'
        'F1–F6 filters evaluated on yesterday\'s close (no look-ahead bias). '
        'The Breakout Trigger at the bottom uses today\'s live close.'
        '</div>',
        unsafe_allow_html=True,
    )
    _render_criteria_panel(df)


# ═══════════════════════════════════════════════════════════════════════════════
#  BACKTEST REPORT — ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

def _bt_run_single(ticker: str, df: pd.DataFrame,
                   start: pd.Timestamp, end: pd.Timestamp) -> tuple[list[dict], list[str]]:
    """
    Walk-forward backtest for one ticker. No capital math — returns only %.
    Signal: F1–F5 + breakout (close_prev > 52W_high_prev, close_prev > EMA220_prev, vol > 1.5× avg).
    Entry:  next-bar Open after signal.
    Exit A: next-bar Open when prev_close < EMA220.
    Exit B: next-bar Open when prev_close < entry_price × 0.85.
    All conditions evaluated on PREVIOUS bar's close — zero look-ahead.
    """
    trades: list[dict] = []
    warns:  list[str]  = []

    close  = df['Close']
    open_  = df['Open']
    volume = df['Volume']

    sma50   = close.rolling(SMA50_P,  min_periods=SMA50_P ).mean()
    sma150  = close.rolling(SMA150_P, min_periods=SMA150_P).mean()
    ema220  = close.ewm(span=EMA220_P, adjust=False).mean()
    high52  = close.rolling(HIGH52_P, min_periods=HIGH52_P).max()
    low52   = close.rolling(LOW52_P,  min_periods=LOW52_P ).min()
    vol20   = volume.rolling(VOLAVG_P,  min_periods=VOLAVG_P ).mean()
    vol50   = volume.rolling(VOL_LOOKBACK, min_periods=VOL_LOOKBACK).mean()
    had_dip = (close < ema220).rolling(DIP_LB, min_periods=1).max()

    arr_c   = close.values.astype(float)
    arr_o   = open_.values.astype(float)
    arr_v   = volume.values.astype(float)
    arr_e   = ema220.values.astype(float)
    arr_s50 = sma50.values.astype(float)
    arr_s150= sma150.values.astype(float)
    arr_h52 = high52.values.astype(float)
    arr_l52 = low52.values.astype(float)
    arr_v20 = vol20.values.astype(float)
    arr_v50 = vol50.values.astype(float)
    arr_dip = had_dip.values.astype(float)
    dates   = df.index
    n       = len(dates)

    # Find start/end positions
    start_i = 0
    for k in range(n):
        if dates[k] >= start:
            start_i = k
            break
    end_i = n - 1
    for k in range(n - 1, -1, -1):
        if dates[k] <= end:
            end_i = k
            break

    start_i = max(start_i, HIGH52_P + 1)
    if start_i > end_i:
        return trades, warns

    in_trade    = False
    entry_price = 0.0
    entry_date  = None

    i = start_i
    while i <= end_i:
        prev = i - 1

        if in_trade:
            c_p = arr_c[prev]
            e_p = arr_e[prev]
            exit_a = (not np.isnan(c_p)) and (not np.isnan(e_p)) and c_p < e_p
            exit_b = (not np.isnan(c_p)) and c_p < entry_price * 0.85

            if exit_a or exit_b:
                ex_px = arr_o[i]
                if not np.isnan(ex_px) and ex_px > 0:
                    ret    = (ex_px / entry_price - 1) * 100
                    reason = 'Stop Loss' if exit_b else 'EMA Cross'
                    trades.append({
                        'Ticker':     ticker,
                        'EntryDate':  entry_date,
                        'ExitDate':   dates[i],
                        'EntryPrice': round(float(entry_price), 4),
                        'ExitPrice':  round(float(ex_px), 4),
                        'Return%':    round(ret, 4),
                        'ExitReason': reason,
                    })
                in_trade = False

        else:
            s_c    = arr_c[prev]
            s_e    = arr_e[prev]
            s_s50  = arr_s50[prev]
            s_s150 = arr_s150[prev]
            # Use prev-1 as 52W high reference: rolling max at [prev] includes close[prev]
            # so close[prev] > high52[prev] is always false. Use high52[prev-1] instead.
            s_h52  = arr_h52[prev - 1] if prev >= 1 else arr_h52[prev]
            s_l52  = arr_l52[prev]
            s_v20  = arr_v20[prev]
            s_v50  = arr_v50[prev]
            s_v    = arr_v[prev]
            s_dip  = arr_dip[prev]

            if any(np.isnan(x) for x in [s_e, s_s50, s_s150, s_h52, s_l52, s_v50]):
                i += 1
                continue

            f1  = s_s150 > s_e
            f2  = s_c > s_s50
            f3  = s_s50 > s_s150
            f4  = s_c >= MIN_PRICE_VS_LOW * s_l52
            f5  = s_dip >= 0.5
            # F6: choppiness check on prev bar's trailing window
            chop_prev = _compute_choppiness(df.iloc[:prev + 1])
            f6  = (chop_prev is None) or (chop_prev < CHOP_THRESH)
            bk     = (s_c > s_h52) and (s_c > s_e)
            vol_ok = (not np.isnan(s_v50)) and s_v50 > 0 and (s_v >= VOL_MULTIPLIER * s_v50)

            if f1 and f2 and f3 and f4 and f5 and f6 and bk and vol_ok:
                en_px = arr_o[i]
                if np.isnan(en_px) or en_px <= 0:
                    i += 1
                    continue
                # Error check: entry open == signal-day close (data quality flag)
                if not np.isnan(s_c) and abs(en_px - s_c) < 0.001:
                    warns.append(
                        f'{ticker} {str(dates[i].date())}: '
                        f'entry_open (₹{en_px:.2f}) = prev_close — possible data gap'
                    )
                entry_price = en_px
                entry_date  = dates[i]
                in_trade    = True

        i += 1

    # Close any open position at period end
    if in_trade:
        last_px = arr_c[end_i]
        if not np.isnan(last_px) and last_px > 0:
            trades.append({
                'Ticker':     ticker,
                'EntryDate':  entry_date,
                'ExitDate':   dates[end_i],
                'EntryPrice': round(float(entry_price), 4),
                'ExitPrice':  round(float(last_px), 4),
                'Return%':    round((last_px / entry_price - 1) * 100, 4),
                'ExitReason': 'Still Open',
            })

    return trades, warns


@st.cache_data(ttl=3600, show_spinner=False)
def _bt_compute(start_str: str, end_str: str, nse_only: bool) -> dict:
    """
    Cached backtest across all loaded stocks.
    String args so st.cache_data can hash them cleanly.
    """
    ohlcv  = load_universe_data()
    start  = pd.Timestamp(start_str)
    end    = pd.Timestamp(end_str)

    all_trades: list[dict] = []
    all_warns:  list[str]  = []
    short_data: list[str]  = []

    for ticker, df in ohlcv.items():
        if nse_only and not ticker.endswith('.NS'):
            continue
        if len(df) < 300:
            short_data.append(f'{ticker}: only {len(df)} bars (< 300 required)')
            continue
        trd, wrn = _bt_run_single(ticker, df, start, end)
        all_trades.extend(trd)
        all_warns.extend(wrn)

    return {'trades': all_trades, 'warnings': all_warns, 'short_data': short_data}


# ═══════════════════════════════════════════════════════════════════════════════
#  BACKTEST REPORT — CHARTS
# ═══════════════════════════════════════════════════════════════════════════════

def _bt_equity_chart(closed: pd.DataFrame) -> go.Figure:
    _empty = go.Figure()
    _empty.update_layout(
        height=280, paper_bgcolor='#0e1117',
        annotations=[dict(text='No closed trades to plot.', x=0.5, y=0.5,
                          showarrow=False, font=dict(color='#5a6480', size=13))],
    )
    if closed.empty:
        return _empty

    df = closed.copy().sort_values('EntryDate').reset_index(drop=True)
    equity  = (1 + df['Return%'] / 100).cumprod()
    cum_ret = (equity - 1) * 100
    roll_max = equity.cummax()
    drawdown = (equity / roll_max - 1) * 100

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df['EntryDate'], y=cum_ret,
        mode='lines', name='Cumulative Return',
        line=dict(color='#00c8ff', width=2),
        fill='tozeroy', fillcolor='rgba(0,200,255,0.06)',
        hovertemplate='%{x|%d %b %Y}  %{y:+.1f}%<extra></extra>',
    ))
    fig.add_trace(go.Scatter(
        x=df['EntryDate'], y=drawdown,
        mode='lines', name='Drawdown',
        line=dict(color='rgba(255,80,80,0.55)', width=1, dash='dot'),
        yaxis='y2',
        hovertemplate='DD: %{y:.1f}%<extra></extra>',
    ))
    fig.add_hline(y=0, line_color='#2a2f45', line_width=1)

    dd_min = float(drawdown.min()) if len(drawdown) > 0 else -50
    fig.update_layout(
        height=310,
        paper_bgcolor='#0e1117', plot_bgcolor='#12172a',
        font=dict(color='#e0e0e0', family='Inter', size=11),
        margin=dict(l=60, r=70, t=30, b=30),
        hovermode='x unified',
        xaxis=dict(gridcolor='#1e2235', tickformat='%b %y'),
        yaxis=dict(
            gridcolor='#1e2235', ticksuffix='%', tickformat='+.0f',
            title=dict(text='Cumulative Return', font=dict(size=10)),
        ),
        yaxis2=dict(
            overlaying='y', side='right', showgrid=False,
            ticksuffix='%', tickformat='.0f',
            title=dict(text='Drawdown', font=dict(size=10)),
            range=[dd_min * 2.2, 5],
        ),
        legend=dict(orientation='h', y=1.02, x=0, font=dict(size=10),
                    bgcolor='rgba(0,0,0,0)'),
    )
    return fig


def _bt_monthly_heatmap(closed: pd.DataFrame) -> go.Figure:
    if closed.empty:
        return go.Figure().update_layout(height=160, paper_bgcolor='#0e1117')

    df = closed.copy()
    df['ExitDate'] = pd.to_datetime(df['ExitDate'], errors='coerce')
    df = df.dropna(subset=['ExitDate', 'Return%'])
    if df.empty:
        return go.Figure().update_layout(height=160, paper_bgcolor='#0e1117')

    df['Year']  = df['ExitDate'].dt.year
    df['Month'] = df['ExitDate'].dt.month
    monthly = df.groupby(['Year', 'Month'])['Return%'].mean().reset_index()

    years  = sorted(monthly['Year'].unique())
    months = list(range(1, 13))

    z = []
    for yr in years:
        yr_rows = monthly[monthly['Year'] == yr]
        row = []
        for mo in months:
            v = yr_rows[yr_rows['Month'] == mo]['Return%']
            row.append(round(float(v.iloc[0]), 2) if len(v) > 0 else None)
        z.append(row)

    flat = [v for row in z for v in row if v is not None]
    zmax = max(abs(min(flat, default=0)), abs(max(flat, default=0)), 1)

    fig = go.Figure(go.Heatmap(
        z=z,
        x=[calendar.month_abbr[m] for m in months],
        y=[str(yr) for yr in years],
        colorscale=[
            [0.0,  '#7b0000'], [0.35, '#cc3333'],
            [0.5,  '#1e2235'],
            [0.65, '#33aa66'], [1.0,  '#006622'],
        ],
        zmid=0, zmin=-zmax, zmax=zmax,
        text=[[f'{v:+.1f}%' if v is not None else '—' for v in row] for row in z],
        texttemplate='%{text}',
        textfont=dict(size=10, color='#ffffff'),
        hovertemplate='%{y}  %{x}: %{z:+.2f}%<extra></extra>',
        showscale=True,
        colorbar=dict(
            ticksuffix='%', thickness=12,
            tickfont=dict(color='#8892a4', size=10),
            title=dict(text='Avg %', font=dict(color='#8892a4', size=10)),
        ),
    ))
    fig.update_layout(
        height=max(180, 38 * len(years) + 80),
        paper_bgcolor='#0e1117', plot_bgcolor='#0e1117',
        font=dict(color='#e0e0e0', family='Inter', size=11),
        margin=dict(l=60, r=60, t=40, b=20),
        xaxis=dict(side='top', tickfont=dict(size=11)),
        yaxis=dict(tickfont=dict(size=11), autorange='reversed'),
    )
    return fig


# ═══════════════════════════════════════════════════════════════════════════════
#  BACKTEST REPORT — PAGE RENDERER
# ═══════════════════════════════════════════════════════════════════════════════

def _bt_render_results(results: dict) -> None:
    """Render metrics, charts, warnings, and trade log from a completed backtest."""
    trades_raw = results.get('trades', [])
    all_warns  = results.get('warnings', [])
    short_data = results.get('short_data', [])

    # ── Warning boxes ──────────────────────────────────────────────────────────
    if short_data:
        with st.expander(
            f'⚠️ {len(short_data)} stocks skipped — fewer than 300 bars of data',
            expanded=False,
        ):
            st.caption(
                '\n'.join(short_data[:60])
                + (f'\n… and {len(short_data) - 60} more' if len(short_data) > 60 else '')
            )

    if all_warns:
        with st.expander(
            f'⚠️ {len(all_warns)} data-quality notices  (entry open ≈ signal-day close)',
            expanded=False,
        ):
            st.caption(
                '\n'.join(all_warns[:60])
                + (f'\n… and {len(all_warns) - 60} more' if len(all_warns) > 60 else '')
            )

    if not trades_raw:
        st.warning('No trades found in this date range. Try widening the date range or checking data.')
        return

    trades_df = pd.DataFrame(trades_raw)
    trades_df['EntryDate'] = pd.to_datetime(trades_df['EntryDate'])
    trades_df['ExitDate']  = pd.to_datetime(trades_df['ExitDate'])

    closed = trades_df[trades_df['ExitReason'] != 'Still Open'].copy()
    wins   = closed[closed['Return%'] > 0]
    losses = closed[closed['Return%'] <= 0]

    n_total  = len(closed)
    win_rate = (len(wins) / n_total * 100) if n_total > 0 else 0
    avg_win  = float(wins['Return%'].mean())   if len(wins)   > 0 else 0.0
    avg_loss = float(losses['Return%'].mean()) if len(losses) > 0 else 0.0
    g_profit = wins['Return%'].sum()
    g_loss   = abs(losses['Return%'].sum())
    pf       = (g_profit / g_loss) if g_loss > 0 else float('inf')

    if not closed.empty:
        eq_s   = (1 + closed.sort_values('EntryDate')['Return%'] / 100).cumprod()
        max_dd = float(((eq_s / eq_s.cummax()) - 1).min() * 100)
    else:
        max_dd = 0.0

    best_row  = closed.loc[closed['Return%'].idxmax()] if not closed.empty else None
    worst_row = closed.loc[closed['Return%'].idxmin()] if not closed.empty else None

    # ── Performance summary ────────────────────────────────────────────────────
    st.markdown('<div class="sec-hdr">Performance Summary</div>', unsafe_allow_html=True)

    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        st.metric('Total Trades', n_total,
                  help='Closed trades only (open positions excluded from metrics)')
    with m2:
        st.metric('Win Rate', f'{win_rate:.1f}%',
                  delta=f'{win_rate - 50:.1f}pp vs 50%', delta_color='normal')
    with m3:
        st.metric('Avg Winning Trade', f'+{avg_win:.2f}%')
    with m4:
        st.metric('Avg Losing Trade', f'{avg_loss:.2f}%')
    with m5:
        pf_str = f'{pf:.2f}×' if pf != float('inf') else '∞'
        st.metric('Profit Factor', pf_str,
                  help='Gross profit ÷ gross loss across all trades. Above 1.5× is considered good.')

    st.markdown('<br>', unsafe_allow_html=True)
    m6, m7, m8, _ = st.columns([1, 1, 1, 2])
    with m6:
        st.metric('Max Drawdown', f'{max_dd:.1f}%',
                  help='Largest peak-to-trough drop in the cumulative return curve')
    with m7:
        if best_row is not None:
            st.metric(
                'Best Trade', f'+{best_row["Return%"]:.1f}%',
                help=(f'{best_row["Ticker"]}  ·  '
                      f'{pd.Timestamp(best_row["EntryDate"]).strftime("%d %b %Y")} → '
                      f'{pd.Timestamp(best_row["ExitDate"]).strftime("%d %b %Y")}'),
            )
    with m8:
        if worst_row is not None:
            st.metric(
                'Worst Trade', f'{worst_row["Return%"]:.1f}%',
                help=(f'{worst_row["Ticker"]}  ·  '
                      f'{pd.Timestamp(worst_row["EntryDate"]).strftime("%d %b %Y")} → '
                      f'{pd.Timestamp(worst_row["ExitDate"]).strftime("%d %b %Y")}'),
            )

    # ── Best / Worst cards ─────────────────────────────────────────────────────
    if best_row is not None and worst_row is not None:
        bc1, bc2 = st.columns(2)
        with bc1:
            st.markdown(f"""
            <div style="background:rgba(0,200,83,0.08);border:1px solid rgba(0,200,83,0.25);
                 border-left:4px solid #00c853;border-radius:8px;padding:12px 16px;margin-top:8px;">
              <div style="font-size:11px;color:#6e7891;margin-bottom:4px;">🏆 BEST TRADE</div>
              <div style="font-size:20px;font-weight:900;color:#00c853;">+{best_row['Return%']:.1f}%</div>
              <div style="font-size:13px;color:#e0e0e0;margin-top:4px;font-weight:700;">{best_row['Ticker']}</div>
              <div style="font-size:11px;color:#5a6480;margin-top:3px;">
                {pd.Timestamp(best_row['EntryDate']).strftime('%d %b %Y')} →
                {pd.Timestamp(best_row['ExitDate']).strftime('%d %b %Y')}
                &nbsp;·&nbsp; {best_row['ExitReason']}
              </div>
            </div>""", unsafe_allow_html=True)
        with bc2:
            st.markdown(f"""
            <div style="background:rgba(255,61,61,0.08);border:1px solid rgba(255,61,61,0.25);
                 border-left:4px solid #ff3d3d;border-radius:8px;padding:12px 16px;margin-top:8px;">
              <div style="font-size:11px;color:#6e7891;margin-bottom:4px;">💔 WORST TRADE</div>
              <div style="font-size:20px;font-weight:900;color:#ff3d3d;">{worst_row['Return%']:.1f}%</div>
              <div style="font-size:13px;color:#e0e0e0;margin-top:4px;font-weight:700;">{worst_row['Ticker']}</div>
              <div style="font-size:11px;color:#5a6480;margin-top:3px;">
                {pd.Timestamp(worst_row['EntryDate']).strftime('%d %b %Y')} →
                {pd.Timestamp(worst_row['ExitDate']).strftime('%d %b %Y')}
                &nbsp;·&nbsp; {worst_row['ExitReason']}
              </div>
            </div>""", unsafe_allow_html=True)

    st.markdown('<br>', unsafe_allow_html=True)

    # ── Equity curve ───────────────────────────────────────────────────────────
    st.markdown('<div class="sec-hdr">Equity Curve — Cumulative Return %</div>',
                unsafe_allow_html=True)
    st.markdown(
        '<div style="font-size:11px;color:#5a6480;margin-bottom:8px;">'
        'Compounded cumulative return of all closed trades sorted by entry date. '
        'Dotted red line = drawdown from peak (right axis).'
        '</div>',
        unsafe_allow_html=True,
    )
    st.plotly_chart(_bt_equity_chart(closed), width='stretch')

    # ── Monthly heatmap ────────────────────────────────────────────────────────
    st.markdown('<div class="sec-hdr">Monthly Returns Heatmap</div>', unsafe_allow_html=True)
    st.markdown(
        '<div style="font-size:11px;color:#5a6480;margin-bottom:8px;">'
        'Average return % of trades <i>closed</i> in each calendar month. '
        'Green = profitable · Red = losing · Dark = no trades closed that month.'
        '</div>',
        unsafe_allow_html=True,
    )
    st.plotly_chart(_bt_monthly_heatmap(closed), width='stretch')

    # ── Trade log ──────────────────────────────────────────────────────────────
    st.markdown('<div class="sec-hdr">Trade Log</div>', unsafe_allow_html=True)
    n_open = len(trades_df) - n_total
    st.markdown(
        f'<div style="font-size:11px;color:#5a6480;margin-bottom:8px;">'
        f'{n_total} closed trades · {n_open} still open at end of period'
        f'</div>',
        unsafe_allow_html=True,
    )
    with st.expander(f'View all {len(trades_df)} trades', expanded=False):
        show = trades_df.copy()
        show['EntryDate'] = show['EntryDate'].dt.strftime('%d %b %Y')
        show['ExitDate']  = show['ExitDate'].dt.strftime('%d %b %Y')
        for c in ('EntryPrice', 'ExitPrice'):
            show[c] = show[c].apply(lambda x: f'₹{x:,.2f}')
        show['Return%'] = show['Return%'].apply(lambda x: f'{x:+.2f}%')
        show = show.sort_values('EntryDate', ascending=False)
        st.dataframe(show, width='stretch', height=400)


def _render_backtest_report() -> None:
    """
    Backtest Report tab — fully self-contained.
    Does not read or write any state used by the Live Screener tab.
    """
    st.markdown("""
    <div style="padding:4px 0 12px 0;">
      <div class="page-title">📋 Backtest Report</div>
      <div class="page-sub">
        Walk-forward backtest of Momentum Edge signals on loaded NSE/BSE stocks.
        Entry at next-bar open &nbsp;·&nbsp; Exit at next-bar open after exit condition fires on prior close.
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="explain-box">
      <b>How the backtest works:</b> Each day, every stock's <i>previous</i> closing price is checked against
      all 6 filters (F1–F5 + breakout). When all conditions pass, the strategy enters at
      <b>tomorrow's open price</b> — no look-ahead bias. It exits at tomorrow's open when
      yesterday's close falls below the 220-day EMA (Exit A) or drops 15% from entry (Exit B).
      All metrics are based on open-to-open price change, not closing prices.
    </div>
    """, unsafe_allow_html=True)

    # ── Parameters ─────────────────────────────────────────────────────────────
    st.markdown('<div class="sec-hdr">Parameters</div>', unsafe_allow_html=True)

    pc1, pc2, pc3, _ = st.columns([1.2, 1.2, 1.2, 2])
    with pc1:
        start_dt = st.date_input('Start Date', value=datetime(2018, 1, 1).date(), key='bt_sd')
    with pc2:
        end_dt   = st.date_input('End Date',   value=datetime.today().date(),      key='bt_ed')
    with pc3:
        nse_only = (
            st.selectbox('Universe', ['NSE Only', 'NSE + BSE'], key='bt_uni') == 'NSE Only'
        )

    if start_dt >= end_dt:
        st.error('Start date must be before end date.')
        return

    params_key = f'{start_dt}|{end_dt}|{nse_only}'

    rb_col, _ = st.columns([1, 5])
    with rb_col:
        run_btn = st.button('▶  Run Backtest', type='primary',
                            width='stretch', key='bt_run')

    st.markdown("""
    <div style="font-size:11px;color:#5a6480;margin:6px 0 16px 0;">
      ⏱ First run may take several minutes for large universes.
      Results are cached — re-clicking with the same dates is instant.
    </div>
    """, unsafe_allow_html=True)

    # ── Run and store ───────────────────────────────────────────────────────────
    if run_btn:
        with st.spinner('Running backtest across all stocks…'):
            results = _bt_compute(str(start_dt), str(end_dt), nse_only)
        st.session_state['bt_results'] = results
        st.session_state['bt_key']     = params_key

    # ── Show results ────────────────────────────────────────────────────────────
    stored = st.session_state.get('bt_results')
    stored_key = st.session_state.get('bt_key')

    if stored is None:
        st.info('Set parameters above and click **▶ Run Backtest** to generate the report.')
        return

    if stored_key != params_key:
        st.warning('Parameters have changed. Click **▶ Run Backtest** to recompute.')

    _bt_render_results(stored)


# ═══════════════════════════════════════════════════════════════════════════════
#  SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════════

def render_sidebar() -> dict:
    with st.sidebar:
        st.markdown("""
        <div style="padding:8px 0 20px 0;">
          <div style="font-size:18px;font-weight:800;color:#E8EDF5;letter-spacing:-0.02em;">📈 Momentum Edge</div>
          <div style="font-size:10px;color:#2A3A58;margin-top:3px;text-transform:uppercase;letter-spacing:0.08em;font-weight:600;">NSE + BSE Universe Scanner</div>
          <div style="height:1px;background:linear-gradient(90deg,rgba(79,123,255,0.4),transparent);margin-top:10px;"></div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown('<div style="font-size:12px;font-weight:700;color:#7c9cff;margin-bottom:8px;">FILTER CONTROLS</div>', unsafe_allow_html=True)
        st.caption('Toggle filters on/off to test their impact')

        use_regime = st.checkbox('☑ Market Regime Filter (Nifty > EMA220)', value=True)
        f1  = st.checkbox('☑ F1: SMA150 > EMA220  (trend)',        value=True)
        f2  = st.checkbox('☑ F2: Close > SMA50  (short strength)',  value=True)
        f3  = st.checkbox('☑ F3: SMA50 > SMA150  (MA alignment)',   value=True)
        f4  = st.checkbox('☑ F4: Price > 1.25× 52W low',           value=True)
        f5  = st.checkbox('☑ F5: Dipped below EMA220 (90 days)',    value=True)
        f6  = st.checkbox('☑ F6: Choppiness < 61.8  (clean chart)', value=True)
        vol_chk = st.checkbox('☑ Volume confirmation (1.5× avg)',   value=True)

        st.markdown('<hr style="margin:12px 0;border-color:#1e2235;">', unsafe_allow_html=True)

        min_score = st.slider('Min Score threshold', 0, 100, 40, step=5)
        exchange  = st.selectbox('Exchange filter', ['All', 'NSE Only', 'BSE Only'])

        st.markdown('<hr style="margin:12px 0;border-color:#1e2235;">', unsafe_allow_html=True)

        if st.button('🔄 Refresh Signals', width='stretch'):
            st.cache_data.clear()
            st.session_state.pop('selected_ticker', None)
            st.rerun()

        st.markdown("""
        <div style="margin-top:16px;font-size:10px;color:#3a4060;line-height:1.8;">
          <b style="color:#5a6480;">Run order:</b><br>
          1. python build_universe.py<br>
          2. python nse_bse_downloader.py<br>
          3. python momentum_edge_backtest.py<br>
          4. streamlit run this file
        </div>
        """, unsafe_allow_html=True)

    return {
        'regime': use_regime, 'f1': f1, 'f2': f2, 'f3': f3,
        'f4': f4, 'f5': f5, 'f6': f6, 'vol': vol_chk,
        'min_score': min_score, 'exchange': exchange,
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN PAGE
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    # Session state init
    if 'selected_ticker' not in st.session_state:
        st.session_state['selected_ticker'] = None

    controls = render_sidebar()

    render_staleness_banner("momentum", "momentum_edge_data")

    # ── Top-level tabs ─────────────────────────────────────────────────────────
    tab_scr, tab_bt = st.tabs(['📊 Live Screener', '📋 Backtest Report'])

    with tab_scr:
        st.markdown("""
        <div style="padding:4px 0 12px 0;">
          <div class="page-title">📈 Momentum Edge Screener</div>
          <div class="page-sub">
            NSE + BSE universe &nbsp;·&nbsp; 220-EMA shakeout-recovery ATH breakout strategy
            &nbsp;·&nbsp; <b>Click any row</b> for a full price chart and criteria breakdown
          </div>
        </div>
        """, unsafe_allow_html=True)

        # ── Load data ──────────────────────────────────────────────────────────
        with st.spinner('Computing signals across universe…'):
            sigs, recent_sigs, funnel, is_bull, latest_date = compute_signals(
                filters_active={k: controls[k] for k in ('regime','f1','f2','f3','f4','f5','f6','vol')},
                min_score=controls['min_score'],
                exchange_filter=controls['exchange'],
            )
        trades_df, equity_df = load_backtest_data()

        # Clear selection if selected ticker no longer appears (e.g., after filter change)
        sel = st.session_state.get('selected_ticker')
        if sel and (sigs.empty or sel not in sigs['Ticker'].values):
            st.session_state['selected_ticker'] = None
            sel = None

        # ── Data Staleness Warning ─────────────────────────────────────────────
        if latest_date is not None:
            from datetime import date as _date
            today_d = _date.today()
            data_d  = latest_date.date() if hasattr(latest_date, 'date') else latest_date
            lag     = (today_d - data_d).days
            if lag >= 2:
                st.warning(
                    f"⚠️ **Data is {lag} days old** — last updated **{data_d}**, today is **{today_d}**. "
                    f"Signals shown below reflect market conditions on {data_d}, NOT today. "
                    f"Stocks that barely passed filters on {data_d} may have already moved off their levels. "
                    f"Run **`python nse_bse_downloader.py`** to download fresh data before checking signals.",
                    icon=None,
                )

        # ── Market Regime Banner ───────────────────────────────────────────────
        if is_bull:
            st.markdown(
                '<div class="regime-bull">'
                '<div class="regime-bull-title">🟢 BULL MARKET — Strategy Active</div>'
                '<div class="regime-sub">Nifty 50 passes all 3 regime conditions. New buy signals are active. Follow breakout setups with proper position sizing.</div>'
                '<div class="regime-pills">'
                '<span class="regime-pill pill-ok">Close &gt; SMA 200</span>'
                '<span class="regime-pill pill-ok">SMA 50 &gt; SMA 200</span>'
                '<span class="regime-pill pill-ok">Within 10% of 52W High</span>'
                '</div>'
                '</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div class="regime-bear">'
                '<div class="regime-bear-title">🔴 BEAR MARKET — No New Entries</div>'
                '<div class="regime-sub">Nifty 50 failed one or more regime conditions. All new entries are paused. Existing positions follow their own exit rules.</div>'
                '<div class="regime-pills">'
                '<span class="regime-pill pill-fail">Regime Filter Active</span>'
                '<span class="regime-pill pill-fail">No new signals</span>'
                '</div>'
                '</div>',
                unsafe_allow_html=True,
            )

        # ── Universe Stats Bar (4 cards) ───────────────────────────────────────
        n_bk   = int((sigs['Signal'] == 'Breakout Today').sum()) if not sigs.empty else 0
        n_near = int((sigs['Signal'] == 'Near Breakout').sum())  if not sigs.empty else 0

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(f"""<div class="me-card">
              <div class="label">Total Universe</div>
              <div class="value" style="color:#7C9CFF;">{funnel['total']:,}</div>
              <div class="sub">NSE + BSE stocks loaded</div>
              <div class="me-card-accent" style="background:#4F7BFF;"></div>
            </div>""", unsafe_allow_html=True)
        with c2:
            st.markdown(f"""<div class="me-card">
              <div class="label">Pass All 6 Filters</div>
              <div class="value" style="color:#00D480;">{funnel['f6']:,}</div>
              <div class="sub">of {funnel['sufficient_data']:,} with sufficient data</div>
              <div class="me-card-accent" style="background:#00D480;"></div>
            </div>""", unsafe_allow_html=True)
        with c3:
            st.markdown(f"""<div class="me-card">
              <div class="label">Pass Vol + Breakout</div>
              <div class="value" style="color:#F5B731;">{funnel['vol_bk']:,}</div>
              <div class="sub">volume surge on breakout day</div>
              <div class="me-card-accent" style="background:#F5B731;"></div>
            </div>""", unsafe_allow_html=True)
        with c4:
            st.markdown(f"""<div class="me-card">
              <div class="label">Breakout Today 🔥</div>
              <div class="value" style="color:#00D480;">{n_bk}</div>
              <div class="sub">Near: {n_near} &nbsp;·&nbsp; All signals: {len(sigs)}</div>
              <div class="me-card-accent" style="background:linear-gradient(90deg,#00D480,#4F7BFF);"></div>
            </div>""", unsafe_allow_html=True)

        st.markdown('<br>', unsafe_allow_html=True)

        # ── Two-column layout: signals + funnel ───────────────────────────────
        col_main, col_side = st.columns([3, 1])

        with col_main:
            st.markdown('<div class="sec-hdr">Live Signals — Click a row to see details</div>',
                        unsafe_allow_html=True)

            st.markdown("""
            <div class="explain-box">
              <b>How to read this table:</b>
              <b>Score /100</b> = overall setup quality (6M momentum rank + breakout proximity + volume surge + recovery speed).
              <b>52W High (₹)</b> = yesterday's 52-week high — the price level the stock is trying to break above.
              <b>Dist 52W%</b> = how far today's close is from the 52-week high (+0.5% = just above, −2% = still below).
              <b>Entry Type</b> = ATH means today's close broke an all-time high; 52W High means it only broke the 1-year high.
              <b>Vol Ratio</b> = today's volume ÷ 50-day average (2.0× means 2× normal buying pressure).
              Green rows = Breakout Today · Yellow = Near Breakout · Blue = Forming/Watch.
              <b>Click any row</b> to open the price chart and all 6 filter conditions.
            </div>
            """, unsafe_allow_html=True)

            n_recent = len(recent_sigs) if not recent_sigs.empty else 0
            tab_all, tab_buy, tab_watch, tab_forming, tab_recent = st.tabs(
                ['All Signals', '🟢 Buy Now', '🟡 Watch', '🔵 Forming',
                 f'🔄 Recent 7d ({n_recent})']
            )

            def _handle_tab(df_tab: pd.DataFrame, key: str) -> None:
                picked = _render_signal_table(df_tab, key)
                if picked:
                    st.session_state['selected_ticker'] = picked

            with tab_all:
                _handle_tab(sigs, 'tbl_all')

            with tab_buy:
                _handle_tab(
                    sigs[sigs['Signal'] == 'Breakout Today'] if not sigs.empty else sigs,
                    'tbl_buy',
                )

            with tab_watch:
                _handle_tab(
                    sigs[sigs['Signal'] == 'Near Breakout'] if not sigs.empty else sigs,
                    'tbl_watch',
                )

            with tab_forming:
                _handle_tab(
                    sigs[sigs['Signal'].isin(['Watch Zone', 'Watchlist'])] if not sigs.empty else sigs,
                    'tbl_forming',
                )

            with tab_recent:
                st.markdown("""
                <div class="explain-box">
                  <b>Recent Breakouts (last 7 trading days)</b> — These stocks had their first-close above
                  52-week resistance within the past week. They may still be buyable if the price hasn't
                  extended too far. Check <b>% Extended</b> (how much above breakout price today's close is)
                  and <b>Bk Price (₹)</b> (the actual breakout bar close). Still above EMA220 = trend intact.
                  Stop loss is 15% below current close.
                </div>""", unsafe_allow_html=True)
                if recent_sigs.empty:
                    st.markdown('<div style="color:#5a6480;padding:16px;">No recent breakouts found in the last 7 trading days.</div>',
                                unsafe_allow_html=True)
                else:
                    display_cols = ['Ticker', 'Exchange', 'Days Ago', 'Close (₹)', 'Bk Price (₹)',
                                    '% Extended', '220 EMA (₹)', 'Vol Ratio', 'Stop Loss (₹)', 'Mom 6M%']
                    show_cols = [c for c in display_cols if c in recent_sigs.columns]
                    st.dataframe(
                        recent_sigs[show_cols].reset_index(drop=True),
                        width='stretch',
                        hide_index=True,
                    )

        with col_side:
            st.markdown('<div class="sec-hdr">Filter Funnel</div>', unsafe_allow_html=True)
            st.markdown("""
            <div style="font-size:11px;color:#5a6480;margin-bottom:8px;">
              Each step shows how many stocks survive. A big drop = that filter is very selective.
            </div>""", unsafe_allow_html=True)
            st.plotly_chart(_chart_funnel(funnel, is_bull), width='stretch')

            funnel_labels = [
                ('Universe',      funnel['total']),
                ('Has Data',      funnel['sufficient_data']),
                ('F1 Trend',      funnel['f1']),
                ('F2 Price',      funnel['f2']),
                ('F3 MA Align',   funnel['f3']),
                ('F4 vs Low',     funnel['f4']),
                ('F5 Dip',        funnel['f5']),
                ('F6 Clean',      funnel['f6']),
                ('Vol+Breakout',  funnel['vol_bk']),
            ]
            for label, count in funnel_labels:
                pct_val = count / max(funnel['total'], 1) * 100 if funnel['total'] > 0 else 0
                pct_str = f'{pct_val:.0f}%'
                fill_color = '#4F7BFF' if label not in ('Vol+Breakout',) else '#00D480'
                st.markdown(
                    f'<div class="funnel-bar">'
                    f'  <div class="funnel-fill" style="width:{pct_val:.1f}%;background:{fill_color};"></div>'
                    f'  <div style="display:flex;justify-content:space-between;align-items:center;">'
                    f'    <span class="funnel-label">{label}</span>'
                    f'    <span>'
                    f'      <span class="funnel-count">{count:,}</span>'
                    f'      &nbsp;<span class="funnel-pct">({pct_str})</span>'
                    f'    </span>'
                    f'  </div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            st.markdown("<div style='margin-top:10px'></div>", unsafe_allow_html=True)
            with st.expander("🔍 What does each filter check?"):
                st.markdown("""
**F1 — Trend is bullish** (SMA150 > EMA220): The 150-day average price is above the 220-day average — the stock is in a long-term uptrend.

**F2 — Price above short-term average** (Close > SMA50): Yesterday's price was above its 50-day average — the stock has short-term strength.

**F3 — Moving averages are stacked** (SMA50 > SMA150): The short-term average is above the medium-term average — all trends are pointing up.

**F4 — Not too close to its yearly low** (Price > 1.25× 52W Low): The stock is at least 25% above its lowest point this year — no dead-cat bounces.

**F5 — Had a shakeout dip** (dipped below EMA220 in last 90 days): The stock recently pulled back below its 220-day average and then recovered — this shakeout removes weak holders.

**F6 — Chart is clean** (Choppiness < 61.8): The stock is trending, not just moving sideways randomly.

**Volume confirmation** (1.5× 50-day average): Today's trading volume must be at least 1.5× the 50-day average, confirming real buying interest on the breakout day.
                """)

        # ════════════════════════════════════════════════════════════════════════
        #  DETAIL PANEL  — shown when a row is selected
        # ════════════════════════════════════════════════════════════════════════
        sel = st.session_state.get('selected_ticker')
        if sel:
            st.markdown('<hr style="margin:28px 0 4px 0;border-color:#1e2235;">', unsafe_allow_html=True)

            hdr_col, btn_col = st.columns([9, 1])
            with hdr_col:
                st.markdown(
                    f'<div class="sec-hdr" style="margin-top:8px;">Stock Detail — {sel}</div>',
                    unsafe_allow_html=True,
                )
            with btn_col:
                if st.button('✕ Close', key='close_detail', width='stretch'):
                    st.session_state['selected_ticker'] = None
                    st.rerun()

            _render_stock_detail(sel, sigs, trades_df)

        # ── Backtest equity curve ──────────────────────────────────────────────
        st.markdown('<hr style="margin:28px 0 4px 0;border-color:#1e2235;">', unsafe_allow_html=True)
        st.markdown('<div class="sec-hdr">Backtest Performance</div>', unsafe_allow_html=True)
        st.markdown("""
        <div style="font-size:12px;color:#5a6480;margin-bottom:8px;">
          Portfolio return % over time from running this strategy on historical data.
          Run <code>momentum_edge_backtest.py</code> to update.
        </div>""", unsafe_allow_html=True)

        bt_c1, bt_c2, bt_c3, bt_c4, bt_c5 = st.columns(5)
        if equity_df is not None and 'Equity' in equity_df.columns:
            eq      = equity_df['Equity']
            initial = eq.iloc[0]
            final   = eq.iloc[-1]
            total_r = (final / initial - 1) * 100
            n_years = len(eq) / 252
            cagr    = ((final / initial) ** (1 / n_years) - 1) * 100 if n_years > 0 else 0
            roll_max = eq.cummax()
            max_dd  = ((eq - roll_max) / roll_max * 100).min()
            with bt_c1:
                st.metric('CAGR', f'{cagr:+.1f}%')
            with bt_c2:
                st.metric('Total Return', f'{total_r:+.1f}%')
            with bt_c3:
                st.metric('Max Drawdown', f'{max_dd:.1f}%')
            if trades_df is not None and len(trades_df) > 0:
                wr = (trades_df['Result'] == 'Win').mean() * 100 if 'Result' in trades_df.columns else 0
                with bt_c4:
                    st.metric('Win Rate', f'{wr:.0f}%')
                with bt_c5:
                    st.metric('Trades', len(trades_df))

        st.plotly_chart(_chart_equity(equity_df), width='stretch')

        # ── Glossary ───────────────────────────────────────────────────────────
        st.markdown("<div style='margin-top:8px'></div>", unsafe_allow_html=True)
        with st.expander("📖 What do these terms mean? — Plain-English Glossary"):
            st.markdown("""
**EMA 220 (Exponential Moving Average)** — The 220-day weighted average price, with more weight on recent prices.
Think of it as the stock's "long-term home base." Stocks above their EMA 220 are in a long-term uptrend.

**SMA 50 / SMA 150 (Simple Moving Average)** — The average closing price over the last 50 or 150 trading days (about 2.5 and 7.5 months).
When SMA50 > SMA150 > EMA220, all timeframes are pointing up — a "stacked" bullish setup.

**52-Week High / Low** — The highest and lowest price the stock has traded at in the past 52 weeks (1 year).
A breakout above the 52-week high is a strong bullish signal.

**ATH (All-Time High)** — The highest price the stock has ever reached. Breaking above the ATH is even stronger than a 52-week high breakout.

**Choppiness Index** — Measures whether a stock is trending or just moving sideways randomly.
Below 61.8 = clean trend (good). Above 61.8 = too choppy to trade reliably (skip it).

**Volume Ratio** — Today's trading volume ÷ the 20-day average volume.
A ratio of 2.0× means today's trading is double the normal level — confirming real buying interest.

**Score /100** — The overall quality score of the breakout setup. Higher is better.
Calculated from: momentum (how much it's gained in 6 months) + proximity to ATH + volume strength + how fast it recovered from its dip.

**Recovery Speed** — How quickly the stock climbed back above its EMA 220 after the shakeout dip.
Fast (≤30 days) is best. Slow (>60 days) suggests weaker demand.

**Stop Loss** — The price at which you should sell to limit your loss. Set at 15% below entry.
If the stock falls here, exit immediately — no second-guessing.

**Dist ATH%** — How far the current price is from the all-time high (or 52-week high).
0% = the stock is AT the breakout level right now. Negative = already broken out above it.

**Mom 6M%** — The stock's price change over the last 6 months. Strong 6-month momentum is a predictor of continued strength.

**Market Regime (Bull / Bear)** — Determined by whether the Nifty 50 index is above or below its own EMA 220.
In a Bear Market regime, no new positions are taken (existing positions follow their own exit rules).
            """)

        # ── Column guide ──────────────────────────────────────────────────────
        with st.expander('📖 How to use this screener — what each column means'):
            st.markdown("""
            | Column | What it means |
            |---|---|
            | **Signal** | Breakout Today = crossing ATH right now · Near Breakout = within 3% · Watch Zone = setup forming |
            | **Action** | BUY NOW = all signals confirmed · WATCH = monitor · FORMING = early stage · BEAR MARKET = regime block |
            | **Score /100** | Quality rank: 40pts momentum + 30pts ATH proximity + 20pts volume + 10pts recovery speed |
            | **Entry Type** | ATH = breaking all-time high (best) · 52W High = breaking 52-week high |
            | **Recovery** | Fast (≤30 days) · Normal (≤60 days) · Slow (≤90 days) from EMA dip to reclaim |
            | **Dist ATH%** | How far current price is from the all-time high. 0% = AT the ATH |
            | **Vol Ratio** | Today's volume ÷ 20-day average. 2.0× = double normal buying activity |
            | **Mom 6M%** | How much the stock gained in the last 6 months. Higher = stronger momentum |
            | **220 EMA (₹)** | The long-term 220-day average. Stock must be above this to qualify |
            | **Stop Loss (₹)** | 15% below entry — exit immediately if price falls here |
            | **Choppiness** | Below 55 = clean trend · 55–62 = borderline · Above 62 = skip |
            """)
            st.markdown("""
            **4 signals must happen in order:**
            1. Stock was near its all-time high
            2. Stock dipped below the 220-day EMA (the "flush")
            3. Stock recovered above the EMA within 90 days
            4. Stock is now breaking to a new ATH/52-week high with volume
            """)

    with tab_bt:
        _render_backtest_report()


if __name__ == '__main__':
    main()
