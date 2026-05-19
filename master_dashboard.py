"""
NSE Strategy Hub — Master Dashboard
Integrates Monthly Rotation, IPO Edge, and Momentum Edge in one unified UI.

Run: streamlit run master_dashboard.py --server.port 8500
"""

import os
import subprocess
import sys
import warnings
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import analytics as core_analytics
from core import data_io as core_data_io
from core import glossary as core_glossary
from core import regime as core_regime
from core import rotation_trades as core_rotation_trades
from core import scorer as core_scorer

warnings.filterwarnings('ignore')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ═══════════════════════════════════════════════════════════════════════════════
#  STRATEGY CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

S_MONTHLY  = 'Monthly Rotation'
S_IPO      = 'IPO Edge'
S_MOMENTUM = 'Momentum Edge'

THEME = {
    S_MONTHLY:  {'color': '#7c9cff', 'bg': 'rgba(124,156,255,0.08)', 'icon': '🔄'},
    S_IPO:      {'color': '#00c853', 'bg': 'rgba(0,200,83,0.08)',    'icon': '🚀'},
    S_MOMENTUM: {'color': '#f9c200', 'bg': 'rgba(249,194,0,0.08)',   'icon': '📈'},
}

IPO_UNIVERSE = {
    'PREMIERENE.NS': 'Premier Energies',    'KROSS.NS':      'Kross Limited',
    'BAJAJHFL.NS':   'Bajaj Housing Finance','MANBA.NS':      'Manba Finance',
    'GARUDA.NS':     'Garuda Construction', 'WAAREEENER.NS': 'Waaree Energies',
    'HYUNDAI.NS':    'Hyundai Motor India', 'SWIGGY.NS':     'Swiggy',
    'SAGILITY.NS':   'Sagility India',      'NTPCGREEN.NS':  'NTPC Green Energy',
    'AFCONS.NS':     'Afcons Infrastructure','MOBIKWIK.NS':  'MobiKwik',
    'DOMS.NS':       'DOMS Industries',     'STALLION.NS':   'Stallion India Fluorochemicals',
    'SEPC.NS':       'SEPC Limited',
}

PLOTLY_BASE = dict(paper_bgcolor='#0e1117', plot_bgcolor='#0e1117',
                   font=dict(color='#c0c0c0', size=12))

# Choppiness constants
CHOPPINESS_P     = 14
CHOPPINESS_THRESH = 61.8

# IPO constants
MIN_IPO_LIQUIDITY_CR = 10.0

# IPO Stage colours
STAGE_COLORS = {
    'Stage 3':  '#00c853',
    'Stage 2':  '#f9c200',
    'Stage 1':  '#7c9cff',
    'In Trade': '#00bfa5',
    'Failed':   '#ff3d3d',
    'Too Early':'#888888',
}
STAGE_ORDER = {
    'Stage 3': 0, 'In Trade': 1, 'Stage 2': 2,
    'Stage 1': 3, 'Too Early': 4, 'Failed': 5,
}


# ═══════════════════════════════════════════════════════════════════════════════
#  PAGE CONFIG + CSS
# ═══════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title='NSE Strategy Hub',
    page_icon='⬡',
    layout='wide',
    initial_sidebar_state='expanded',
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

/* ── Global ── */
html, body, [data-testid="stApp"] {
    background: #080c14 !important;
    color: #e4e8f0 !important;
    font-family: 'Inter', 'Segoe UI', sans-serif !important;
}
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #080c14 0%, #0b0f1c 100%) !important;
    border-right: 1px solid #1a2035 !important;
}
[data-testid="stSidebar"] * { color: #b0b8cc !important; }
[data-testid="stSidebar"] .stRadio label { padding: 6px 0; }
[data-testid="stAppViewContainer"] { background: #080c14 !important; }
.block-container { padding-top: 1.5rem !important; }
div[data-testid="column"] { padding: 4px 5px !important; }

/* ── Strategy hub cards ── */
.hub-card {
    background: linear-gradient(135deg, #0f1528 0%, #131829 100%);
    border-radius: 16px;
    padding: 22px 24px;
    border: 1px solid #1e2640;
    position: relative;
    overflow: hidden;
    height: 100%;
    box-shadow: 0 4px 24px rgba(0,0,0,0.4);
}
.hub-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    border-radius: 16px 16px 0 0;
}
.hub-card .strategy-name {
    font-size: 11px; font-weight: 700; text-transform: uppercase;
    letter-spacing: .10em; margin-bottom: 14px; opacity: 0.75;
}
.hub-card .big-num {
    font-size: 36px; font-weight: 900; line-height: 1;
    letter-spacing: -.02em;
}
.hub-card .plain-label {
    font-size: 11px; color: #6a748a; margin-top: 2px; margin-bottom: 14px;
}
.hub-card .divider { border-top: 1px solid #1e2640; margin: 14px 0; }
.hub-card .row { display: flex; justify-content: space-between; gap: 8px; }
.hub-card .kv-block { flex: 1; }
.hub-card .kv-l { color: #5a6480; font-size: 10px; text-transform: uppercase; letter-spacing:.05em; margin-bottom: 2px; }
.hub-card .kv-v { font-size: 14px; font-weight: 700; }
.hub-card .kv-explain { font-size: 9px; color: #3d4560; margin-top: 1px; }
.hub-card .desc-box {
    background: rgba(255,255,255,0.03); border-radius: 8px;
    padding: 8px 10px; margin-top: 12px; font-size: 11px; color: #6a748a; line-height: 1.6;
}

/* ── Metric pill ── */
.metric-pill {
    background: linear-gradient(135deg, #0f1528 0%, #131829 100%);
    border: 1px solid #1e2640;
    border-radius: 12px;
    padding: 14px 16px;
    text-align: center;
    box-shadow: 0 2px 12px rgba(0,0,0,0.3);
    height: 100%;
}
.metric-pill .label {
    color: #6a748a; font-size: 10px; text-transform: uppercase;
    letter-spacing: .08em; font-weight: 600;
}
.metric-pill .value {
    font-size: 26px; font-weight: 800; margin: 6px 0 4px; letter-spacing: -.01em;
}
.metric-pill .sub   { color: #5a6480; font-size: 10px; line-height: 1.4; }
.metric-pill .explain {
    font-size: 9.5px; color: #3d4a60; margin-top: 5px;
    padding-top: 5px; border-top: 1px solid #1a2035; line-height: 1.4;
}

/* ── Section headers ── */
.sec-hdr {
    font-size: 10px; font-weight: 700; text-transform: uppercase;
    letter-spacing: .12em; color: #4a5470; margin: 0 0 10px 2px;
    display: flex; align-items: center; gap: 8px;
}
.sec-hdr::after {
    content: ''; flex: 1; height: 1px; background: #1a2035;
}

/* ── Page title ── */
.page-title {
    font-size: 28px; font-weight: 900; letter-spacing: -.02em; line-height: 1.1;
}
.page-sub { color: #4a5470; font-size: 13px; margin-top: 4px; }

/* ── Signal badges ── */
.badge {
    display: inline-block; border-radius: 5px;
    padding: 3px 9px; font-size: 11px; font-weight: 700; letter-spacing: .03em;
}
.badge-green  { background: rgba(0,200,83,0.15);  color: #00c853; border: 1px solid rgba(0,200,83,0.3); }
.badge-yellow { background: rgba(249,194,0,0.12);  color: #f9c200; border: 1px solid rgba(249,194,0,0.3); }
.badge-blue   { background: rgba(124,156,255,0.12);color: #7c9cff; border: 1px solid rgba(124,156,255,0.3); }
.badge-red    { background: rgba(255,61,61,0.10);  color: #ff5555; border: 1px solid rgba(255,61,61,0.25); }
.badge-grey   { background: rgba(136,146,164,0.10);color: #8892a4; border: 1px solid rgba(136,146,164,0.2); }

/* ── Term pill (inline definition) ── */
.term-pill {
    display: inline-block; background: rgba(124,156,255,0.08);
    border: 1px solid rgba(124,156,255,0.18); border-radius: 4px;
    padding: 1px 6px; font-size: 10px; color: #7c9cff; font-weight: 600;
    cursor: default;
}

/* ── Explain box (inline callout) ── */
.explain-box {
    background: rgba(255,255,255,0.025);
    border: 1px solid #1e2640;
    border-left: 3px solid #7c9cff;
    border-radius: 0 8px 8px 0;
    padding: 10px 14px;
    margin: 8px 0 12px 0;
    font-size: 12px; color: #8892a4; line-height: 1.7;
}
.explain-box b { color: #b0b8cc; }

/* ── Tip box ── */
.tip-box {
    background: rgba(249,194,0,0.05);
    border: 1px solid rgba(249,194,0,0.2);
    border-radius: 8px;
    padding: 10px 14px;
    margin: 10px 0;
    font-size: 12px; color: #a09060; line-height: 1.7;
}

/* ── Good/Bad verdict box ── */
.verdict-good {
    background: rgba(0,200,83,0.06);
    border: 1px solid rgba(0,200,83,0.2);
    border-radius: 8px; padding: 10px 14px;
    font-size: 12px; color: #5cb87a; line-height: 1.6;
}
.verdict-bad {
    background: rgba(255,61,61,0.06);
    border: 1px solid rgba(255,61,61,0.2);
    border-radius: 8px; padding: 10px 14px;
    font-size: 12px; color: #c86060; line-height: 1.6;
}

/* ── Signal card (home page feed) ── */
.sig-card {
    background: #0f1528;
    border-radius: 10px;
    border: 1px solid #1e2640;
    padding: 10px 14px;
    margin-bottom: 8px;
    transition: border-color .2s;
}

/* ── Step badge ── */
.step-badge {
    display: inline-flex; align-items: center; justify-content: center;
    width: 22px; height: 22px; border-radius: 50%;
    font-size: 11px; font-weight: 800; margin-right: 6px; flex-shrink: 0;
}

/* ── Update banner ── */
.upd-banner {
    background: #0f1528; border: 1px solid #1e2640; border-radius: 10px;
    padding: 10px 16px; font-size: 12px; color: #6a748a;
    display: flex; justify-content: space-between; align-items: center;
}

/* ── Streamlit overrides ── */
[data-testid="stMetric"] { background: #0f1528; border-radius: 10px; padding: 10px; }
.stExpander { background: #0f1528 !important; border: 1px solid #1e2640 !important; border-radius: 10px !important; }
.stExpander summary { color: #8892a4 !important; font-size: 12px !important; }
button[kind="primary"] { border-radius: 8px !important; font-weight: 700 !important; }
button[kind="secondary"] { border-radius: 8px !important; background: #131829 !important; border-color: #1e2640 !important; }
.stAlert { border-radius: 10px !important; }
hr { border-color: #1a2035 !important; }
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  SHARED INDICATOR HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _compute_choppiness(df: pd.DataFrame, period: int = CHOPPINESS_P) -> pd.Series:
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
    """Returns (label, days). label: 'Fast' ≤30, 'Normal' 31-60, 'Slow' >60, 'No Reclaim' -1."""
    n = len(close)
    if n < 10:
        return ('No Reclaim', -1)
    window = close.iloc[max(0, n - lookback):]
    e_window = ema220.iloc[max(0, n - lookback):]
    below = (window < e_window).values
    if not below.any():
        return ('No Reclaim', -1)

    # Find last contiguous block below EMA220
    last_below = int(np.where(below)[0][-1])
    start_idx = last_below
    while start_idx > 0 and below[start_idx - 1]:
        start_idx -= 1

    ep_close = window.iloc[start_idx: last_below + 1]
    if ep_close.empty:
        return ('No Reclaim', -1)
    dip_local = int(ep_close.values.argmin())
    dip_global = start_idx + dip_local

    ep_after_close = window.iloc[dip_global + 1:]
    ep_after_ema   = e_window.iloc[dip_global + 1:]
    reclaim_mask   = (ep_after_close >= ep_after_ema).values
    if not reclaim_mask.any():
        return ('No Reclaim', -1)

    days = int(np.where(reclaim_mask)[0][0]) + 1
    if days <= 30:
        return ('Fast', days)
    if days <= 60:
        return ('Normal', days)
    return ('Slow', days)


def _detect_ipo_stage(df: pd.DataFrame, ipo_day_high: float,
                      breakout_level: float, base_low: float,
                      base_vol_avg: float) -> str:
    close  = df['Close']
    volume = df['Volume']
    ema10  = close.ewm(span=10, adjust=False).mean()

    if len(close) < 5:
        return 'Too Early'

    latest_close = float(close.iloc[-1])
    latest_ema   = float(ema10.iloc[-1])
    latest_vol   = float(volume.iloc[-1])
    vol_confirmed = (base_vol_avg > 0) and (latest_vol >= 1.5 * base_vol_avg)

    r5 = volume.iloc[-5:].replace(0, np.nan).mean()
    lw = volume.iloc[:5].replace(0, np.nan).mean()
    vol_contracting = (not pd.isna(r5)) and (not pd.isna(lw)) and (float(r5) < float(lw))

    if latest_close < base_low * 0.90:
        return 'Failed'
    if latest_close > breakout_level and vol_confirmed:
        return 'Stage 3'
    if latest_close > latest_ema and latest_close <= breakout_level:
        return 'Stage 2'
    if latest_close <= ipo_day_high and vol_contracting:
        return 'Stage 1'
    return 'Stage 1'


def _detect_ipo_setup_type(base_slice: pd.DataFrame, ipo_hi: float,
                           base_hi: float, base_lo: float,
                           sma10: pd.Series) -> str:
    """Classify the IPO base as FLAG, U-TURN, EARLY BOOM, or STANDARD."""
    if base_slice.empty or len(base_slice) < 5:
        return 'STANDARD'

    closes = base_slice['Close']
    vols   = base_slice['Volume'].replace(0, np.nan).dropna()

    # EARLY BOOM: first week above IPO high, then holds SMA10
    first_week_high = closes.iloc[:5].max() if len(closes) >= 5 else 0
    if first_week_high > ipo_hi and len(sma10.dropna()) >= 5:
        sma_slice    = sma10.reindex(base_slice.index).dropna()
        recent_c     = closes.iloc[-5:] if len(closes) >= 5 else closes
        recent_sma   = sma_slice.iloc[-5:] if len(sma_slice) >= 5 else sma_slice
        if len(recent_sma) > 0 and (recent_c >= recent_sma).mean() >= 0.6:
            return 'EARLY BOOM'

    # FLAG: tight range + declining volume
    if base_hi > 0 and (base_hi - base_lo) / base_hi < 0.15 and len(vols) >= 10:
        fh = vols.iloc[:len(vols)//2].mean()
        sh = vols.iloc[len(vols)//2:].mean()
        if sh < fh:
            return 'FLAG'

    # U-TURN: initial decline then higher lows
    if len(closes) >= 10:
        mid = len(closes) // 2
        first_low    = closes.iloc[:mid].min()
        second_low   = closes.iloc[mid:].min()
        first_trend  = closes.iloc[:mid].iloc[-1] < closes.iloc[:mid].iloc[0]
        if first_trend and second_low > first_low:
            return 'U-TURN'

    return 'STANDARD'


def _load_promoter_quality() -> dict:
    path = Path(BASE_DIR) / 'ipo_promoter_quality.csv'
    if not path.exists():
        return {}
    try:
        df = pd.read_csv(path)
        return {
            row['Symbol'].strip(): row['PromoterBacked'].strip().upper()
            for _, row in df.iterrows()
        }
    except Exception:
        return {}


@st.cache_data(ttl=3600)
def _get_pe(ticker_ns: str) -> float | None:
    try:
        import yfinance as yf
        info = yf.Ticker(ticker_ns).info
        pe   = info.get('trailingPE') or info.get('forwardPE')
        return float(pe) if pe else None
    except Exception:
        return None


def _score_bar(score: float, max_score: int = 10) -> str:
    filled = min(max_score, max(0, round(score)))
    empty  = max_score - filled
    bar    = '█' * filled + '░' * empty
    return f'{bar}  {score:.1f}/{max_score}'


# ═══════════════════════════════════════════════════════════════════════════════
#  DATA LOADERS
# ═══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=3600)
def load_monthly():
    """Load Monthly Rotation outputs."""
    out = {}

    p_rank = Path(BASE_DIR) / 'live_rankings.csv'
    if p_rank.exists():
        try:
            df = pd.read_csv(p_rank)
            if not df.empty:
                out['rankings'] = df
        except Exception:
            pass

    p_bt = Path(BASE_DIR) / 'backtest_results.csv'
    if p_bt.exists():
        try:
            df = pd.read_csv(p_bt, parse_dates=['Date'])
            if not df.empty and 'Date' in df.columns:
                df.set_index('Date', inplace=True)
                out['equity'] = df
        except Exception:
            pass

    p_reb = Path(BASE_DIR) / 'rebalance_log.csv'
    if p_reb.exists():
        try:
            df = pd.read_csv(p_reb, parse_dates=['Date'])
            if not df.empty:
                out['rebalance'] = df
        except Exception:
            pass

    return out


@st.cache_data(ttl=3600)
def load_ipo():
    """Load IPO Edge outputs and compute live signals."""
    out = {}

    p_eq = Path(BASE_DIR) / 'ipo_edge_equity.csv'
    if p_eq.exists():
        try:
            df = pd.read_csv(p_eq, parse_dates=['Date'])
            if not df.empty and 'Date' in df.columns:
                df.set_index('Date', inplace=True)
                out['equity'] = df
        except Exception:
            pass

    p_tr = Path(BASE_DIR) / 'ipo_edge_trades.csv'
    if p_tr.exists():
        try:
            df_tr = pd.read_csv(p_tr)
            if not df_tr.empty:
                out['trades'] = df_tr
        except Exception:
            pass

    out['signals'] = _compute_ipo_signals()
    return out


@st.cache_data(ttl=3600)
def load_momentum():
    """Load Momentum Edge outputs and compute live signals."""
    out = {}

    p_eq = Path(BASE_DIR) / 'momentum_edge_equity.csv'
    if p_eq.exists():
        try:
            df = pd.read_csv(p_eq, parse_dates=['Date'])
            if not df.empty and 'Date' in df.columns:
                df.set_index('Date', inplace=True)
                out['equity'] = df
        except Exception:
            pass

    p_tr = Path(BASE_DIR) / 'momentum_edge_trades.csv'
    if p_tr.exists():
        try:
            df_tr = pd.read_csv(p_tr)
            if not df_tr.empty:
                out['trades'] = df_tr
        except Exception:
            pass

    out['signals'] = _compute_momentum_signals()
    return out


# ═══════════════════════════════════════════════════════════════════════════════
#  LIVE SIGNAL COMPUTATION
# ═══════════════════════════════════════════════════════════════════════════════

def _load_ohlcv_csv(path: Path) -> pd.DataFrame | None:
    try:
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        df.index = pd.to_datetime(df.index)
        df.sort_index(inplace=True)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        needed = [c for c in ['Open', 'High', 'Low', 'Close', 'Volume'] if c in df.columns]
        return df[needed] if len(needed) == 5 else None
    except Exception:
        return None


def _compute_ipo_signals() -> pd.DataFrame:
    """Detect IPO Edge live signals with quality filters and scoring."""
    folder    = Path(BASE_DIR) / 'ipo_data'
    skip, base_w = 3, 40
    min_days  = skip + base_w
    today     = datetime.now().date()
    rows      = []

    promoter_quality = _load_promoter_quality()

    # Determine open tickers from backtest trades
    open_tickers: set[str] = set()
    p_tr = Path(BASE_DIR) / 'ipo_edge_trades.csv'
    if p_tr.exists():
        try:
            t_df = pd.read_csv(p_tr)
            if 'Status' in t_df.columns and 'Ticker' in t_df.columns:
                open_tickers = set(
                    t_df[t_df['Status'] == 'Open']['Ticker']
                    .str.replace('.NS', '', regex=False)
                    .tolist()
                )
        except Exception:
            pass

    for ticker, company in IPO_UNIVERSE.items():
        sym   = ticker.replace('.NS', '')
        path  = folder / f'{ticker}.csv'
        df    = _load_ohlcv_csv(path)
        if df is None or len(df) < min_days:
            continue

        listing_date = df.index[0].date()
        age_days     = (today - listing_date).days
        if age_days > 365:
            continue

        # ── IPO day stats ──────────────────────────────────────────────────
        ipo_day_close = float(df['Close'].iloc[0])
        ipo_day_vol   = float(df['Volume'].iloc[0])
        ipo_day_value_cr = round(ipo_day_close * ipo_day_vol / 1e7, 2)
        liquidity_ok   = ipo_day_value_cr >= MIN_IPO_LIQUIDITY_CR
        liquidity_str  = 'Liquid ✅' if liquidity_ok else 'Low Liq ❌'

        # ── Base window ─────────────────────────────────────────────────────
        base_df    = df.iloc[skip: skip + base_w]
        vol_series = base_df['Volume'].replace(0, pd.NA).dropna()
        base_vol_avg = float(vol_series.mean()) if len(vol_series) > 0 else 0
        ipo_hi   = float(df['High'].iloc[0])
        base_hi  = float(base_df['High'].max())
        base_lo  = float(base_df['Low'].min())
        bk_level = max(base_hi, ipo_hi)

        close      = df['Close']
        volume     = df['Volume']
        ema10      = close.ewm(span=10, adjust=False).mean()
        # FIX 3: use rolling 20-day volume average (not static base window avg)
        vol_20_series = volume.rolling(20).mean()
        vol_avg_20    = float(vol_20_series.iloc[-1]) if not pd.isna(vol_20_series.iloc[-1]) else (base_vol_avg or 1.0)
        latest_close = float(close.iloc[-1])
        latest_vol   = float(volume.iloc[-1])
        vol_ratio    = (latest_vol / vol_avg_20) if vol_avg_20 > 0 else 0
        vs_bk_pct    = (latest_close / bk_level - 1) * 100

        # ── Signal label ────────────────────────────────────────────────────
        if latest_close > bk_level and vol_ratio >= 1.5 and latest_close > float(ema10.iloc[-1]):
            signal = 'Live Breakout'
        elif latest_close > bk_level * 0.97 or vol_ratio >= 1.2:
            signal = 'Watch Zone'
        elif latest_close < base_lo:
            signal = 'Avoid'
        else:
            signal = 'Forming Base'

        # ── Setup type detection ─────────────────────────────────────────────
        base_slice = df.iloc[skip: skip + base_w]
        sma10      = close.rolling(10).mean()
        setup_type = _detect_ipo_setup_type(base_slice, ipo_hi, base_hi, base_lo, sma10)

        # ── 3-Stage pattern ─────────────────────────────────────────────────
        if sym in open_tickers:
            stage = 'In Trade'
        else:
            stage = _detect_ipo_stage(df, ipo_hi, bk_level, base_lo, base_vol_avg)

        stage_label = stage  # direct use in table

        # ── Promoter quality ───────────────────────────────────────────────
        pq_raw = promoter_quality.get(sym, 'UNKNOWN')
        if pq_raw == 'YES':
            promoter_str = 'YES ✅'
        elif pq_raw == 'NO':
            promoter_str = 'NO ❌'
        else:
            promoter_str = 'Unknown ⚪'

        # ── Listing PE ──────────────────────────────────────────────────────
        pe_val = _get_pe(ticker)
        if pe_val is None:
            pe_str = '—'
        elif pe_val < 20:
            pe_str = f'{pe_val:.1f} 🟢'
        elif pe_val <= 40:
            pe_str = f'{pe_val:.1f} 🟡'
        else:
            pe_str = f'{pe_val:.1f} 🟠'

        # ── Signal Quality Score (max 10) ───────────────────────────────────
        score = 0.0
        # Stage (max 3)
        stage_pts = {'Stage 3': 3, 'In Trade': 3, 'Stage 2': 2, 'Stage 1': 1,
                     'Too Early': 0, 'Failed': 0}
        score += stage_pts.get(stage, 0)
        # Liquidity (max 2)
        if liquidity_ok:
            score += 2
        # Promoter (max 2)
        if pq_raw == 'YES':
            score += 2
        elif pq_raw == 'UNKNOWN':
            score += 1
        # PE (max 1)
        if pe_val is not None:
            if pe_val < 20:
                score += 1.0
            elif pe_val <= 40:
                score += 0.5
        # Volume confirmed (max 2)
        if vol_ratio >= 1.5:
            score += 2

        rows.append({
            'Ticker':      sym,
            'Company':     company,
            'Signal':      signal,
            'Stage':       stage_label,
            'Setup':       setup_type,
            'Close':       round(latest_close, 2),
            'Bk Level':   round(bk_level, 2),
            'vs Bk%':     round(vs_bk_pct, 2),
            'Vol Ratio':  round(vol_ratio, 2),
            'IPO Day Val':ipo_day_value_cr,
            'Liquidity':  liquidity_str,
            'Promoter':   promoter_str,
            'Listing PE': pe_str,
            'Age (d)':    age_days,
            'Score':      round(score, 1),
            '_stage_rank':STAGE_ORDER.get(stage, 9),
            '_score':     score,
        })

    if not rows:
        return pd.DataFrame()

    df_out = pd.DataFrame(rows)
    df_out.sort_values(['_score', '_stage_rank'], ascending=[False, True], inplace=True)
    return df_out.drop(columns=['_stage_rank', '_score']).reset_index(drop=True)


def _render_me_detail(ticker: str, trades: pd.DataFrame | None) -> None:
    """Candlestick + SMA50/EMA220 + 52W lines + trade markers for one ticker.

    Looks up OHLCV from data/nse_bse/<ticker>.csv first, falls back to
    momentum_edge_data/. Renders 252-bar window inline.
    """
    full = Path(BASE_DIR) / 'data' / 'nse_bse' / f'{ticker}.NS.csv'
    legacy = Path(BASE_DIR) / 'momentum_edge_data' / f'{ticker}.NS.csv'
    raw = Path(BASE_DIR) / 'data' / 'nse_bse' / f'{ticker}.csv'  # may already include .NS suffix
    path = next((p for p in (full, legacy, raw) if p.exists()), None)
    if path is None:
        st.info(f'No OHLCV file found for {ticker}.')
        return

    df = _load_ohlcv_csv(path)
    if df is None or len(df) < 60:
        st.info('Not enough bars to chart this ticker.')
        return

    close = df['Close']
    sma50  = close.rolling(50).mean()
    sma150 = close.rolling(150).mean()
    ema220 = close.ewm(span=220, adjust=False).mean()
    high52 = float(close.rolling(252).max().iloc[-1])
    low52  = float(close.rolling(252).min().iloc[-1])

    df_w = df.tail(252).copy()
    idx = df_w.index

    fig = go.Figure()
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
    fig.add_trace(go.Scatter(x=idx, y=sma50.loc[idx], name='SMA 50',
                             line=dict(color='#4c9fff', width=1.5)))
    fig.add_trace(go.Scatter(x=idx, y=sma150.loc[idx], name='SMA 150',
                             line=dict(color='#ff9800', width=1.5)))
    fig.add_trace(go.Scatter(x=idx, y=ema220.loc[idx], name='EMA 220',
                             line=dict(color='#ff5252', width=2, dash='dot')))
    fig.add_hline(y=high52, line_color='rgba(0,200,83,0.6)', line_dash='dash',
                  annotation_text=f'52W High ₹{high52:,.0f}',
                  annotation_position='bottom right',
                  annotation_font=dict(color='#00c853', size=10))
    fig.add_hline(y=low52, line_color='rgba(255,61,61,0.6)', line_dash='dash',
                  annotation_text=f'52W Low ₹{low52:,.0f}',
                  annotation_position='top right',
                  annotation_font=dict(color='#ff5252', size=10))

    # Past trade markers
    if trades is not None and not trades.empty and 'Ticker' in trades.columns:
        ticker_full = ticker if ticker.endswith('.NS') else f'{ticker}.NS'
        t = trades[trades['Ticker'].astype(str).str.replace('.NS', '', regex=False) == ticker].copy()
        if not t.empty:
            ed = pd.to_datetime(t.get('Entry_Date'), errors='coerce')
            xd = pd.to_datetime(t.get('Exit_Date'),  errors='coerce')
            ep = pd.to_numeric(t.get('Entry_Price'), errors='coerce')
            xp = pd.to_numeric(t.get('Exit_Price'),  errors='coerce')
            window_start = pd.Timestamp(idx[0])
            em = (ed >= window_start)
            xm = (xd >= window_start)
            if em.any():
                fig.add_trace(go.Scatter(
                    x=ed[em], y=ep[em], mode='markers', name='BUY',
                    marker=dict(symbol='triangle-up', size=14, color='#00e676',
                                line=dict(color='#fff', width=1)),
                    hovertemplate='BUY  ₹%{y:,.2f}<br>%{x}<extra></extra>',
                ))
            if xm.any():
                fig.add_trace(go.Scatter(
                    x=xd[xm], y=xp[xm], mode='markers', name='EXIT',
                    marker=dict(symbol='triangle-down', size=14, color='#ff1744',
                                line=dict(color='#fff', width=1)),
                    hovertemplate='EXIT  ₹%{y:,.2f}<br>%{x}<extra></extra>',
                ))

    fig.update_layout(
        height=480,
        paper_bgcolor='#0e1117', plot_bgcolor='#12172a',
        xaxis=dict(gridcolor='#1e2235', rangeslider=dict(visible=False),
                   tickformat='%d %b %y', tickfont=dict(size=10)),
        yaxis=dict(gridcolor='#1e2235', tickprefix='₹', tickformat=',.0f',
                   tickfont=dict(size=10)),
        legend=dict(orientation='h', y=1.02, x=0,
                    font=dict(size=11, color='#8892a4'),
                    bgcolor='rgba(0,0,0,0)'),
        font=dict(color='#e0e0e0', family='Inter'),
        margin=dict(l=70, r=30, t=50, b=30),
        hovermode='x unified',
    )
    st.plotly_chart(fig, width='stretch')

    # Mini stats bar
    close_now  = float(close.iloc[-1])
    close_prev = float(close.iloc[-2]) if len(close) >= 2 else close_now
    pct_chg    = (close_now / close_prev - 1) * 100
    vol_avg30  = float(df['Volume'].iloc[-30:].mean())
    vol_str    = (f'{vol_avg30 / 1_000_000:.1f}M' if vol_avg30 >= 1_000_000
                  else f'{vol_avg30 / 1_000:.0f}K')

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: st.metric('Current Price', f'₹{close_now:,.2f}')
    with c2: st.metric("Today's Change", f'{pct_chg:+.2f}%', delta=f'{pct_chg:+.2f}%')
    with c3: st.metric('52W High', f'₹{high52:,.2f}')
    with c4: st.metric('52W Low',  f'₹{low52:,.2f}')
    with c5: st.metric('Avg Vol (30d)', vol_str)


def _compute_momentum_signals() -> pd.DataFrame:
    """Detect Momentum Edge live signals — SPEC-ALIGNED with momentum_edge_dashboard.py.

    F1-F4 use day-T values (per spec); F5/F6 use T-1; breakout-ref uses T-1 (resistance =
    yesterday's 252-day rolling max). Volume check uses 50-day average per spec.
    State machine excludes stocks whose current breakout already fired (POST_BREAKOUT).
    Regime gate (3-condition) is applied — entries in Bear regime get BEAR MARKET action.
    """
    full_folder   = Path(BASE_DIR) / 'data' / 'nse_bse'
    legacy_folder = Path(BASE_DIR) / 'momentum_edge_data'
    folder = full_folder if full_folder.exists() and any(full_folder.glob('*.csv')) else legacy_folder
    sym_file = Path(BASE_DIR) / 'momentum_edge_symbols.csv'
    if not folder.exists():
        return pd.DataFrame()

    universe: dict[str, str] = {}
    if sym_file.exists():
        try:
            s = pd.read_csv(sym_file)
            universe = dict(zip(s['Ticker'].str.strip(), s['Company'].str.strip()))
        except Exception:
            pass

    # ── Regime gate (3-condition on Nifty) ─────────────────────────────────
    bench = _benchmark_first('data/nse_bse', 'data')
    is_bull_today = True
    if bench is not None and len(bench) >= 200:
        _sma50  = bench.rolling(50).mean()
        _sma200 = bench.rolling(200).mean()
        _high52 = bench.rolling(252).max()
        _b = bench.iloc[-1]
        is_bull_today = bool(
            _b > _sma200.iloc[-1]
            and _sma50.iloc[-1] > _sma200.iloc[-1]
            and _b >= 0.90 * _high52.iloc[-1]
        )

    # Match standalone constants
    SMA50_P, SMA150_P, EMA220_P = 50, 150, 220
    HIGH52_P, LOW52_P           = 252, 252
    VOL_LOOKBACK                = 50
    VOL_MULTIPLIER              = 1.5
    DIP_LB                      = 90
    MOM_P                       = 126
    MIN_PRICE_VS_LOW            = 1.25
    MIN_BARS, MIN_CLOSE_PRICE   = 252, 50.0
    MIN_AVG_VOL                 = 100_000
    NEAR_BK_PCT                 = 0.02

    rows       = []
    skip_stems = {'NIFTYBEES.NS', 'me_summary', '^NSEI'}

    for csv_path in sorted(folder.glob('*.csv')):
        if csv_path.stem in skip_stems:
            continue
        ticker  = csv_path.stem
        company = universe.get(ticker, ticker.replace('.NS', ''))
        df      = _load_ohlcv_csv(csv_path)
        if df is None or len(df) < MIN_BARS:
            continue
        if df['Close'].iloc[-1] < MIN_CLOSE_PRICE:
            continue
        if df['Volume'].iloc[-30:].mean() < MIN_AVG_VOL:
            continue

        close  = df['Close']
        volume = df['Volume']

        sma50      = close.rolling(SMA50_P).mean()
        sma150     = close.rolling(SMA150_P).mean()
        ema220     = close.ewm(span=EMA220_P, adjust=False).mean()
        high52     = close.rolling(HIGH52_P).max()
        low52      = close.rolling(LOW52_P).min()
        vol50      = volume.rolling(VOL_LOOKBACK).mean()
        resistance = close.shift(1).rolling(HIGH52_P).max()   # yesterday's 252-day max
        ath        = close.expanding().max()
        dip_flag   = (close < ema220).astype(int)
        had_dip    = dip_flag.rolling(DIP_LB).max().astype(bool)
        mom_6m     = close.pct_change(MOM_P)

        # 1-2-3 state machine (vectorized, mirrors standalone _compute_cycle_state)
        c_arr = close.values.astype(float)
        e_arr = ema220.values.astype(float)
        r_arr = resistance.values.astype(float)
        n_arr = len(c_arr)
        cycle_state = 'NORMAL'
        if n_arr >= 2:
            valid = ~(np.isnan(c_arr) | np.isnan(e_arr))
            below_ema = valid & (c_arr < e_arr)
            above_res = np.zeros(n_arr, dtype=bool)
            above_res[1:] = (
                ~np.isnan(r_arr[1:])
                & (c_arr[1:] > r_arr[1:])
                & (c_arr[:-1] <= r_arr[1:])
            )
            for i in range(1, n_arr):
                if not valid[i]:
                    continue
                if below_ema[i]:
                    cycle_state = 'FLUSHED'
                elif cycle_state == 'FLUSHED' and above_res[i]:
                    cycle_state = 'POST_BREAKOUT'

        # Skip stocks where this cycle's breakout already fired
        if cycle_state == 'POST_BREAKOUT':
            continue

        def _s(series):
            return series.iloc[-2] if len(series) >= 2 else np.nan

        close_s    = _s(close)
        vol50_s    = _s(vol50)
        had_dip_s  = bool(_s(had_dip))
        ath_prev   = _s(ath)
        high52_s   = _s(high52)
        mom_s      = _s(mom_6m)
        res_today  = float(resistance.iloc[-1]) if not pd.isna(resistance.iloc[-1]) else np.nan

        close_now  = float(close.iloc[-1])
        ema220_now = float(ema220.iloc[-1])
        sma50_now  = float(sma50.iloc[-1])
        sma150_now = float(sma150.iloc[-1])
        low52_now  = float(low52.iloc[-1])
        vol_today  = float(volume.iloc[-1])

        if any(pd.isna(v) for v in (close_now, ema220_now, sma50_now, sma150_now, low52_now)):
            continue

        # ── F1-F4 on day T, F5 / F6 on T-1 ────────────────────────────────
        if not (sma150_now > ema220_now): continue
        if not (close_now  > sma50_now):  continue
        if not (sma50_now  > sma150_now): continue
        if not (close_now  >= MIN_PRICE_VS_LOW * low52_now): continue
        if not had_dip_s: continue

        chop_series = _compute_choppiness(df, CHOPPINESS_P)
        chop_val    = float(chop_series.iloc[-2]) if len(chop_series) >= 2 and not pd.isna(chop_series.iloc[-2]) else float('nan')
        if not pd.isna(chop_val) and chop_val > CHOPPINESS_THRESH:
            continue

        # ── Volume + breakout (vol50 per spec) ────────────────────────────
        vol_ok = (
            not pd.isna(vol50_s) and vol50_s > 0
            and not pd.isna(vol_today)
            and vol_today >= VOL_MULTIPLIER * vol50_s
        )

        bk_ref = res_today if not pd.isna(res_today) else high52_s
        is_breakout = (
            not pd.isna(res_today)
            and close_now > res_today
            and close_s <= res_today
            and close_now > ema220_now
        )
        dist_to_res = (res_today - close_now) / res_today if (not pd.isna(res_today) and res_today > 0) else 1.0
        is_near_bk = (
            (not is_breakout)
            and (not pd.isna(res_today))
            and 0 < dist_to_res <= NEAR_BK_PCT
            and vol_ok
        )

        if is_breakout and vol_ok:
            signal = 'Breakout Today'
        elif is_near_bk:
            signal = 'Near Breakout'
        else:
            signal = 'Watch Zone'

        # ── Entry type, recovery, score ───────────────────────────────────
        entry_type = 'ATH' if (not pd.isna(ath_prev) and close_now > float(ath_prev)) else '52W High'

        rec_label, rec_days = _compute_recovery_speed(close, ema220, lookback=90)
        rec_str = {'Fast': 'Fast 🟢', 'Normal': 'Normal 🟡', 'Slow': 'Slow 🟠'}.get(rec_label, '— ⚪')

        vol_ratio = (vol_today / vol50_s) if (not pd.isna(vol50_s) and vol50_s > 0) else 0
        ath_prox  = min((close_now / bk_ref), 1.0) if (bk_ref and bk_ref > 0) else 0
        mom_pct   = float(mom_s) if not pd.isna(mom_s) else 0
        score = round(ath_prox * 30 + min(vol_ratio * 10, 20) + min(mom_pct * 100, 20), 1)

        dist_ath = ((close_now / float(bk_ref)) - 1) * 100 if bk_ref and bk_ref > 0 else 0

        rows.append({
            'Ticker':       ticker.replace('.NS', ''),
            'Company':      company,
            'Signal':       signal,
            'Close':        round(close_now, 2),
            'ATH (₹)':      round(float(ath.iloc[-1]), 2),
            'Dist ATH%':    round((close_now / float(ath.iloc[-1]) - 1) * 100, 2),
            'Entry Type':   entry_type,
            'Chart Qual':   'Clean ✅' if (not pd.isna(chop_val) and chop_val < CHOPPINESS_THRESH) else 'Choppy ❌',
            'Choppiness':   round(chop_val, 1) if not pd.isna(chop_val) else '—',
            'Recovery':     rec_str,
            '220 EMA':      round(ema220_now, 2),
            '52W High':     round(float(bk_ref), 2) if bk_ref else None,
            'vs High%':     round(dist_ath, 2),
            'Vol Ratio':    round(vol_ratio, 2),
            'Score':        score,
            '_score':       score,
            '_is_bull':     is_bull_today,
        })

    if not rows:
        return pd.DataFrame()

    df_out = pd.DataFrame(rows)
    sig_rank = {'Breakout Today': 0, 'Near Breakout': 1, 'Watch Zone': 2}
    df_out['_rank'] = df_out['Signal'].map(sig_rank).fillna(3)
    df_out = df_out.sort_values(['_rank', '_score'], ascending=[True, False])
    return df_out.drop(columns=['_rank', '_score', '_is_bull']).reset_index(drop=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _hex_rgba(hex_color: str, alpha: float = 0.07) -> str:
    """Convert '#rrggbb' to 'rgba(r,g,b,alpha)' for Plotly fill colors."""
    h = hex_color.lstrip('#')
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f'rgba({r},{g},{b},{alpha})'


def pill(label, value, sub='', color='#e0e0e0', explain=''):
    exp_html = (f'<div class="explain">{explain}</div>' if explain else '')
    return (f'<div class="metric-pill">'
            f'<div class="label">{label}</div>'
            f'<div class="value" style="color:{color}">{value}</div>'
            f'<div class="sub">{sub}</div>'
            f'{exp_html}</div>')


def _explain_box(text: str, color: str = '#7c9cff') -> str:
    """Inline blue callout explaining a metric or concept."""
    return (f'<div class="explain-box" style="border-left-color:{color}">'
            f'{text}</div>')


def _tip_box(text: str) -> str:
    return f'<div class="tip-box">💡 {text}</div>'


def _term(word: str) -> str:
    """Inline term badge — looks like a tag."""
    return f'<span class="term-pill">{word}</span>'


def _glossary_expander():
    """Full glossary in a collapsible expander — shown at bottom of every page."""
    with st.expander('📖  Glossary — What do these words mean?', expanded=False):
        st.markdown("""
<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px 24px;font-size:12px;line-height:1.7;">

<div>
<b style="color:#7c9cff">CAGR</b> — <i>Compounded Annual Growth Rate</i><br>
If you invested ₹1 lakh and it became ₹1.5 lakh in 3 years, your CAGR is ~14%.
It tells you the "average yearly return" smoothed out over time.
</div>

<div>
<b style="color:#7c9cff">Max Drawdown</b> — <i>Worst fall from peak</i><br>
If your portfolio hit ₹1.5 lakh then fell to ₹1.1 lakh, drawdown is -27%.
Smaller is safer — a good strategy limits this below -20%.
</div>

<div>
<b style="color:#7c9cff">Win Rate</b> — <i>How often trades make money</i><br>
60% win rate = 6 out of every 10 trades were profitable.
Even 45% win rate can be great if wins are bigger than losses.
</div>

<div>
<b style="color:#7c9cff">Sharpe Ratio</b> — <i>Return per unit of risk</i><br>
Above 1.0 = good. Above 2.0 = excellent.
It measures if you are being rewarded enough for the risk you take.
</div>

<div>
<b style="color:#7c9cff">RS Score / Momentum Score</b> — <i>How strong the stock is vs others</i><br>
Higher score = stock is outperforming the market. We buy the top 5 strongest.
</div>

<div>
<b style="color:#7c9cff">EMA (Exponential Moving Average)</b> — <i>Price trend line</i><br>
220 EMA = average price of the last 220 days, giving more weight to recent days.
If price is above EMA, the stock is in an uptrend.
</div>

<div>
<b style="color:#7c9cff">SMA (Simple Moving Average)</b> — <i>Basic average price line</i><br>
50 SMA = average of last 50 days (equal weight). Used to confirm trend direction.
</div>

<div>
<b style="color:#7c9cff">ATH (All-Time High)</b> — <i>Highest price ever recorded</i><br>
Breaking above ATH = very bullish — no one is sitting at a loss, so no selling pressure.
</div>

<div>
<b style="color:#7c9cff">Breakout</b> — <i>Price crosses a key resistance level</i><br>
Like breaking out of a tight box. Strong volume confirms it's real, not a fake move.
</div>

<div>
<b style="color:#7c9cff">Choppiness Index</b> — <i>Is the chart trending or sideways?</i><br>
Below 61.8 = trending (good to trade). Above 61.8 = sideways/noisy (avoid).
</div>

<div>
<b style="color:#7c9cff">Hard Stop</b> — <i>Auto-exit at a fixed loss level</i><br>
If you buy at ₹100 and set a 15% hard stop, you exit at ₹85 — no matter what.
Protects you from large losses.
</div>

<div>
<b style="color:#7c9cff">Alpha</b> — <i>Extra return above the market</i><br>
If Nifty returned 12% and your strategy returned 20%, your alpha is +8%.
Positive alpha = you beat the market.
</div>

<div>
<b style="color:#7c9cff">Partial Booking</b> — <i>Selling a portion of the position at a profit</i><br>
At +15% gain, sell 1/3 of your shares to lock in profit,
then let the rest run with the stop moved to breakeven.
</div>

<div>
<b style="color:#7c9cff">IPO Base</b> — <i>Settling period after listing</i><br>
After a stock lists, it often trades sideways for 40 days.
This "base" is the foundation from which a strong breakout launches.
</div>

<div>
<b style="color:#7c9cff">Stage 1 / 2 / 3</b> — <i>IPO pattern stages</i><br>
Stage 1 = still forming base. Stage 2 = recovering above EMA.
Stage 3 = breakout with volume — the buy signal.
</div>

<div>
<b style="color:#7c9cff">Rebalance</b> — <i>Adjusting the portfolio monthly</i><br>
Every month, sell stocks that fell in rank and buy the new top 5.
Forces you to always hold the strongest stocks.
</div>

</div>
""", unsafe_allow_html=True)


def _equity_metrics(eq_df: pd.DataFrame, start_col: str = 'Portfolio_Value',
                    alt_col: str = 'Equity') -> dict:
    col = start_col if start_col in eq_df.columns else alt_col
    if col not in eq_df.columns:
        return {}
    s = eq_df[col].dropna()
    if len(s) < 2:
        return {}
    cap   = s.iloc[0]
    final = s.iloc[-1]
    n_yr  = (s.index[-1] - s.index[0]).days / 365.25
    cagr  = ((final / cap) ** (1 / n_yr) - 1) * 100 if n_yr > 0 else 0
    dd    = ((s - s.cummax()) / s.cummax() * 100).min()
    return {
        'col': col, 'cap': cap, 'final': final,
        'total_ret': (final / cap - 1) * 100,
        'cagr': cagr, 'max_dd': dd,
        'start': str(s.index[0].date()), 'end': str(s.index[-1].date()),
    }


def _file_age(filename: str) -> str:
    p = Path(BASE_DIR) / filename
    if not p.exists():
        return 'never'
    mtime = datetime.fromtimestamp(p.stat().st_mtime)
    delta = datetime.now() - mtime
    if delta.seconds < 3600:
        return f'{delta.seconds // 60}m ago'
    if delta.days == 0:
        return f'{delta.seconds // 3600}h ago'
    return f'{delta.days}d ago'


def _run_strategy(commands: list[list[str]]):
    """Run a list of commands sequentially in the project folder."""
    for cmd in commands:
        result = subprocess.run(
            cmd, cwd=BASE_DIR, capture_output=True, text=True,
            env={**os.environ, 'PYTHONIOENCODING': 'utf-8'},
        )
        if result.returncode != 0:
            st.error(f'`{" ".join(cmd)}` failed:\n```\n{result.stderr[-800:]}\n```')
            return False
    return True


# ═══════════════════════════════════════════════════════════════════════════════
#  CHART BUILDERS
# ═══════════════════════════════════════════════════════════════════════════════

def chart_combined_equity(m: dict, i: dict, mo: dict) -> go.Figure:
    """Overlay all three equity curves normalized to % return."""
    fig = go.Figure()
    traces = [
        (m,  'Portfolio_Value', S_MONTHLY,  THEME[S_MONTHLY]['color'],  'solid'),
        (i,  'Portfolio_Value', S_IPO,      THEME[S_IPO]['color'],      'solid'),
        (mo, 'Equity',          S_MOMENTUM, THEME[S_MOMENTUM]['color'], 'solid'),
    ]
    for data, col, name, color, dash in traces:
        eq = data.get('equity')
        if eq is None or col not in eq.columns:
            continue
        s = eq[col].dropna()
        ret = (s / s.iloc[0] - 1) * 100
        fig.add_trace(go.Scatter(
            x=ret.index, y=ret.values,
            name=name, line=dict(color=color, width=2, dash=dash),
        ))
    fig.add_hline(y=0, line=dict(color='#333', dash='dash', width=1))
    fig.update_layout(
        **PLOTLY_BASE,
        title=dict(text='All Strategies — Normalised Return (%)',
                   font=dict(color='#e0e0e0', size=13)),
        yaxis=dict(ticksuffix='%', gridcolor='#1a1f35', title='Return'),
        xaxis=dict(gridcolor='#1a1f35'),
        legend=dict(orientation='h', x=0, y=1.1, bgcolor='rgba(0,0,0,0)'),
        height=340,
        margin=dict(l=10, r=10, t=50, b=10),
    )
    return fig


def chart_equity(eq_df: pd.DataFrame, col: str, name: str,
                 color: str, bench_col: str | None = None) -> go.Figure:
    """Single strategy equity curve with optional benchmark."""
    fig = go.Figure()
    s = eq_df[col].dropna()
    ret = (s / s.iloc[0] - 1) * 100
    fig.add_trace(go.Scatter(
        x=ret.index, y=ret.values, name=name,
        line=dict(color=color, width=2),
        fill='tozeroy', fillcolor=_hex_rgba(color, 0.07),
    ))
    if bench_col and bench_col in eq_df.columns:
        b = eq_df[bench_col].dropna()
        b_ret = (b / b.iloc[0] - 1) * 100
        fig.add_trace(go.Scatter(
            x=b_ret.index, y=b_ret.values, name='NiftyBees',
            line=dict(color='#ff9800', width=1.2, dash='dot'),
        ))
    fig.add_hline(y=0, line=dict(color='#333', dash='dash', width=1))
    fig.update_layout(
        **PLOTLY_BASE,
        yaxis=dict(ticksuffix='%', gridcolor='#1a1f35'),
        xaxis=dict(gridcolor='#1a1f35'),
        legend=dict(orientation='h', x=0, y=1.08, bgcolor='rgba(0,0,0,0)'),
        height=300,
        margin=dict(l=10, r=10, t=30, b=10),
    )
    return fig


def chart_plotly_table(df: pd.DataFrame, col_widths: list[int] | None = None,
                       row_colors: list[str] | None = None,
                       score_col: str | None = 'Score') -> go.Figure:
    """Plotly table with optional per-row colours and score bar column."""
    disp = df.copy()
    if score_col and score_col in disp.columns:
        disp[score_col] = disp[score_col].apply(
            lambda x: _score_bar(float(x)) if str(x) not in ('—', 'nan', '') else '—'
        )

    vals   = [disp[c].tolist() for c in disp.columns]
    n_rows = len(disp)
    fill   = row_colors if row_colors else ['#12172a'] * n_rows
    fig = go.Figure(go.Table(
        columnwidth=col_widths,
        header=dict(
            values=[f'<b>{c}</b>' for c in disp.columns],
            fill_color='#1a1f35', align='center',
            font=dict(color='#8892a4', size=11), height=30,
        ),
        cells=dict(
            values=vals,
            fill_color=[fill] * len(disp.columns),
            align='left',
            font=dict(color='#d8dde8', size=11),
            height=26,
        ),
    ))
    fig.update_layout(
        **PLOTLY_BASE,
        height=min(56 + n_rows * 28, 680),
        margin=dict(l=0, r=0, t=0, b=0),
    )
    return fig


# ═══════════════════════════════════════════════════════════════════════════════
#  SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════════
#  HISTORY & PROOF  —  HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _annual_returns(eq: pd.Series) -> dict[int, float]:
    """Year-by-year returns from an equity series."""
    out = {}
    for yr in sorted(eq.index.year.unique()):
        s = eq[eq.index.year == yr].dropna()
        if len(s) >= 2:
            out[yr] = round((s.iloc[-1] / s.iloc[0] - 1) * 100, 1)
    return out


def _win_rate_from_trades(trades: pd.DataFrame | None) -> float | None:
    """Win rate from a trades DataFrame that has Result or PnL_Pct column."""
    if trades is None or trades.empty:
        return None
    closed = trades[trades['Status'] == 'Closed'] if 'Status' in trades.columns else trades
    if closed.empty:
        return None
    if 'Result' in closed.columns:
        return (closed['Result'] == 'Win').mean() * 100
    if 'PnL_Pct' in closed.columns:
        return (closed['PnL_Pct'] > 0).mean() * 100
    return None


def _sharpe_from_equity(eq: pd.Series) -> float:
    dr = eq.pct_change().dropna()
    return float(dr.mean() / dr.std() * (252 ** 0.5)) if dr.std() > 0 else 0.0


def _compute_confidence(
    eq_df: pd.DataFrame | None,
    eq_col: str,
    trades: pd.DataFrame | None,
    bench_col: str | None,
) -> dict:
    """
    Score each strategy 0-100 across 5 criteria (20 pts each):
      1. Positive total return
      2. Beat benchmark CAGR
      3. Win rate > 45%  (or > 50% monthly months for Monthly Rotation)
      4. Sharpe ratio > 0.3
      5. Max drawdown > -25%
    Returns a dict with score, level, color, criteria list, annual_returns, metrics.
    """
    results = []
    score   = 0

    if eq_df is None or eq_col not in eq_df.columns:
        return {'score': 0, 'level': 'NO DATA', 'color': '#555', 'criteria': [],
                'annual': {}, 'metrics': {}}

    eq = eq_df[eq_col].dropna()
    mx = _equity_metrics(eq_df, eq_col, eq_col)

    # ── 1. Positive total return ───────────────────────────────────────────────
    total_ret = mx.get('total_ret', -999)
    passed    = total_ret > 0
    if passed: score += 20
    results.append({
        'label': 'Positive Total Return',
        'value': f'{total_ret:+.1f}%',
        'pass': passed,
        'detail': 'Strategy made money over the backtest period',
    })

    # ── 2. Beat benchmark ─────────────────────────────────────────────────────
    bench_cagr = None
    if bench_col and bench_col in eq_df.columns:
        b = eq_df[bench_col].dropna()
        if len(b) > 1:
            b_yr = (b.index[-1] - b.index[0]).days / 365.25
            bench_cagr = ((b.iloc[-1] / b.iloc[0]) ** (1 / b_yr) - 1) * 100 if b_yr > 0 else 0
    strat_cagr = mx.get('cagr', -999)
    if bench_cagr is not None:
        passed = strat_cagr > bench_cagr
        alpha  = strat_cagr - bench_cagr
        if passed: score += 20
        results.append({
            'label': 'Beat NiftyBees (CAGR)',
            'value': f'Alpha {alpha:+.1f}%/yr',
            'pass': passed,
            'detail': f'Strategy CAGR {strat_cagr:+.1f}% vs NiftyBees {bench_cagr:+.1f}%',
        })
    else:
        results.append({
            'label': 'Beat NiftyBees (CAGR)',
            'value': 'No benchmark data',
            'pass': None,
            'detail': 'Benchmark CSV not available',
        })

    # ── 3. Win rate ───────────────────────────────────────────────────────────
    wr = _win_rate_from_trades(trades)
    if wr is not None:
        passed = wr > 45
        if passed: score += 20
        results.append({
            'label': 'Win Rate > 45%',
            'value': f'{wr:.1f}%',
            'pass': passed,
            'detail': f'{wr:.1f}% of closed trades were profitable',
        })
    else:
        # For Monthly Rotation: use % of months with positive return
        monthly_rets = [v for v in _annual_returns(eq).values()]
        pct_pos = sum(1 for r in monthly_rets if r > 0) / len(monthly_rets) * 100 if monthly_rets else 0
        passed = pct_pos > 50
        if passed: score += 20
        results.append({
            'label': '% Positive Years',
            'value': f'{pct_pos:.0f}%',
            'pass': passed,
            'detail': f'{pct_pos:.0f}% of years had positive returns',
        })

    # ── 4. Sharpe ratio ───────────────────────────────────────────────────────
    sharpe = _sharpe_from_equity(eq)
    passed = sharpe > 0.3
    if passed: score += 20
    results.append({
        'label': 'Sharpe Ratio > 0.3',
        'value': f'{sharpe:.2f}',
        'pass': passed,
        'detail': 'Risk-adjusted return (higher = better, >1 is excellent)',
    })

    # ── 5. Drawdown within limit ──────────────────────────────────────────────
    max_dd = mx.get('max_dd', -100)
    passed = max_dd > -25
    if passed: score += 20
    results.append({
        'label': 'Max Drawdown < 25%',
        'value': f'{max_dd:.1f}%',
        'pass': passed,
        'detail': 'Worst peak-to-trough loss (smaller loss = more controlled)',
    })

    # ── Confidence level ──────────────────────────────────────────────────────
    if score >= 80:
        level, color = 'HIGH',   '#00c853'
    elif score >= 60:
        level, color = 'MODERATE', '#f9c200'
    elif score >= 40:
        level, color = 'CAUTION', '#ff9800'
    else:
        level, color = 'LOW',    '#ff3d3d'

    return {
        'score':    score,
        'level':    level,
        'color':    color,
        'criteria': results,
        'annual':   _annual_returns(eq),
        'metrics':  mx,
        'sharpe':   sharpe,
        'bench_cagr': bench_cagr,
    }


def _color_ret(val: float) -> str:
    """Cell background for return value."""
    if val > 15:  return 'rgba(0,200,83,0.30)'
    if val > 5:   return 'rgba(0,200,83,0.16)'
    if val > 0:   return 'rgba(0,200,83,0.08)'
    if val > -5:  return 'rgba(255,61,61,0.08)'
    if val > -15: return 'rgba(255,61,61,0.18)'
    return 'rgba(255,61,61,0.30)'


def chart_bar_comparison(strategies: dict[str, dict]) -> go.Figure:
    """Grouped bar chart: CAGR vs Benchmark for each strategy."""
    names      = list(strategies.keys())
    cagrs      = [d['metrics'].get('cagr', 0)      for d in strategies.values()]
    bench_cagrs= [d.get('bench_cagr') or 0         for d in strategies.values()]
    colors     = [d['color']                        for d in strategies.values()]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name='Strategy CAGR', x=names, y=cagrs,
        marker_color=colors, text=[f'{v:+.1f}%' for v in cagrs],
        textposition='outside',
    ))
    fig.add_trace(go.Bar(
        name='NiftyBees CAGR', x=names, y=bench_cagrs,
        marker_color='#ff9800', opacity=0.6,
        text=[f'{v:+.1f}%' for v in bench_cagrs],
        textposition='outside',
    ))
    fig.add_hline(y=0, line=dict(color='#444', width=1))
    fig.update_layout(
        **PLOTLY_BASE,
        barmode='group',
        title=dict(text='Strategy CAGR vs NiftyBees Benchmark',
                   font=dict(color='#e0e0e0', size=13)),
        yaxis=dict(ticksuffix='%', gridcolor='#1a1f35'),
        xaxis=dict(gridcolor='#1a1f35'),
        legend=dict(orientation='h', x=0, y=1.12, bgcolor='rgba(0,0,0,0)'),
        height=340,
        margin=dict(l=10, r=10, t=60, b=10),
    )
    return fig


def chart_drawdown_comparison(data_map: dict[str, tuple[pd.DataFrame, str]]) -> go.Figure:
    """Overlay drawdown curves for all strategies."""
    fig = go.Figure()
    for name, (eq_df, col) in data_map.items():
        if eq_df is None or col not in eq_df.columns:
            continue
        s    = eq_df[col].dropna()
        dd   = (s - s.cummax()) / s.cummax() * 100
        color = THEME.get(name, {}).get('color', '#888')
        fig.add_trace(go.Scatter(
            x=dd.index, y=dd.values, name=name,
            line=dict(color=color, width=1.5),
            fill='tozeroy', fillcolor=_hex_rgba(color, 0.08),
        ))
    fig.add_hline(y=0, line=dict(color='#444', dash='dash', width=1))
    fig.update_layout(
        **PLOTLY_BASE,
        title=dict(text='Drawdown — All Strategies',
                   font=dict(color='#e0e0e0', size=13)),
        yaxis=dict(ticksuffix='%', gridcolor='#1a1f35', title='Drawdown %'),
        xaxis=dict(gridcolor='#1a1f35'),
        legend=dict(orientation='h', x=0, y=1.12, bgcolor='rgba(0,0,0,0)'),
        height=280,
        margin=dict(l=10, r=10, t=50, b=10),
    )
    return fig


# ═══════════════════════════════════════════════════════════════════════════════
#  HISTORY & PROOF  —  PAGE RENDER
# ═══════════════════════════════════════════════════════════════════════════════

def _chart_yearly_bars(ann_data: dict[str, dict[int, float]],
                       bench_ann: dict[int, float]) -> go.Figure:
    """Grouped bar chart: each strategy's yearly return + Nifty line."""
    all_years = sorted(set(
        yr for d in ann_data.values() for yr in d
    ) | set(bench_ann.keys()))

    fig = go.Figure()

    for strat, ann in ann_data.items():
        th = THEME[strat]
        vals = [ann.get(yr) for yr in all_years]
        # only plot years that have data
        xs = [yr for yr, v in zip(all_years, vals) if v is not None]
        ys = [v  for v in vals if v is not None]
        if not xs:
            continue
        fig.add_trace(go.Bar(
            name=f'{th["icon"]} {strat}',
            x=xs, y=ys,
            marker_color=th['color'],
            text=[f'{v:+.0f}%' for v in ys],
            textposition='outside',
            opacity=0.85,
        ))

    # Nifty as a line overlay
    if bench_ann:
        bx = [yr for yr in all_years if yr in bench_ann]
        by = [bench_ann[yr] for yr in bx]
        fig.add_trace(go.Scatter(
            name='📊 Nifty (benchmark)',
            x=bx, y=by,
            mode='lines+markers+text',
            line=dict(color='#ff9800', width=2, dash='dot'),
            marker=dict(size=6, color='#ff9800'),
            text=[f'{v:+.0f}%' for v in by],
            textposition='top center',
            textfont=dict(color='#ff9800', size=10),
        ))

    fig.add_hline(y=0, line=dict(color='#555', width=1))
    fig.update_layout(
        **PLOTLY_BASE,
        barmode='group',
        title=dict(text='Yearly Returns — Strategy vs Nifty',
                   font=dict(color='#e0e0e0', size=13)),
        yaxis=dict(ticksuffix='%', gridcolor='#1a1f35',
                   zeroline=False, title='Return %'),
        xaxis=dict(gridcolor='#1a1f35', tickmode='linear', dtick=1,
                   title='Year'),
        legend=dict(orientation='h', x=0, y=1.14, bgcolor='rgba(0,0,0,0)',
                    font=dict(size=11)),
        height=400,
        margin=dict(l=10, r=10, t=70, b=10),
    )
    return fig


def _chart_growth_of_1L(data_map: dict[str, tuple[pd.DataFrame, str]],
                         bench: tuple[pd.DataFrame, str] | None) -> go.Figure:
    """Line chart: ₹1 lakh invested at start grows to ₹X over time."""
    fig = go.Figure()
    for strat, (eq_df, col) in data_map.items():
        if eq_df is None or col not in eq_df.columns:
            continue
        s = eq_df[col].dropna()
        if len(s) < 2:
            continue
        normalized = s / s.iloc[0] * 100_000
        th = THEME[strat]
        fig.add_trace(go.Scatter(
            x=normalized.index, y=normalized.values,
            name=f'{th["icon"]} {strat}',
            line=dict(color=th['color'], width=2),
            fill='tozeroy',
            fillcolor=_hex_rgba(th['color'], 0.05),
        ))
    if bench is not None:
        eq_df, col = bench
        if eq_df is not None and col in eq_df.columns:
            s = eq_df[col].dropna()
            if len(s) >= 2:
                normalized = s / s.iloc[0] * 100_000
                fig.add_trace(go.Scatter(
                    x=normalized.index, y=normalized.values,
                    name='📊 Nifty (if you just held)',
                    line=dict(color='#ff9800', width=2, dash='dot'),
                ))

    fig.add_hline(y=100_000, line=dict(color='#555', dash='dash', width=1),
                  annotation_text='₹1 lakh invested',
                  annotation_font=dict(color='#888', size=10))
    fig.update_layout(
        **PLOTLY_BASE,
        title=dict(text='Growth of ₹1 Lakh — If You Had Invested from Day 1',
                   font=dict(color='#e0e0e0', size=13)),
        yaxis=dict(
            gridcolor='#1a1f35',
            title='Portfolio Value (₹)',
            tickformat=',.0f',
        ),
        xaxis=dict(gridcolor='#1a1f35'),
        legend=dict(orientation='h', x=0, y=1.14, bgcolor='rgba(0,0,0,0)',
                    font=dict(size=11)),
        height=340,
        margin=dict(l=10, r=10, t=70, b=10),
    )
    return fig


def render_history(m: dict, i: dict, mo: dict):
    st.markdown("""
    <div style="padding:4px 0 16px 0;">
      <div class="page-title">📊 History & Proof</div>
      <div class="page-sub">
        Simple question: <b>did these strategies actually make money?</b>
        Here's the complete year-by-year record in plain numbers.
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Pull equity series ─────────────────────────────────────────────────────
    m_eq  = m.get('equity')
    i_eq  = i.get('equity')
    mo_eq = mo.get('equity')

    # ── Compute confidence for each strategy ───────────────────────────────────
    conf_m  = _compute_confidence(m_eq,  'Portfolio_Value', m.get('trades'),  'Benchmark_Value')
    conf_i  = _compute_confidence(i_eq,  'Portfolio_Value', i.get('trades'),  'Benchmark_Value')
    conf_mo = _compute_confidence(mo_eq, 'Equity',          mo.get('trades'), None)

    confs = {
        S_MONTHLY:  conf_m,
        S_IPO:      conf_i,
        S_MOMENTUM: conf_mo,
    }

    # ══════════════════════════════════════════════════════════════════════════
    #  COLLECT ANNUAL DATA (shared across sections)
    # ══════════════════════════════════════════════════════════════════════════
    ann_data  = {}
    bench_ann = {}

    for strat, col, df_src in [
        (S_MONTHLY,  'Portfolio_Value', m_eq),
        (S_IPO,      'Portfolio_Value', i_eq),
        (S_MOMENTUM, 'Equity',          mo_eq),
    ]:
        if df_src is not None and col in df_src.columns:
            ann_data[strat] = _annual_returns(df_src[col].dropna())
        else:
            ann_data[strat] = {}

    if m_eq is not None and 'Benchmark_Value' in m_eq.columns:
        bench_ann = _annual_returns(m_eq['Benchmark_Value'].dropna())

    all_years = sorted(set(
        yr for d in ann_data.values() for yr in d
    ) | set(bench_ann.keys()))

    # ══════════════════════════════════════════════════════════════════════════
    #  SECTION 1 — PLAIN-ENGLISH SUMMARY CARDS
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown(
        '<div class="sec-hdr">At a Glance — How Each Strategy Performed</div>',
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns(3)
    for col_st, (strat, conf) in zip([c1, c2, c3], confs.items()):
        th    = THEME[strat]
        color = conf['color']
        level = conf['level']
        mx    = conf['metrics']
        ann   = ann_data.get(strat, {})

        # How many years of data
        years_data = sorted(ann.keys())
        n_years    = len(years_data)
        yr_range   = f'{years_data[0]}–{years_data[-1]}' if years_data else '—'

        # Total growth of ₹1L
        if mx and mx.get('total_ret') is not None:
            end_val   = 100_000 * (1 + mx['total_ret'] / 100)
            growth_str = f'₹{end_val:,.0f}'
        else:
            growth_str = '—'

        # Beat Nifty in how many years
        beat_count = sum(
            1 for yr in years_data
            if yr in bench_ann and ann[yr] > bench_ann[yr]
        )
        beat_str   = f'{beat_count} of {n_years} years' if n_years else '—'

        # Avg return per year
        avg_yr = sum(ann.values()) / len(ann) if ann else 0

        # Verdict emoji
        verdict_icon = {'HIGH': '✅', 'MODERATE': '⚠️', 'CAUTION': '🟠', 'LOW': '❌'}.get(level, '⚪')

        with col_st:
            st.markdown(f"""
            <div class="hub-card" style="border-top:4px solid {color};">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
                <div style="font-size:14px;font-weight:800;color:{th['color']}">
                  {th['icon']} {strat}
                </div>
                <div style="font-size:20px;">{verdict_icon}</div>
              </div>

              <div style="font-size:11px;color:#6e7891;margin-bottom:12px;">
                {n_years} year{'s' if n_years != 1 else ''} of data &nbsp;·&nbsp; {yr_range}
              </div>

              <div style="margin-bottom:8px;">
                <div style="font-size:11px;color:#6e7891;">₹1 lakh invested grew to</div>
                <div style="font-size:26px;font-weight:800;color:{color};line-height:1.1;">{growth_str}</div>
              </div>

              <div class="divider"></div>

              <div style="display:flex;justify-content:space-between;font-size:12px;margin-top:8px;">
                <div>
                  <div style="color:#6e7891;font-size:10px;">Avg yearly return</div>
                  <div style="color:#e0e0e0;font-weight:700;">{avg_yr:+.1f}%</div>
                </div>
                <div>
                  <div style="color:#6e7891;font-size:10px;">Beat Nifty</div>
                  <div style="color:#e0e0e0;font-weight:700;">{beat_str}</div>
                </div>
                <div>
                  <div style="color:#6e7891;font-size:10px;">Worst loss</div>
                  <div style="color:#ff3d3d;font-weight:700;">{mx.get('max_dd', 0):.1f}%</div>
                </div>
              </div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown('<br>', unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════════
    #  SECTION 2 — YEAR-BY-YEAR BAR CHART
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown('<div class="sec-hdr">Year-by-Year Returns — Strategy vs Nifty</div>',
                unsafe_allow_html=True)
    st.markdown(
        '<div style="font-size:12px;color:#5a6480;margin-bottom:10px;">'
        'Each bar = how much % profit or loss that year. '
        'Orange dotted line = what Nifty gave that same year. '
        'Bars above orange = strategy beat Nifty. Bars below = Nifty won.'
        '</div>', unsafe_allow_html=True,
    )
    st.plotly_chart(_chart_yearly_bars(ann_data, bench_ann), width='stretch')

    # ══════════════════════════════════════════════════════════════════════════
    #  SECTION 3 — GROWTH OF ₹1 LAKH CHART
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown('<div class="sec-hdr">Growth of ₹1 Lakh — From Start to Today</div>',
                unsafe_allow_html=True)
    st.markdown(
        '<div style="font-size:12px;color:#5a6480;margin-bottom:10px;">'
        'If you had put ₹1 lakh into each strategy on day one and never touched it, '
        'here is what it would be worth today. Orange line = just buying Nifty (do nothing).'
        '</div>', unsafe_allow_html=True,
    )
    bench_src = (m_eq, 'Benchmark_Value') if m_eq is not None else None
    st.plotly_chart(
        _chart_growth_of_1L(
            {S_MONTHLY:  (m_eq,  'Portfolio_Value'),
             S_IPO:      (i_eq,  'Portfolio_Value'),
             S_MOMENTUM: (mo_eq, 'Equity')},
            bench_src,
        ),
        width='stretch',
    )

    # ══════════════════════════════════════════════════════════════════════════
    #  SECTION 4 — YEAR-BY-YEAR TABLE (simple, with Beat Nifty column)
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown('<br>', unsafe_allow_html=True)
    st.markdown('<div class="sec-hdr">Complete Year-by-Year Record (with Beat Nifty?)</div>',
                unsafe_allow_html=True)
    st.markdown(
        '<div style="font-size:11px;color:#5a6480;margin-bottom:8px;">'
        'Green = made money that year &nbsp;·&nbsp; Red = lost money &nbsp;·&nbsp; '
        '✅ = beat Nifty that year &nbsp;·&nbsp; ❌ = Nifty did better'
        '</div>', unsafe_allow_html=True,
    )

    if all_years:
        hdr_html = (
            '<th style="background:#1a1f35;color:#8892a4;padding:9px 14px;font-size:12px;text-align:left;">Year</th>'
        )
        for strat in [S_MONTHLY, S_IPO, S_MOMENTUM]:
            th = THEME[strat]
            hdr_html += (
                f'<th style="background:#1a1f35;color:{th["color"]};padding:9px 14px;'
                f'font-size:12px;text-align:center;">{th["icon"]} {strat}</th>'
                f'<th style="background:#1a1f35;color:{th["color"]}88;padding:9px 10px;'
                f'font-size:11px;text-align:center;">Beat Nifty?</th>'
            )
        hdr_html += ('<th style="background:#1a1f35;color:#ff9800;padding:9px 14px;'
                     'font-size:12px;text-align:center;">📊 Nifty</th>')

        rows_html = ''
        for yr in all_years:
            row = f'<td style="background:#12172a;color:#8892a4;padding:7px 14px;font-weight:700;font-size:13px;">{yr}</td>'
            for strat in [S_MONTHLY, S_IPO, S_MOMENTUM]:
                val = ann_data.get(strat, {}).get(yr)
                bv  = bench_ann.get(yr)
                if val is not None:
                    bg   = _color_ret(val)
                    sign = '+' if val >= 0 else ''
                    row += (f'<td style="background:{bg};color:#e0e0e0;padding:7px 14px;'
                            f'text-align:center;font-size:13px;font-weight:700;">'
                            f'{sign}{val:.1f}%</td>')
                    # Beat Nifty column
                    if bv is not None:
                        beat = '✅' if val > bv else '❌'
                        bc   = '#00c853' if val > bv else '#ff3d3d'
                        row += (f'<td style="background:#12172a;color:{bc};padding:7px 10px;'
                                f'text-align:center;font-size:14px;">{beat}</td>')
                    else:
                        row += '<td style="background:#12172a;color:#3a4060;text-align:center;">—</td>'
                else:
                    row += '<td style="background:#0e1117;color:#3a4060;text-align:center;padding:7px 14px;">—</td>'
                    row += '<td style="background:#0e1117;color:#3a4060;text-align:center;">—</td>'
            # Nifty column
            if bv is not None:
                bg   = _color_ret(bv)
                sign = '+' if bv >= 0 else ''
                row += (f'<td style="background:{bg};color:#ff9800;padding:7px 14px;'
                        f'text-align:center;font-size:13px;font-weight:700;">{sign}{bv:.1f}%</td>')
            else:
                row += '<td style="background:#0e1117;color:#3a4060;text-align:center;padding:7px 14px;">—</td>'
            rows_html += f'<tr>{row}</tr>'

        st.markdown(f"""
        <div style="overflow-x:auto;margin-bottom:16px;">
        <table style="width:100%;border-collapse:collapse;
               font-family:'Inter','Segoe UI',sans-serif;">
          <thead><tr>{hdr_html}</tr></thead>
          <tbody>{rows_html}</tbody>
        </table>
        </div>
        """, unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════════
    #  SECTION 5 — HOW MANY TRADES WON / LOST (IPO + Momentum only)
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown('<div class="sec-hdr">Individual Trades — Did More Win or Lose?</div>',
                unsafe_allow_html=True)
    st.markdown(
        '<div style="font-size:12px;color:#5a6480;margin-bottom:10px;">'
        'Every single stock trade taken — how many made profit, how many lost money, '
        'and the best / worst individual trades.'
        '</div>', unsafe_allow_html=True,
    )

    trade_cols = st.columns(2)
    for col_idx, (strat, data) in enumerate([
        (S_IPO,      i),
        (S_MOMENTUM, mo),
    ]):
        trades = data.get('trades')
        th     = THEME[strat]
        with trade_cols[col_idx]:
            st.markdown(f'<div style="font-size:13px;font-weight:700;color:{th["color"]};'
                        f'margin-bottom:8px;">{th["icon"]} {strat}</div>', unsafe_allow_html=True)

            if trades is None or trades.empty:
                st.caption('No trade data available. Run the backtest first.')
                continue

            closed = trades[trades['Status'] == 'Closed'] if 'Status' in trades.columns else trades
            if closed.empty:
                st.caption('No closed trades yet.')
                continue

            result_col = 'Result' if 'Result' in closed.columns else None
            wins   = closed[closed[result_col] == 'Win']  if result_col else closed[closed['PnL_Pct'] > 0]
            losses = closed[closed[result_col] == 'Loss'] if result_col else closed[closed['PnL_Pct'] <= 0]

            n_tot  = len(closed)
            n_win  = len(wins)
            n_loss = len(losses)
            wr     = n_win / n_tot * 100 if n_tot else 0
            avg_g  = wins['PnL_Pct'].mean()   if n_win  else 0
            avg_l  = losses['PnL_Pct'].mean() if n_loss else 0
            exp    = (wr/100) * avg_g + (1 - wr/100) * avg_l

            bar_w  = int(wr)
            bar_l  = 100 - bar_w
            exp_col = '#00c853' if exp > 0 else '#ff3d3d'

            st.markdown(f"""
            <div style="background:#12172a;border:1px solid #1e2235;border-radius:10px;padding:16px;">
              <!-- Win/Loss bar -->
              <div style="display:flex;gap:0;border-radius:6px;overflow:hidden;
                   margin-bottom:6px;height:18px;">
                <div style="width:{bar_w}%;background:#00c853;"></div>
                <div style="width:{bar_l}%;background:#ff3d3d;"></div>
              </div>
              <div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:14px;">
                <span style="color:#00c853;font-weight:700;">✅ {n_win} trades made profit ({wr:.0f}%)</span>
                <span style="color:#ff3d3d;font-weight:700;">❌ {n_loss} trades lost ({100-wr:.0f}%)</span>
              </div>

              <!-- Key numbers in plain english -->
              <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;font-size:12px;">
                <div style="background:#0e1117;border-radius:6px;padding:8px;text-align:center;">
                  <div style="color:#6e7891;font-size:10px;margin-bottom:2px;">When it wins</div>
                  <div style="color:#00c853;font-weight:800;font-size:16px;">{avg_g:+.1f}%</div>
                  <div style="color:#555;font-size:10px;">avg profit</div>
                </div>
                <div style="background:#0e1117;border-radius:6px;padding:8px;text-align:center;">
                  <div style="color:#6e7891;font-size:10px;margin-bottom:2px;">When it loses</div>
                  <div style="color:#ff3d3d;font-weight:800;font-size:16px;">{avg_l:+.1f}%</div>
                  <div style="color:#555;font-size:10px;">avg loss</div>
                </div>
                <div style="background:#0e1117;border-radius:6px;padding:8px;text-align:center;">
                  <div style="color:#6e7891;font-size:10px;margin-bottom:2px;">Per trade avg</div>
                  <div style="color:{exp_col};font-weight:800;font-size:16px;">{exp:+.1f}%</div>
                  <div style="color:#555;font-size:10px;">expected gain</div>
                </div>
              </div>
            </div>
            """, unsafe_allow_html=True)

            # Best and worst trades
            if 'PnL_Pct' in closed.columns:
                hold_col = 'Holding_Days' if 'Holding_Days' in closed.columns else None
                best3    = closed.nlargest(3,  'PnL_Pct')
                worst3   = closed.nsmallest(3, 'PnL_Pct')

                def _trade_rows(df, color_str):
                    html = ''
                    for _, r in df.iterrows():
                        hd   = f" · {int(r[hold_col])} days" if hold_col and pd.notna(r.get(hold_col)) else ''
                        html += (
                            f'<div style="display:flex;justify-content:space-between;'
                            f'font-size:12px;padding:4px 0;border-bottom:1px solid #1e2235;">'
                            f'<span style="color:#c0c0c0;">'
                            f'  {r["Ticker"].replace(".NS","")}'
                            f'  <span style="color:#555;font-size:10px;">{hd}</span>'
                            f'</span>'
                            f'<span style="color:{color_str};font-weight:700;">'
                            f'  {r["PnL_Pct"]:+.1f}%'
                            f'</span></div>'
                        )
                    return html

                lc, rc = st.columns(2)
                with lc:
                    st.markdown(
                        f'<div style="font-size:11px;color:#5a6480;margin:10px 0 4px;">🏆 Best 3 trades</div>'
                        f'<div style="background:#0b1a10;border:1px solid #1a3520;'
                        f'border-radius:8px;padding:8px 12px;">'
                        f'{_trade_rows(best3, "#00c853")}</div>',
                        unsafe_allow_html=True,
                    )
                with rc:
                    st.markdown(
                        f'<div style="font-size:11px;color:#5a6480;margin:10px 0 4px;">📉 Worst 3 trades</div>'
                        f'<div style="background:#1a0b0b;border:1px solid #3a1515;'
                        f'border-radius:8px;padding:8px 12px;">'
                        f'{_trade_rows(worst3, "#ff3d3d")}</div>',
                        unsafe_allow_html=True,
                    )

    # ══════════════════════════════════════════════════════════════════════════
    #  SECTION 6 — WORST LOSING PERIODS (Drawdown)
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown('<br>', unsafe_allow_html=True)
    st.markdown('<div class="sec-hdr">Worst Losing Periods — How Bad Did It Get?</div>',
                unsafe_allow_html=True)
    st.markdown(
        '<div style="font-size:12px;color:#5a6480;margin-bottom:10px;">'
        'This shows how far the portfolio fell from its peak at any point in time. '
        'Smaller dips = more stable. If it drops -20% it means ₹1 lakh became ₹80,000 temporarily.'
        '</div>', unsafe_allow_html=True,
    )
    dd_map = {
        S_MONTHLY:  (m_eq,  'Portfolio_Value'),
        S_IPO:      (i_eq,  'Portfolio_Value'),
        S_MOMENTUM: (mo_eq, 'Equity'),
    }
    st.plotly_chart(chart_drawdown_comparison(dd_map), width='stretch')

    # ══════════════════════════════════════════════════════════════════════════
    #  SECTION 7 — FINAL VERDICT
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown('<br>', unsafe_allow_html=True)
    st.markdown('<div class="sec-hdr">Should You Invest? — Final Verdict</div>',
                unsafe_allow_html=True)

    VERDICTS = {
        'HIGH':     ('✅ Yes — Invest with Confidence',
                     'Strong proof that this strategy works across multiple years. '
                     'Follow the signals with proper position sizing.'),
        'MODERATE': ('⚠️ Yes — But Use Discipline',
                     'Strategy shows good results but not perfect. '
                     'Start with smaller amounts and follow the rules strictly.'),
        'CAUTION':  ('🟠 Maybe — Paper Trade First',
                     'Mixed results. Practice on paper for 1–2 months before '
                     'putting real money in.'),
        'LOW':      ('❌ No — Wait for Better Proof',
                     'Not enough evidence this strategy works reliably. '
                     'Do not invest real money until results improve.'),
        'NO DATA':  ('⚪ Run Backtest First',
                     'No historical data available yet. Run the backtest scripts first.'),
    }

    v1, v2, v3 = st.columns(3)
    for col_st, (strat, conf) in zip([v1, v2, v3], confs.items()):
        th      = THEME[strat]
        level   = conf['level']
        color   = conf['color']
        score   = conf['score']
        verdict, reason = VERDICTS.get(level, VERDICTS['NO DATA'])

        # Criteria checklist in plain english
        crit_html = ''
        for c in conf['criteria']:
            if c['pass'] is True:
                icon, ic = '✅', '#00c853'
            elif c['pass'] is False:
                icon, ic = '❌', '#ff3d3d'
            else:
                icon, ic = '⚪', '#888'
            crit_html += (
                f'<div style="display:flex;justify-content:space-between;'
                f'font-size:11px;padding:3px 0;border-bottom:1px solid #1e2235;">'
                f'<span style="color:#a0a8bf;">{icon} {c["label"]}</span>'
                f'<span style="color:{ic};font-weight:600;">{c["value"]}</span>'
                f'</div>'
            )

        with col_st:
            st.markdown(f"""
            <div class="hub-card" style="border-top:4px solid {color};text-align:center;">
              <div style="font-size:12px;font-weight:700;color:{th['color']};margin-bottom:10px;">
                {th['icon']} {strat}
              </div>
              <div style="font-size:18px;font-weight:800;color:{color};
                   line-height:1.3;margin-bottom:10px;">
                {verdict}
              </div>
              <div style="font-size:11px;color:#8892a4;line-height:1.6;margin-bottom:12px;">
                {reason}
              </div>
              <div style="background:{color}18;border-radius:6px;
                   padding:8px 12px;margin-bottom:12px;text-align:left;">
                {crit_html}
              </div>
              <div style="background:{color}22;border-radius:6px;
                   padding:8px;font-size:13px;font-weight:700;color:{color};">
                Confidence: {score}/100
              </div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("""
    <div style="margin-top:24px;background:#12172a;border:1px solid #1e2235;
         border-left:4px solid #f9c200;border-radius:8px;padding:14px 18px;
         font-size:11px;color:#8892a4;line-height:1.9;">
      <b style="color:#f9c200;">⚠️ Important:</b>
      These results are from past data (backtesting). Past performance does not
      guarantee the same returns in the future. Markets can change. Always invest
      only what you can afford to lose, and never put all your money in one strategy.
      This is for learning and research — not financial advice.
    </div>
    """, unsafe_allow_html=True)

    # ── Glossary ───────────────────────────────────────────────────────────────
    st.markdown('<br>', unsafe_allow_html=True)
    _glossary_expander()


def render_sidebar() -> str:
    with st.sidebar:
        st.markdown("""
        <div style="padding:12px 4px 24px 4px;">
          <div style="font-size:22px;font-weight:900;color:#e4e8f0;letter-spacing:-.02em;">
            ⬡ NSE Hub
          </div>
          <div style="font-size:11px;color:#3d4a60;margin-top:3px;letter-spacing:.04em;">
            3 STRATEGIES · SYSTEMATIC INVESTING
          </div>
        </div>
        """, unsafe_allow_html=True)

        page = st.radio(
            'Navigate',
            ['🏠  Home', '🔄  Monthly Rotation', '🚀  IPO Edge',
             '📈  Momentum Edge', '🔬  Insights', '📊  History & Proof'],
            label_visibility='collapsed',
        )

        st.markdown('<hr style="margin:16px 0;">', unsafe_allow_html=True)
        st.markdown('<div class="sec-hdr">Refresh Data</div>', unsafe_allow_html=True)

        col_a, col_b = st.columns(2)
        with col_a:
            if st.button('🔄 Monthly', width='stretch'):
                with st.spinner('Updating…'):
                    ok = _run_strategy([
                        [sys.executable, 'step1_download_data.py'],
                        [sys.executable, 'step2_backtest_momentum.py'],
                        [sys.executable, 'step3_dashboard.py'],
                    ])
                if ok:
                    st.cache_data.clear()
                    st.success('Done ✓')
                    st.rerun()

        with col_b:
            if st.button('🚀 IPO', width='stretch'):
                with st.spinner('Updating…'):
                    ok = _run_strategy([
                        [sys.executable, 'ipo_edge_downloader.py'],
                        [sys.executable, 'ipo_edge_backtest.py'],
                    ])
                if ok:
                    st.cache_data.clear()
                    st.success('Done ✓')
                    st.rerun()

        if st.button('📈 Momentum Edge', width='stretch'):
            with st.spinner('Updating…'):
                ok = _run_strategy([
                    [sys.executable, 'momentum_edge_downloader.py'],
                    [sys.executable, 'momentum_edge_backtest.py'],
                ])
            if ok:
                st.cache_data.clear()
                st.success('Done ✓')
                st.rerun()

        st.markdown('<hr style="margin:16px 0;">', unsafe_allow_html=True)
        st.markdown('<div class="sec-hdr">Last Updated</div>', unsafe_allow_html=True)
        st.markdown(f"""
        <div style="font-size:11px;line-height:2.2;color:#3d4a60;">
          🔄 Monthly &nbsp;&nbsp;<b style="color:#7c9cff">{_file_age('live_rankings.csv')}</b><br>
          🚀 IPO Edge &nbsp;&nbsp;<b style="color:#00c853">{_file_age('ipo_edge_equity.csv')}</b><br>
          📈 Momentum &nbsp;<b style="color:#f9c200">{_file_age('momentum_edge_equity.csv')}</b>
        </div>
        """, unsafe_allow_html=True)

        st.markdown('<hr style="margin:16px 0;">', unsafe_allow_html=True)
        st.markdown('<div class="sec-hdr">Quick Guide</div>', unsafe_allow_html=True)
        st.markdown("""
        <div style="font-size:11px;color:#3d4a60;line-height:2;padding:2px 0;">
          🏠 <b style="color:#6a748a">Home</b> — overview of all 3<br>
          🔄 <b style="color:#7c9cff">Monthly</b> — buy top 5 stocks, hold 1 month<br>
          🚀 <b style="color:#00c853">IPO Edge</b> — trade new listings at breakout<br>
          📈 <b style="color:#f9c200">Momentum</b> — buy stocks at all-time highs<br>
          📊 <b style="color:#8892a4">History</b> — see proof it worked
        </div>
        """, unsafe_allow_html=True)

    return page.split('  ', 1)[-1].strip()


# ═══════════════════════════════════════════════════════════════════════════════
#  HOME PAGE
# ═══════════════════════════════════════════════════════════════════════════════

def render_home(m: dict, i: dict, mo: dict):
    st.markdown("""
    <div style="padding:4px 0 20px 0;">
      <div class="page-title" style="color:#e4e8f0;">⬡ NSE Strategy Hub</div>
      <div class="page-sub">Three rules-based strategies that remove emotion from investing</div>
    </div>
    """, unsafe_allow_html=True)

    STRATEGY_DESC = {
        S_MONTHLY: {
            'plain':  'Buy the 5 strongest Nifty 50 stocks every month. Switch when better ones emerge.',
            'how':    'Every month we rank all 50 Nifty stocks by recent performance and hold the top 5. No guessing — pure data.',
            'good_for': 'Anyone who wants a simple, low-effort strategy. One decision per month.',
        },
        S_IPO: {
            'plain':  'Buy newly listed stocks when they break out of their first trading base.',
            'how':    'After an IPO settles for 40 days, we wait for a price breakout with strong volume. Early movers win big.',
            'good_for': 'Higher risk, higher reward. Works best when market sentiment is positive.',
        },
        S_MOMENTUM: {
            'plain':  'Buy large-cap stocks that dipped below trend, recovered, and hit new all-time highs.',
            'how':    'We use the 220-day moving average as the trend line. Stock must dip below it, recover fast, then make new highs.',
            'good_for': 'Best in bull markets. Tends to sit in cash during downturns automatically.',
        },
    }

    cards = [
        (S_MONTHLY,  m,  'Portfolio_Value', 'Benchmark_Value'),
        (S_IPO,      i,  'Portfolio_Value', None),
        (S_MOMENTUM, mo, 'Equity',          None),
    ]
    c1, c2, c3 = st.columns(3)
    for col, (strategy, data, eq_col, _) in zip([c1, c2, c3], cards):
        th      = THEME[strategy]
        eq      = data.get('equity')
        m_eq    = _equity_metrics(eq, eq_col, eq_col) if eq is not None else {}
        cagr    = f"{m_eq['cagr']:+.1f}%" if m_eq else '—'
        ret     = f"{m_eq['total_ret']:+.1f}%" if m_eq else '—'
        dd      = f"{m_eq['max_dd']:.1f}%" if m_eq else '—'
        trades_df = data.get('trades')
        n_tr    = len(trades_df) if trades_df is not None else '—'
        wr      = (f"{(trades_df['Result']=='Win').mean()*100:.0f}%"
                   if trades_df is not None and len(trades_df) else '—')
        desc    = STRATEGY_DESC[strategy]
        dd_color = '#ff5555' if m_eq and m_eq.get('max_dd', 0) < -20 else '#f9c200' if m_eq and m_eq.get('max_dd', 0) < -10 else '#00c853'

        with col:
            st.markdown(f"""
            <div class="hub-card" style="border-top: 3px solid {th['color']};">
              <div class="strategy-name" style="color:{th['color']}">
                {th['icon']} {strategy}
              </div>
              <div class="big-num" style="color:{th['color']}">{cagr}</div>
              <div class="plain-label">Avg yearly return &nbsp;·&nbsp; Total: {ret}</div>
              <div class="divider"></div>
              <div class="row">
                <div class="kv-block">
                  <div class="kv-l">Worst loss ever</div>
                  <div class="kv-v" style="color:{dd_color}">{dd}</div>
                  <div class="kv-explain">Max Drawdown</div>
                </div>
                <div class="kv-block">
                  <div class="kv-l">Trades done</div>
                  <div class="kv-v">{n_tr}</div>
                  <div class="kv-explain">Total trades</div>
                </div>
                <div class="kv-block">
                  <div class="kv-l">Profitable trades</div>
                  <div class="kv-v" style="color:#00c853">{wr}</div>
                  <div class="kv-explain">Win Rate</div>
                </div>
              </div>
              <div class="desc-box">
                <b style="color:#b0b8cc">In plain English:</b><br>{desc['plain']}<br><br>
                <b style="color:#6a748a">Good for:</b> {desc['good_for']}
              </div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown('<br>', unsafe_allow_html=True)

    st.markdown('<div class="sec-hdr">All 3 Strategies vs Nifty — Growth of ₹5 Lakh</div>',
                unsafe_allow_html=True)
    st.markdown("""
    <div style="font-size:11px;color:#3d4a60;margin:-4px 0 10px 2px;">
      Each line shows how ₹5 lakh would have grown if invested at the start of that strategy's backtest.
    </div>""", unsafe_allow_html=True)
    st.plotly_chart(chart_combined_equity(m, i, mo), width='stretch')

    st.markdown('<br>', unsafe_allow_html=True)
    st.markdown('<div class="sec-hdr">Today\'s Signals — What to Watch</div>', unsafe_allow_html=True)
    left, mid, right = st.columns(3)

    def _sig_card(ticker, company, signal, signal_color, extra_line=''):
        return f"""
        <div class="sig-card" style="border-left: 3px solid {signal_color};">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;">
            <div>
              <div style="font-size:14px;font-weight:800;color:#e4e8f0">{ticker}</div>
              <div style="font-size:10px;color:#4a5470;margin-top:1px">{company}</div>
            </div>
            <span class="badge" style="background:rgba(0,0,0,0.3);color:{signal_color};
                  border:1px solid {signal_color}44;font-size:10px;">{signal}</span>
          </div>
          {f'<div style="font-size:10px;color:#4a5470;margin-top:6px;">{extra_line}</div>' if extra_line else ''}
        </div>"""

    with left:
        st.markdown(f'<div style="font-size:11px;font-weight:700;color:{THEME[S_MONTHLY]["color"]};margin-bottom:8px;">🔄 Monthly — Hold These Now</div>', unsafe_allow_html=True)
        ranks = m.get('rankings', pd.DataFrame())
        if not ranks.empty:
            for _, row in ranks.head(3).iterrows():
                rs = row.get('RS_Score', 0)
                st.markdown(_sig_card(
                    row['Ticker'].replace('.NS', ''), row['Company'],
                    'Top Pick', THEME[S_MONTHLY]['color'],
                    f"Strength score: {rs:+.1f}% &nbsp;·&nbsp; Rank #{int(row['Rank'])}"
                ), unsafe_allow_html=True)
        else:
            st.markdown('<div style="font-size:12px;color:#3d4a60;padding:12px;">Run Monthly update to see picks</div>', unsafe_allow_html=True)

    with mid:
        st.markdown(f'<div style="font-size:11px;font-weight:700;color:{THEME[S_IPO]["color"]};margin-bottom:8px;">🚀 IPO Edge — Live Breakouts</div>', unsafe_allow_html=True)
        sigs = i.get('signals', pd.DataFrame())
        shown = sigs[sigs['Signal'].isin(['Live Breakout', 'Watch Zone'])].head(3) if not sigs.empty and 'Signal' in sigs.columns else pd.DataFrame()
        sig_c = {'Live Breakout': '#00c853', 'Watch Zone': '#f9c200'}
        if not shown.empty:
            for _, row in shown.iterrows():
                sc = sig_c.get(row['Signal'], '#888')
                setup = row.get('Setup', '')
                st.markdown(_sig_card(
                    row['Ticker'], row['Company'], row['Signal'], sc,
                    f"Stage: {row.get('Stage','')} &nbsp;·&nbsp; Setup: {setup} &nbsp;·&nbsp; Vol: {row.get('Vol Ratio',0):.1f}×"
                ), unsafe_allow_html=True)
        else:
            st.markdown('<div style="font-size:12px;color:#3d4a60;padding:12px;">No active IPO breakouts right now</div>', unsafe_allow_html=True)

    with right:
        st.markdown(f'<div style="font-size:11px;font-weight:700;color:{THEME[S_MOMENTUM]["color"]};margin-bottom:8px;">📈 Momentum — Breakouts Today</div>', unsafe_allow_html=True)
        msigs = mo.get('signals', pd.DataFrame())
        shown = msigs[msigs['Signal'].isin(['Breakout Today', 'Near Breakout'])].head(3) if not msigs.empty and 'Signal' in msigs.columns else pd.DataFrame()
        sig_c = {'Breakout Today': '#00c853', 'Near Breakout': '#f9c200'}
        if not shown.empty:
            for _, row in shown.iterrows():
                sc  = sig_c.get(row['Signal'], '#888')
                rec = row.get('Recovery', '—')
                qual = row.get('Chart Qual', '—')
                st.markdown(_sig_card(
                    row['Ticker'], row['Company'], row['Signal'], sc,
                    f"Recovery: {rec} &nbsp;·&nbsp; Chart: {qual}"
                ), unsafe_allow_html=True)
        else:
            st.markdown('<div style="font-size:12px;color:#3d4a60;padding:12px;">No momentum breakouts today</div>', unsafe_allow_html=True)

    st.markdown('<br>', unsafe_allow_html=True)
    _glossary_expander()


# ═══════════════════════════════════════════════════════════════════════════════
#  MONTHLY ROTATION PAGE
# ═══════════════════════════════════════════════════════════════════════════════

def render_monthly(m: dict):
    color = THEME[S_MONTHLY]['color']
    st.markdown(f'<div class="page-title" style="color:{color}">🔄 Monthly Rotation</div>'
                '<div class="page-sub">Buy the 5 strongest Nifty stocks · Switch every month · No emotion</div><br>',
                unsafe_allow_html=True)

    st.markdown(_explain_box(
        '<b>How it works:</b> Every month, we rank all 50 Nifty stocks by their recent price strength '
        '(<b>RS Score</b>). We buy the top 5 and hold them for the month. If a stock falls out of the '
        'top 5, we sell it and replace it with the new entrant. Simple, systematic, no guessing.',
        color
    ), unsafe_allow_html=True)

    eq = m.get('equity')
    if eq is None:
        st.error('No backtest data. Run **step1 → step2 → step3** first.')
        return

    mx    = _equity_metrics(eq, 'Portfolio_Value', 'Portfolio_Value')
    ranks = m.get('rankings', pd.DataFrame())
    reb   = m.get('rebalance', pd.DataFrame())

    b_ret  = 0.0
    b_cagr = 0.0
    if 'Benchmark_Value' in eq.columns:
        bv     = eq['Benchmark_Value'].dropna()
        b_ret  = (bv.iloc[-1] / bv.iloc[0] - 1) * 100
        b_yrs  = (bv.index[-1] - bv.index[0]).days / 365.25
        b_cagr = ((bv.iloc[-1] / bv.iloc[0]) ** (1 / max(b_yrs, 0.01)) - 1) * 100

    n_months = len(reb) if reb is not None and not reb.empty else '—'
    alpha    = mx['cagr'] - b_cagr if mx else 0

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: st.markdown(pill('Avg Yearly Return', f"{mx['cagr']:+.1f}%" if mx else '—',
        f"Total gain: {mx['total_ret']:+.1f}%" if mx else '', color,
        'CAGR — how much it grew per year on average'), unsafe_allow_html=True)
    with c2: st.markdown(pill('Worst Loss Ever', f"{mx['max_dd']:.1f}%" if mx else '—',
        'From peak to trough', '#ff5555',
        'Max Drawdown — if it peaked at ₹1L then fell, how low did it go?'), unsafe_allow_html=True)
    with c3: st.markdown(pill('Nifty Return', f'{b_ret:+.1f}%',
        f'CAGR: {b_cagr:+.1f}%', '#ff9800',
        'What plain Nifty index gave in the same period'), unsafe_allow_html=True)
    with c4: st.markdown(pill('Extra vs Nifty', f"{alpha:+.1f}%",
        'Per year above Nifty', color,
        'Alpha — the bonus return above just buying the index'), unsafe_allow_html=True)
    with c5: st.markdown(pill('Months Tracked', str(n_months),
        f"{mx['start']} → {mx['end']}" if mx else '', '#8892a4',
        'How long this strategy has been running'), unsafe_allow_html=True)

    st.markdown('<br>', unsafe_allow_html=True)

    if not ranks.empty:
        st.markdown(f'<div class="sec-hdr" style="color:{color}">Buy These Now — Top 5 This Month</div>', unsafe_allow_html=True)
        st.markdown('<div style="font-size:11px;color:#3d4a60;margin:-4px 0 12px 2px;">These are ranked by RS Score — how much they outperformed recently. Higher = stronger stock.</div>', unsafe_allow_html=True)
        cols = st.columns(5)
        for col_st, (_, row) in zip(cols, ranks.head(5).iterrows()):
            rs    = row.get('RS_Score', 0)
            price = row.get('Current_Price', 0)
            sig   = str(row.get('Signal', ''))
            sig_color = '#00c853' if '🟢' in sig or 'BUY' in sig.upper() else '#ff5555'
            with col_st:
                st.markdown(f"""
                <div style="background:linear-gradient(135deg,#0f1528,#131829);
                     border:1px solid #1e2640;border-top:3px solid {color};
                     border-radius:12px;padding:16px;text-align:center;
                     box-shadow:0 2px 12px rgba(0,0,0,0.3);">
                  <div style="font-size:18px;font-weight:900;color:{color};letter-spacing:-.01em;">
                    {row['Ticker'].replace('.NS','')}
                  </div>
                  <div style="font-size:9px;color:#4a5470;margin:3px 0;text-transform:uppercase;letter-spacing:.04em">{row['Company'][:20]}</div>
                  <div style="font-size:22px;font-weight:800;color:#e4e8f0;margin:8px 0">₹{price:,.0f}</div>
                  <div style="font-size:11px;font-weight:700;color:{color}">Strength: {rs:+.1f}%</div>
                  <div style="font-size:9px;color:#3d4a60;margin-top:2px">RS Score vs Nifty</div>
                </div>
                """, unsafe_allow_html=True)

    st.markdown('<br>', unsafe_allow_html=True)

    st.markdown(f'<div class="sec-hdr" style="color:{color}">Portfolio Growth vs Nifty</div>', unsafe_allow_html=True)
    st.markdown('<div style="font-size:11px;color:#3d4a60;margin:-4px 0 10px 2px;">Blue line = this strategy. Orange dotted = just buying Nifty index. Bigger gap above = more profit.</div>', unsafe_allow_html=True)
    st.plotly_chart(
        chart_equity(eq, 'Portfolio_Value', S_MONTHLY, color, 'Benchmark_Value'),
        width='stretch',
    )

    if not ranks.empty:
        st.markdown(f'<div class="sec-hdr" style="color:{color}">All 50 Stocks — Ranked by Strength</div>', unsafe_allow_html=True)
        st.markdown('<div style="font-size:11px;color:#3d4a60;margin:-4px 0 10px 2px;">Top 5 (highlighted) = currently held. RS Score = how much it outperformed recently. Higher is better.</div>', unsafe_allow_html=True)
        tbl = ranks[['Rank', 'Ticker', 'Company', 'Current_Price',
                      'Return_%', 'RS_Score', 'Signal']].copy()
        tbl['Ticker']        = tbl['Ticker'].str.replace('.NS', '')
        tbl['Current_Price'] = tbl['Current_Price'].apply(lambda x: f'₹{x:,.2f}')
        tbl['Return_%']      = tbl['Return_%'].apply(lambda x: f'{x:+.2f}%')
        tbl['RS_Score']      = tbl['RS_Score'].apply(lambda x: f'{x:+.2f}%')
        tbl['Signal']        = tbl['Signal'].str.replace('🟢 ', '').str.replace('🔴 ', '')
        row_colors = [
            'rgba(124,156,255,0.10)' if i < 5 else 'rgba(15,21,40,0.8)'
            for i in range(len(tbl))
        ]
        st.plotly_chart(chart_plotly_table(tbl, [30, 80, 170, 80, 70, 70, 80],
                                           row_colors, score_col=None),
                        width='stretch')

    if reb is not None and not reb.empty:
        st.markdown(f'<div class="sec-hdr" style="color:{color}">Rebalance Log — What Changed Each Month</div>', unsafe_allow_html=True)
        st.markdown('<div style="font-size:11px;color:#3d4a60;margin:-4px 0 10px 2px;">Shows which stocks were bought/sold each month. Bought = new entrant. Sold = fell out of top 5.</div>', unsafe_allow_html=True)
        r = reb[['Date', 'Top5_Stocks', 'Stocks_Bought', 'Stocks_Sold', 'Portfolio_Value']].copy()
        r['Date']            = r['Date'].astype(str).str[:10]
        r['Portfolio_Value'] = r['Portfolio_Value'].apply(lambda x: f'₹{x:,.0f}')
        st.plotly_chart(chart_plotly_table(r.tail(12), score_col=None), width='stretch')

    st.markdown('<br>', unsafe_allow_html=True)
    _glossary_expander()


# ═══════════════════════════════════════════════════════════════════════════════
#  IPO EDGE PAGE
# ═══════════════════════════════════════════════════════════════════════════════

def render_ipo(i: dict):
    color  = THEME[S_IPO]['color']
    st.markdown(f'<div class="page-title" style="color:{color}">🚀 IPO Edge</div>'
                '<div class="page-sub">Buy newly listed stocks when they break out of their first base — early, before the crowd</div><br>',
                unsafe_allow_html=True)

    st.markdown(_explain_box(
        '<b>How it works:</b> When a stock lists on NSE, it often trades sideways for ~40 days (the "<b>base</b>"). '
        'Once it breaks above that base <b>with strong volume</b>, we enter. We exit when it drops below its '
        '10-day average or hits a hard stop. A partial profit is booked at +15% gain.',
        color
    ), unsafe_allow_html=True)

    eq     = i.get('equity')
    trades = i.get('trades')
    sigs   = i.get('signals', pd.DataFrame())

    mx   = _equity_metrics(eq, 'Portfolio_Value', 'Portfolio_Value') if eq is not None else {}
    n_bk = int((sigs['Signal'] == 'Live Breakout').sum()) if not sigs.empty else 0
    n_wz = int((sigs['Signal'] == 'Watch Zone').sum())   if not sigs.empty else 0
    n_tr = len(trades) if trades is not None else 0
    # IPO trades use 'Result' field (Win/Loss/Open) added in backtest
    if trades is not None and len(trades) and 'Result' in trades.columns:
        wr_str = f"{(trades['Result']=='Win').mean()*100:.0f}%"
    elif trades is not None and len(trades) and 'PnL_Pct' in trades.columns:
        closed = trades[trades.get('Status', pd.Series('Closed')) == 'Closed'] if 'Status' in trades.columns else trades
        wr_str = f"{(closed['PnL_Pct'] > 0).mean()*100:.0f}%" if len(closed) else '—'
    else:
        wr_str = '—'

    # Stage summary counts
    if not sigs.empty and 'Stage' in sigs.columns:
        n_s3 = int((sigs['Stage'] == 'Stage 3').sum())
        n_s2 = int((sigs['Stage'] == 'Stage 2').sum())
        n_s1 = int((sigs['Stage'] == 'Stage 1').sum())
        n_it = int((sigs['Stage'] == 'In Trade').sum())
    else:
        n_s3 = n_s2 = n_s1 = n_it = 0

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: st.markdown(pill('Avg Yearly Return', f"{mx['cagr']:+.1f}%" if mx else '—',
        f"Total: {mx['total_ret']:+.1f}%" if mx else '', color,
        'CAGR — average return per year since strategy started'), unsafe_allow_html=True)
    with c2: st.markdown(pill('Worst Loss Ever', f"{mx['max_dd']:.1f}%" if mx else '—',
        'Max drop from peak', '#ff5555',
        'Max Drawdown — biggest fall before recovering'), unsafe_allow_html=True)
    with c3: st.markdown(pill('Ready to Break Out 🟢', str(n_s3),
        f'Recovering: {n_s2} · Building: {n_s1}', color,
        'Stage 3 = breakout with volume. Stage 2 = recovering. Stage 1 = still forming base.'), unsafe_allow_html=True)
    with c4: st.markdown(pill('Currently In Trade', str(n_it),
        f'Live Breakout signals: {n_bk}', '#00bfa5',
        'Stocks currently held in an open position'), unsafe_allow_html=True)
    with c5: st.markdown(pill('Trades Won', wr_str,
        f'{n_tr} trades done · Watching: {n_wz}', '#8892a4',
        'Win Rate — % of closed trades that made a profit'), unsafe_allow_html=True)

    st.markdown('<br>', unsafe_allow_html=True)

    if eq is not None:
        st.markdown(f'<div class="sec-hdr" style="color:{color}">Backtest Equity Curve</div>', unsafe_allow_html=True)
        eq_col = 'Portfolio_Value' if 'Portfolio_Value' in eq.columns else 'Equity'
        bench  = 'Benchmark_Value' if 'Benchmark_Value' in eq.columns else None
        st.plotly_chart(chart_equity(eq, eq_col, S_IPO, color, bench), width='stretch')

    # ── Live signal table ──────────────────────────────────────────────────────
    st.markdown(f'<div class="sec-hdr" style="color:{color}">Live Screener — IPOs Listed in Last 12 Months</div>',
                unsafe_allow_html=True)
    st.markdown("""
    <div style="font-size:11px;color:#3d4a60;margin:-4px 0 10px 2px;">
      <b style="color:#6a748a">Signal guide:</b>
      &nbsp;<span style="color:#00c853">● Live Breakout</span> = buy signal now &nbsp;
      <span style="color:#f9c200">● Watch Zone</span> = almost ready, monitor closely &nbsp;
      <span style="color:#7c9cff">● Forming Base</span> = wait, not ready yet &nbsp;
      <span style="color:#ff5555">● Avoid</span> = broken, skip<br>
      <b style="color:#6a748a">Stage:</b> 3=Breakout 2=Recovering 1=Base In Trade=Held now &nbsp;·&nbsp;
      <b style="color:#6a748a">Vol Ratio:</b> >1.5× = strong volume (confirms breakout) &nbsp;·&nbsp;
      <b style="color:#6a748a">Score:</b> 0–10, higher = better quality setup
    </div>""", unsafe_allow_html=True)
    if sigs.empty:
        st.info('No data in ipo_data/ — run **ipo_edge_downloader.py** first.')
    else:
        # ── Enrich w/ historical analytics overlay ──────────────────────────
        try:
            ipo_report = _build_report(S_IPO)
            sigs = core_scorer.enrich_signals(
                sigs, ipo_report,
                feature_map={},  # no per-row features → use overall + regime fallback
            )
        except Exception:
            pass

        display_cols = [
            'Ticker', 'Company', 'Signal', 'Stage', 'Setup',
            'Close', 'Bk Level', 'vs Bk%', 'Vol Ratio',
            'IPO Day Val', 'Liquidity', 'Promoter', 'Listing PE',
            'Age (d)', 'Score', 'Hist Win%', 'Hist Avg%',
        ]
        disp = sigs[[c for c in display_cols if c in sigs.columns]].copy()

        # Row colour = stage colour (dimmed)
        def _stage_row_color(row):
            stage = row.get('Stage', '')
            sig   = row.get('Signal', '')
            if stage == 'Stage 3' or sig == 'Live Breakout':
                return 'rgba(0,200,83,0.10)'
            if stage == 'In Trade':
                return 'rgba(0,191,165,0.10)'
            if stage == 'Stage 2' or sig == 'Watch Zone':
                return 'rgba(249,194,0,0.08)'
            if sig == 'Avoid':
                return 'rgba(255,61,61,0.06)'
            return '#12172a'

        row_colors = [_stage_row_color(r) for _, r in sigs.iterrows()]

        disp['Close']       = disp['Close'].apply(lambda x: f'₹{x:,.2f}')
        disp['Bk Level']    = disp['Bk Level'].apply(lambda x: f'₹{x:,.2f}')
        disp['vs Bk%']      = disp['vs Bk%'].apply(lambda x: f'{x:+.1f}%')
        disp['Vol Ratio']   = disp['Vol Ratio'].apply(lambda x: f'{x:.2f}×')
        disp['IPO Day Val'] = disp['IPO Day Val'].apply(lambda x: f'₹{x:.1f} Cr')
        if 'Hist Win%' in disp.columns:
            disp['Hist Win%'] = disp['Hist Win%'].apply(lambda x: f'{x:.0f}%')
        if 'Hist Avg%' in disp.columns:
            disp['Hist Avg%'] = disp['Hist Avg%'].apply(lambda x: f'{x:+.1f}%')

        n_cols = len(disp.columns)
        widths = ([60, 130, 90, 80, 75, 60, 65, 55, 60, 80, 70, 75, 70, 50, 130, 60, 60])[:n_cols]
        st.plotly_chart(
            chart_plotly_table(disp, widths, row_colors, score_col='Score'),
            width='stretch',
        )
        st.caption(
            '📊 *Hist Win%* / *Hist Avg%* — overall historical IPO Edge win rate from closed trades.'
        )

    # ── Trade history ──────────────────────────────────────────────────────────
    if trades is not None and not trades.empty:
        st.markdown(f'<div class="sec-hdr" style="color:{color}">Trade History</div>', unsafe_allow_html=True)
        # IPO trades use Hold_Days → Holding_Days (fixed in backtest), Status, Result
        hold_col   = 'Holding_Days' if 'Holding_Days' in trades.columns else 'Hold_Days'
        result_col = 'Result' if 'Result' in trades.columns else None
        want_cols  = ['Ticker', 'Entry_Date', 'Entry_Price', 'Exit_Date',
                      'Exit_Price', 'PnL_Pct', hold_col, 'Exit_Reason', 'Status']
        if result_col:
            want_cols.append(result_col)
        extra = [c for c in ('Entry_Stage', 'Setup_Type', 'Partial_Booked', 'Liquidity_Status', 'Promoter_Backed')
                 if c in trades.columns]
        avail = [c for c in want_cols + extra if c in trades.columns]
        t = trades[avail].copy()
        t['Ticker']      = t['Ticker'].str.replace('.NS', '', regex=False)
        t['Entry_Price'] = t['Entry_Price'].apply(lambda x: f'₹{x:,.2f}')
        t['Exit_Price']  = t['Exit_Price'].apply(lambda x: f'₹{x:,.2f}')
        t['PnL_Pct']     = t['PnL_Pct'].apply(lambda x: f'{x:+.2f}%')
        if result_col and result_col in trades.columns:
            row_colors = ['rgba(0,200,83,0.08)' if r == 'Win' else
                          'rgba(136,146,164,0.05)' if r == 'Open' else
                          'rgba(255,61,61,0.06)'
                          for r in trades[result_col]]
        else:
            row_colors = ['rgba(0,200,83,0.08)' if p > 0 else 'rgba(255,61,61,0.06)'
                          for p in trades['PnL_Pct']]
        st.plotly_chart(chart_plotly_table(t, row_colors=row_colors, score_col=None),
                        width='stretch')


# ═══════════════════════════════════════════════════════════════════════════════
#  MOMENTUM EDGE PAGE
# ═══════════════════════════════════════════════════════════════════════════════

def render_momentum(mo: dict):
    color  = THEME[S_MOMENTUM]['color']
    st.markdown(
        f'<div class="page-title" style="color:{color}">📈 Momentum Edge</div>'
        '<div class="page-sub">Large/mid-cap stocks that dipped below their 220-day average, recovered, '
        'and are now breaking to new all-time highs — caught at the perfect moment.</div><br>',
        unsafe_allow_html=True,
    )

    # ── How it works callout ───────────────────────────────────────────────────
    st.markdown(_explain_box(
        '🧠 <b>How This Strategy Works (Plain English)</b><br>'
        'We look for strong NSE stocks that recently dipped below their long-term average (220-day line), '
        'then bounced back up — showing the dip was temporary, not a collapse. '
        'We only buy when the stock is also breaking to an <b>all-time high (ATH)</b>, meaning buyers are fully in control. '
        'We exit if the stock falls 15% from our buy price (hard stop) or breaks back below the 220-day average.',
        color,
    ), unsafe_allow_html=True)

    eq     = mo.get('equity')
    trades = mo.get('trades')
    sigs   = mo.get('signals', pd.DataFrame())

    mx     = _equity_metrics(eq, 'Equity', 'Equity') if eq is not None else {}
    n_bk   = int((sigs['Signal'] == 'Breakout Today').sum())  if not sigs.empty else 0
    n_near = int((sigs['Signal'] == 'Near Breakout').sum())   if not sigs.empty else 0
    n_wz   = int((sigs['Signal'] == 'Watch Zone').sum())      if not sigs.empty else 0
    n_tr   = len(trades) if trades is not None else 0
    wr_str = (f"{(trades['Result']=='Win').mean()*100:.0f}%"
              if trades is not None and len(trades) else '—')

    # ATH / clean chart counts
    if not sigs.empty:
        n_ath   = int((sigs.get('Entry Type', pd.Series()) == 'ATH').sum()) \
                  if 'Entry Type' in sigs.columns else 0
        n_clean = int((sigs.get('Chart Qual', pd.Series()) == 'Clean ✅').sum()) \
                  if 'Chart Qual' in sigs.columns else 0
        n_fast  = int(sigs.get('Recovery', pd.Series()).str.startswith('Fast').sum()) \
                  if 'Recovery' in sigs.columns else 0
    else:
        n_ath = n_clean = n_fast = 0

    # ── Key metric pills ───────────────────────────────────────────────────────
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.markdown(pill(
            'Annual Return (CAGR)',
            f"{mx['cagr']:+.1f}%" if mx else '—',
            f"Total gain: {mx['total_ret']:+.1f}%" if mx else '',
            color,
            explain='How much % the portfolio grew per year on average. Higher = better.',
        ), unsafe_allow_html=True)
    with c2:
        st.markdown(pill(
            'Worst Drawdown',
            f"{mx['max_dd']:.1f}%" if mx else '—',
            'Max peak-to-trough drop',
            '#ff3d3d',
            explain='Largest % drop from the portfolio peak at any point. -20% means ₹1L became ₹80K temporarily.',
        ), unsafe_allow_html=True)
    with c3:
        st.markdown(pill(
            'Breakout Today 🔥',
            str(n_bk),
            f'Near: {n_near} · Watch: {n_wz}',
            color,
            explain='Stocks crossing their all-time high TODAY — the strongest buy signal in this strategy.',
        ), unsafe_allow_html=True)
    with c4:
        st.markdown(pill(
            'ATH Entries 🎯',
            str(n_ath),
            f'Clean charts: {n_clean} · Fast recovery: {n_fast}',
            '#00bfa5',
            explain='Signals where the stock is at or very near its all-time high — the highest-quality setups.',
        ), unsafe_allow_html=True)
    with c5:
        st.markdown(pill(
            'Win Rate',
            wr_str,
            f'{n_tr} total trades',
            '#8892a4',
            explain='% of trades that made a profit. A 50%+ win rate with good avg gains = positive expectancy.',
        ), unsafe_allow_html=True)

    st.markdown('<br>', unsafe_allow_html=True)

    # ── Signal type legend ─────────────────────────────────────────────────────
    st.markdown("""
    <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:18px;">
      <div style="background:rgba(0,200,83,0.12);border:1px solid rgba(0,200,83,0.3);
           border-radius:20px;padding:5px 14px;font-size:12px;color:#00c853;font-weight:600;">
        🟢 Breakout Today — crossing ATH right now, strongest signal
      </div>
      <div style="background:rgba(249,194,0,0.10);border:1px solid rgba(249,194,0,0.3);
           border-radius:20px;padding:5px 14px;font-size:12px;color:#f9c200;font-weight:600;">
        🟡 Near Breakout — within 2% of ATH, ready to pop
      </div>
      <div style="background:rgba(124,156,255,0.08);border:1px solid rgba(124,156,255,0.25);
           border-radius:20px;padding:5px 14px;font-size:12px;color:#7c9cff;font-weight:600;">
        🔵 Watch Zone — good setup, wait for price to move up
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Equity curve ───────────────────────────────────────────────────────────
    if eq is not None:
        st.markdown(
            f'<div class="sec-hdr" style="color:{color}">Portfolio Growth — Backtest Result</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div style="font-size:12px;color:#5a6480;margin-bottom:10px;">'
            'This shows how ₹10 lakh invested at the start of the backtest would have grown over time '
            'following every signal from this strategy. Each peak = new all-time high for the portfolio. '
            'Dips = times the market corrected.'
            '</div>', unsafe_allow_html=True,
        )
        st.plotly_chart(chart_equity(eq, 'Equity', S_MOMENTUM, color), width='stretch')

    # ── Live signal table ──────────────────────────────────────────────────────
    st.markdown(
        f'<div class="sec-hdr" style="color:{color}">Live Screener — Today\'s Best Setups (sorted by Score)</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div style="font-size:12px;color:#5a6480;margin-bottom:6px;">'
        'These are the stocks that pass ALL filters of the strategy right now. '
        '<b>Score</b> = quality rank (higher = better setup). '
        '<b>Vol Ratio</b> = today\'s volume ÷ 20-day average (above 1.0× = above-normal buying activity). '
        '<b>Dist ATH%</b> = how far the current price is from the all-time high (negative = below ATH).'
        '</div>', unsafe_allow_html=True,
    )

    # Column guide chips
    st.markdown("""
    <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px;font-size:11px;">
      <span style="background:#1e2235;border-radius:4px;padding:3px 10px;color:#7c9cff;">
        📊 Score = overall signal quality rank
      </span>
      <span style="background:#1e2235;border-radius:4px;padding:3px 10px;color:#00bfa5;">
        🎯 Entry Type: ATH = all-time high breakout (best) | 52W = 52-week high
      </span>
      <span style="background:#1e2235;border-radius:4px;padding:3px 10px;color:#f9c200;">
        📉 Chart Qual: Clean ✅ = no big sideways chop in chart
      </span>
      <span style="background:#1e2235;border-radius:4px;padding:3px 10px;color:#c0c0c0;">
        ⚡ Recovery: Fast = bounced quickly after the dip
      </span>
    </div>
    """, unsafe_allow_html=True)

    if sigs.empty:
        st.markdown(_tip_box(
            '💡 No signals found today. Run <code>momentum_edge_downloader.py</code> to pull fresh market data. '
            'Signals appear when a stock passes all 8 filters simultaneously — this is intentionally selective.'
        ), unsafe_allow_html=True)
    else:
        # ── Enrich w/ historical analytics overlay ──────────────────────────
        try:
            me_report = _build_report(S_MOMENTUM)
            sigs = core_scorer.enrich_signals(
                sigs, me_report,
                feature_map={'Entry Type': 'Entry_Type', 'Recovery': 'Recovery_Speed'},
            )
        except Exception:
            pass

        display_cols = [
            'Ticker', 'Company', 'Signal',
            'Close', 'ATH (₹)', 'Dist ATH%',
            'Entry Type', 'Chart Qual', 'Choppiness',
            'Recovery', '220 EMA', '52W High', 'vs High%', 'Vol Ratio',
            'Score', 'Hist Win%', 'Hist Avg%',
        ]
        disp = sigs[[c for c in display_cols if c in sigs.columns]].copy()

        sig_color_map = {
            'Breakout Today': 'rgba(0,200,83,0.10)',
            'Near Breakout':  'rgba(249,194,0,0.09)',
            'Watch Zone':     'rgba(124,156,255,0.07)',
            'Watchlist':      'rgba(136,146,164,0.05)',
        }
        row_colors = [sig_color_map.get(s, '#12172a') for s in sigs['Signal']]

        for c in ('Close', 'ATH (₹)', '220 EMA', '52W High'):
            if c in disp.columns:
                disp[c] = disp[c].apply(lambda x: f'₹{x:,.2f}')
        if 'Dist ATH%' in disp.columns:
            disp['Dist ATH%'] = disp['Dist ATH%'].apply(lambda x: f'{x:+.1f}%')
        if 'vs High%' in disp.columns:
            disp['vs High%']  = disp['vs High%'].apply(lambda x: f'{x:+.1f}%')
        if 'Vol Ratio' in disp.columns:
            disp['Vol Ratio'] = disp['Vol Ratio'].apply(lambda x: f'{x:.2f}×')
        if 'Hist Win%' in disp.columns:
            disp['Hist Win%'] = disp['Hist Win%'].apply(lambda x: f'{x:.0f}%')
        if 'Hist Avg%' in disp.columns:
            disp['Hist Avg%'] = disp['Hist Avg%'].apply(lambda x: f'{x:+.1f}%')

        n_cols = len(disp.columns)
        widths = ([60, 130, 90, 65, 70, 65, 65, 65, 65, 75, 65, 65, 55, 55, 130, 60, 60])[:n_cols]
        st.plotly_chart(
            chart_plotly_table(disp, widths, row_colors, score_col='Score'),
            width='stretch',
        )
        st.caption(
            '📊 *Hist Win%* / *Hist Avg%* — historical performance of past trades '
            'with the same Entry Type + Recovery Speed combo. Based on closed backtest trades only.'
        )

        # ── Signal Detail Drawer (pick ticker → candle chart + overlays) ───────
        st.markdown('<br>', unsafe_allow_html=True)
        st.markdown(f'<div class="sec-hdr" style="color:{color}">🔍 Drill Into Any Signal</div>',
                    unsafe_allow_html=True)
        st.caption('Pick a stock to see the price chart with SMA50, EMA220, 52W high/low and past trades overlaid.')

        ticker_choices = sigs['Ticker'].tolist()
        if ticker_choices:
            sel = st.selectbox('Ticker', ticker_choices, key='me_detail_picker',
                               label_visibility='collapsed')
            try:
                _render_me_detail(sel, trades)
            except Exception as e:
                st.warning(f'Could not render chart: {e}')

    # ── How to read the screener ───────────────────────────────────────────────
    with st.expander('📖 How to read this screener — what each column means'):
        st.markdown("""
        | Column | Plain-English Meaning |
        |---|---|
        | **Signal** | Breakout Today = best, Near Breakout = almost there, Watch Zone = monitor |
        | **Close** | Today's last traded price |
        | **ATH (₹)** | All-Time High price — the highest this stock has ever traded |
        | **Dist ATH%** | How far today's price is from the all-time high. 0% = AT the all-time high |
        | **Entry Type** | ATH = breaking all-time high · 52W = breaking 52-week high (second best) |
        | **Chart Qual** | Clean ✅ = chart looks tidy, no messy sideways action (Choppiness < 55) |
        | **Choppiness** | 0–100 score. Below 55 = trending. Above 62 = choppy/sideways — avoid |
        | **Recovery** | Fast = bounced back from dip in <30 days · Slow = took longer |
        | **220 EMA** | The long-term average price (220 days). Stock must be above this to qualify |
        | **Vol Ratio** | Today's volume ÷ 20-day average. Above 1.5× = strong buying interest |
        | **Score** | Overall quality score (0–10). Higher = better setup. Sort by this to prioritise |
        """)

    # ── Trade history ──────────────────────────────────────────────────────────
    if trades is not None and not trades.empty:
        st.markdown('<br>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="sec-hdr" style="color:{color}">Past Trades — Every Entry & Exit</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div style="font-size:12px;color:#5a6480;margin-bottom:10px;">'
            'Green row = trade made a profit. Red = trade was a loss. '
            '<b>Exit Reason</b> tells you why we sold: '
            '"15% Hard Stop" = cut loss before it got worse · '
            '"220 EMA break" = stock fell below its long-term average · '
            '"Target" = hit profit target.'
            '</div>', unsafe_allow_html=True,
        )
        base_cols = ['Ticker', 'Entry_Date', 'Entry_Price', 'Exit_Date',
                     'Exit_Price', 'PnL_Pct', 'Holding_Days', 'Exit_Reason', 'Result']
        extra = [c for c in ('Entry_Type', 'Recovery_Speed', 'Recovery_Days')
                 if c in trades.columns]
        t = trades[base_cols + extra].copy()
        t['Ticker']      = t['Ticker'].str.replace('.NS', '')
        t['Entry_Price'] = t['Entry_Price'].apply(lambda x: f'₹{x:,.2f}')
        t['Exit_Price']  = t['Exit_Price'].apply(lambda x: f'₹{x:,.2f}')
        t['PnL_Pct']     = t['PnL_Pct'].apply(lambda x: f'{x:+.2f}%')
        row_colors = ['rgba(0,200,83,0.08)' if r == 'Win' else 'rgba(255,61,61,0.06)'
                      for r in trades['Result']]
        st.plotly_chart(chart_plotly_table(t, row_colors=row_colors, score_col=None),
                        width='stretch')

    # ── Glossary ───────────────────────────────────────────────────────────────
    st.markdown('<br>', unsafe_allow_html=True)
    _glossary_expander()


# ═══════════════════════════════════════════════════════════════════════════════
#  INSIGHTS PAGE
# ═══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=3600)
def _load_ohlcv_cached(folder: str, min_bars: int, skip: tuple[str, ...]) -> dict:
    """Thin Streamlit cache wrapper around core.data_io.load_ohlcv."""
    ohlcv, _ = core_data_io.load_ohlcv(folder, min_bars=min_bars, skip=set(skip))
    return ohlcv


@st.cache_data(ttl=3600)
def _load_benchmark_cached(folder: str) -> pd.Series | None:
    return core_data_io.load_benchmark(folder, ['^NSEI', 'NIFTYBEES.NS'])


def _benchmark_first(*folders: str) -> pd.Series | None:
    """Return first non-empty benchmark from the given folders. Series-safe (no `or`)."""
    for f in folders:
        s = _load_benchmark_cached(f)
        if s is not None and not s.empty:
            return s
    return None


@st.cache_data(ttl=3600)
def _build_report(strategy: str) -> dict:
    """Build analytics.full_report for a given strategy. Cached 1h."""
    if strategy == S_MOMENTUM:
        ohlcv = _load_ohlcv_cached('data/nse_bse', 10, ('^NSEI', 'NIFTYBEES.NS'))
        if not ohlcv:
            ohlcv = _load_ohlcv_cached('data', 10, ('^NSEI', 'NIFTYBEES.NS'))
        bench = _benchmark_first('data/nse_bse', 'data')
        return core_analytics.full_report('momentum_edge_trades.csv', ohlcv, bench)
    if strategy == S_IPO:
        ohlcv = _load_ohlcv_cached('ipo_data', 5, ('NIFTYBEES.NS', 'ipo_summary'))
        bench = _benchmark_first('data/nse_bse', 'data')
        return core_analytics.full_report('ipo_edge_trades.csv', ohlcv, bench)
    if strategy == S_MONTHLY:
        trades = core_rotation_trades.build('rebalance_log.csv', 'data')
        ohlcv = core_rotation_trades.build_pseudo_ohlcv('data')
        bench = _benchmark_first('data', 'data/nse_bse')
        return core_analytics.full_report_from_df(trades, ohlcv, bench)
    return {}


def _kpi_card(label: str, value: str, sub: str = '', color: str = '#7c9cff') -> None:
    st.markdown(
        f"""
        <div style="background:rgba(255,255,255,0.02);border:1px solid #1f2533;
                    border-radius:10px;padding:14px 16px;">
          <div style="font-size:10px;letter-spacing:.08em;color:#6a748a;
                      text-transform:uppercase;">{label}</div>
          <div style="font-size:24px;font-weight:800;color:{color};margin-top:4px;">{value}</div>
          <div style="font-size:11px;color:#3d4a60;margin-top:2px;">{sub}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_strategy_insights(strategy: str, report: dict) -> None:
    if not report or report.get('trades') is None or report['trades'].empty:
        st.info(f'No trade data for {strategy} yet. Run the backtest first.')
        return

    color = THEME[strategy]['color']
    trades_x = report['trades']
    n = len(trades_x)

    # ── Header KPIs ─────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        _kpi_card('Total Trades', f'{n}', 'closed positions', color)
    with c2:
        wr = report.get('overall_win_rate', 0)
        _kpi_card('Win Rate', f'{wr}%', 'profitable trades', color)
    with c3:
        _kpi_card('Avg PnL', f'{report.get("overall_avg_pnl", 0):+.2f}%', 'per trade', color)
    with c4:
        _kpi_card('Median PnL', f'{report.get("overall_median", 0):+.2f}%', 'half above/below', color)

    st.markdown('<div style="height:18px;"></div>', unsafe_allow_html=True)

    # ── Optimal Entry — by entry features ──────────────────────────────────
    st.markdown('### 🎯 Optimal Entry — what predicts winners?')
    st.caption('Win rate and average PnL grouped by entry feature. Larger Count = more reliable signal.')

    cols = st.columns(2)
    with cols[0]:
        df = report.get('by_entry_type', pd.DataFrame())
        if not df.empty:
            st.markdown('**By Entry Type**')
            st.dataframe(df, hide_index=True, width='stretch')
    with cols[1]:
        df = report.get('by_recovery_speed', pd.DataFrame())
        if not df.empty:
            st.markdown('**By Recovery Speed**')
            st.dataframe(df, hide_index=True, width='stretch')

    df = report.get('by_regime', pd.DataFrame())
    if not df.empty and (df['Regime_At_Entry'] != 'Unknown').any():
        st.markdown('**By Market Regime at Entry**')
        st.caption('Bull = all 3 Nifty regime conditions on. Bear = at least one off.')
        st.dataframe(df, hide_index=True, width='stretch')

    df = report.get('by_score_bucket', pd.DataFrame())
    if not df.empty:
        st.markdown('**By Setup Score (quintiles)**')
        st.caption('Higher buckets = stronger setups at entry. Look for a monotonic win-rate ladder.')
        st.dataframe(df, hide_index=True, width='stretch')

    st.markdown('<div style="height:18px;"></div>', unsafe_allow_html=True)

    # ── Optimal Sell — partial booking sensitivity ─────────────────────────
    st.markdown('### 💰 Optimal Sell — when to take profits?')
    st.caption(
        'For each candidate partial-booking level, how many trades touched it, '
        'how many faded back below it, and what trades finally averaged.'
    )
    df = report.get('partial_levels', pd.DataFrame())
    if not df.empty:
        st.dataframe(df, hide_index=True, width='stretch')
        best = df.loc[df['Fade_Rate'].idxmin()] if len(df) else None
        if best is not None:
            st.success(
                f'📌 Lowest fade rate: **+{int(best["Level_Pct"])}%** level '
                f'({best["Fade_Rate"]}% fade, avg final +{best["Avg_Final"]}%). '
                'Compare against the strategy\'s current partial spec.'
            )

    st.markdown('**Hold-day Curve** — PnL by holding-period bucket')
    df = report.get('hold_curve', pd.DataFrame())
    if not df.empty:
        st.dataframe(df, hide_index=True, width='stretch')

    st.markdown('<div style="height:18px;"></div>', unsafe_allow_html=True)

    # ── Loss Avoidance — stop loss recommendation ──────────────────────────
    st.markdown('### 🛡️ Loss Avoidance — where to set the stop?')
    rec = report.get('stop_recommendation', {})
    if rec:
        cc = st.columns(4)
        with cc[0]:
            _kpi_card('Winner MAE p95',
                      f'{rec.get("winner_mae_p95", "—")}%',
                      'most winners survive', '#00c853')
        with cc[1]:
            _kpi_card('Winner MAE mean',
                      f'{rec.get("winner_mae_mean", "—")}%',
                      'avg deepest dip', '#00c853')
        with cc[2]:
            _kpi_card('Loser MAE p95',
                      f'{rec.get("loser_mae_p95", "—")}%',
                      'typical loser depth', '#e85a8c')
        with cc[3]:
            _kpi_card('Loser MAE mean',
                      f'{rec.get("loser_mae_mean", "—")}%',
                      'avg loser depth', '#e85a8c')

        st.caption(
            'Read: set the stop *just above* the Winner MAE p95 line — '
            'tight enough to cut losses, loose enough that most eventual '
            'winners do not get stopped out on a normal pullback.'
        )

    cl = report.get('loss_clusters', {})
    if cl:
        cc = st.columns(3)
        with cc[0]:
            _kpi_card('Max Consecutive Losses', f'{cl.get("max_consecutive_losses", 0)}',
                      'worst losing streak', '#e85a8c')
        with cc[1]:
            _kpi_card('Avg Streak Length', f'{cl.get("avg_consecutive_losses", 0)}',
                      'typical losing run', '#6a748a')
        with cc[2]:
            _kpi_card('Total Losses', f'{cl.get("total_losses", 0)}',
                      f'of {n} trades', '#6a748a')

    st.markdown('<div style="height:18px;"></div>', unsafe_allow_html=True)

    # ── Best Hold Period — when to take the win ────────────────────────────
    st.markdown('### ⏱️ Best Hold Period — how long to stay in')
    oh = report.get('optimal_hold', {})
    if oh and oh.get('best_return_bucket'):
        br = oh['best_return_bucket']
        bw = oh['best_winrate_bucket']
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(
                f"""
                <div style="background:rgba(0,200,83,0.08);border:1px solid rgba(0,200,83,0.35);
                            border-left:4px solid #00c853;border-radius:10px;padding:14px 16px;">
                  <div style="font-size:10px;color:#6a748a;letter-spacing:.08em;text-transform:uppercase;">
                    Best for big returns
                  </div>
                  <div style="font-size:22px;font-weight:800;color:#00c853;margin-top:4px;">
                    Hold {br['bucket']} days
                  </div>
                  <div style="font-size:12px;color:#a0b0cc;margin-top:6px;">
                    Won {br['win_rate']:.0f}% of the time · Averaged
                    <b style="color:#e4e8f0">{br['avg_pnl']:+.1f}%</b> per trade
                  </div>
                  <div style="font-size:11px;color:#6a748a;margin-top:4px;">
                    Based on {br['count']} past trades
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with c2:
            st.markdown(
                f"""
                <div style="background:rgba(124,156,255,0.08);border:1px solid rgba(124,156,255,0.35);
                            border-left:4px solid #7c9cff;border-radius:10px;padding:14px 16px;">
                  <div style="font-size:10px;color:#6a748a;letter-spacing:.08em;text-transform:uppercase;">
                    Safest profit
                  </div>
                  <div style="font-size:22px;font-weight:800;color:#7c9cff;margin-top:4px;">
                    Hold {bw['bucket']} days
                  </div>
                  <div style="font-size:12px;color:#a0b0cc;margin-top:6px;">
                    Won <b style="color:#e4e8f0">{bw['win_rate']:.0f}%</b> · Averaged
                    {bw['avg_pnl']:+.1f}% per trade
                  </div>
                  <div style="font-size:11px;color:#6a748a;margin-top:4px;">
                    Best historical hit-rate ({bw['count']} trades)
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    sh = report.get('safe_hold', {})
    if sh and sh.get('safe_bucket'):
        sb = sh['safe_bucket']
        stop = sh.get('stop_pct', 15.0)
        st.markdown(
            f"""
            <div style="background:rgba(249,194,0,0.06);border:1px solid rgba(249,194,0,0.3);
                        border-radius:10px;padding:12px 16px;margin-top:14px;font-size:13px;">
              🛟 <b style="color:#f9c200">Safe Hold Window</b> —
              Holding for <b style="color:#e4e8f0">{sb['bucket']} days</b> kept
              average losses to <b style="color:#e4e8f0">{sb['avg_loser']:+.1f}%</b>,
              within the {stop:.0f}% hard-stop budget.
              {len(sh.get('all_safe_buckets', []))} of {len(sh.get('all_buckets', []))} hold
              buckets historically stayed inside the stop.
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Full curve for transparency
    with st.expander('Full hold-day breakdown'):
        st.dataframe(report.get('hold_curve', pd.DataFrame()),
                     hide_index=True, width='stretch')

    st.markdown('<div style="height:18px;"></div>', unsafe_allow_html=True)

    # ── Per-ticker history ─────────────────────────────────────────────────
    th = report.get('ticker_history', pd.DataFrame())
    if not th.empty:
        st.markdown('### 📜 Past Stocks — which tickers earned/lost the most')
        st.caption('Every closed trade aggregated by stock. Total_PnL = sum of all PnL% from this ticker.')

        c1, c2 = st.columns(2)
        with c1:
            st.markdown('**🏆 Top 10 winners (by total return)**')
            st.dataframe(th.head(10), hide_index=True, width='stretch')
        with c2:
            losers = th.sort_values('Total_PnL').head(10)
            st.markdown('**💀 Top 10 losers**')
            st.dataframe(losers, hide_index=True, width='stretch')

        with st.expander(f'All {len(th)} traded tickers'):
            st.dataframe(th, hide_index=True, width='stretch')

    st.markdown('<div style="height:18px;"></div>', unsafe_allow_html=True)

    # ── Trade-level MAE/MFE table (collapsed) ──────────────────────────────
    with st.expander('🔍 Full trade table with MAE / MFE'):
        show_cols = [c for c in [
            'Ticker', 'Entry_Date', 'Exit_Date', 'PnL_Pct',
            'MAE_Pct', 'MFE_Pct', 'Time_To_MAE', 'Time_To_MFE',
            'Holding_Days', 'Exit_Reason', 'Result',
        ] if c in trades_x.columns]
        st.dataframe(
            trades_x[show_cols].sort_values('Exit_Date', ascending=False),
            hide_index=True, width='stretch',
        )


@st.cache_data(ttl=3600)
def _regime_snapshot() -> dict:
    """Compute Nifty regime state for top-of-page banner.

    Returns dict with keys: status ('Bull'/'Bear'/'Unknown'), bars_since_flip,
    close, sma50, sma200, high52, pct_from_high.
    """
    bench = _benchmark_first('data/nse_bse', 'data')
    if bench is None or len(bench) < 200:
        return {'status': 'Unknown', 'bars_since_flip': 0}

    series = core_regime.build_series(bench, {'use_regime_filter': True})
    if series is None or series.empty:
        return {'status': 'Unknown', 'bars_since_flip': 0}

    state_now = bool(series.dropna().iloc[-1])
    return {
        'status':          'Bull' if state_now else 'Bear',
        'bars_since_flip': core_regime.bars_since_flip(series),
        'close':           round(float(bench.iloc[-1]), 2),
        'sma50':           round(float(bench.rolling(50).mean().iloc[-1]), 2),
        'sma200':          round(float(bench.rolling(200).mean().iloc[-1]), 2),
        'high52':          round(float(bench.rolling(252).max().iloc[-1]), 2),
        'pct_from_high':   round((float(bench.iloc[-1]) / float(bench.rolling(252).max().iloc[-1]) - 1) * 100, 2),
        'date':            str(bench.index[-1].date()),
    }


def _render_regime_banner() -> None:
    """Persistent Nifty regime banner shown above every page."""
    snap = _regime_snapshot()
    status = snap.get('status', 'Unknown')

    if status == 'Bull':
        bg, border, accent, icon, msg = (
            'rgba(0,200,83,0.10)', 'rgba(0,200,83,0.45)', '#00c853',
            '🟢', 'BULL — all 3 regime conditions on. New entries allowed.',
        )
    elif status == 'Bear':
        bg, border, accent, icon, msg = (
            'rgba(232,90,140,0.10)', 'rgba(232,90,140,0.45)', '#e85a8c',
            '🔴', 'BEAR / SIDEWAYS — at least one regime condition has failed.',
        )
    else:
        bg, border, accent, icon, msg = (
            'rgba(124,156,255,0.08)', 'rgba(124,156,255,0.35)', '#7c9cff',
            '⚪', 'Regime unknown — benchmark data unavailable.',
        )

    bars = snap.get('bars_since_flip', 0)
    extras = ''
    if snap.get('close'):
        extras = (
            f'<span style="margin-left:18px;color:#6a748a;">'
            f'Nifty <b style="color:#e4e8f0">{snap["close"]:,}</b> · '
            f'SMA50 <b style="color:#e4e8f0">{snap["sma50"]:,}</b> · '
            f'SMA200 <b style="color:#e4e8f0">{snap["sma200"]:,}</b> · '
            f'{snap["pct_from_high"]:+.1f}% from 52W high · '
            f'{snap["date"]}</span>'
        )

    st.markdown(
        f"""
        <div style="background:{bg};border:1px solid {border};
                    border-left:4px solid {accent};border-radius:10px;
                    padding:10px 16px;margin-bottom:18px;
                    display:flex;align-items:center;font-size:13px;">
          <span style="font-size:18px;margin-right:10px;">{icon}</span>
          <b style="color:{accent};letter-spacing:.03em;">{msg}</b>
          <span style="margin-left:14px;color:#6a748a;">
            {bars} bars since last flip
          </span>
          {extras}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_insights(m: dict, i: dict, mo: dict) -> None:
    st.markdown(
        '<h1 style="margin:0 0 6px 0;font-size:30px;font-weight:900;letter-spacing:-.02em;">'
        '🔬 Insights</h1>',
        unsafe_allow_html=True,
    )
    st.caption('Post-hoc analytics on closed trades — entry quality, exit timing, stop placement.')

    tab_me, tab_ipo, tab_rot = st.tabs(
        ['📈 Momentum Edge', '🚀 IPO Edge', '🔄 Monthly Rotation']
    )

    with tab_me:
        with st.spinner('Building Momentum Edge report…'):
            report = _build_report(S_MOMENTUM)
        _render_strategy_insights(S_MOMENTUM, report)

    with tab_ipo:
        with st.spinner('Building IPO Edge report…'):
            report = _build_report(S_IPO)
        _render_strategy_insights(S_IPO, report)

    with tab_rot:
        st.caption(
            'Rotation has no native per-trade log — trades are synthesized by '
            'walking the monthly rebalance log. Each Stocks_Bought entry is paired '
            'with its next Stocks_Sold appearance to form a round-trip.'
        )
        with st.spinner('Building Rotation report…'):
            report = _build_report(S_MONTHLY)
        _render_strategy_insights(S_MONTHLY, report)


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    page = render_sidebar()
    core_glossary.render_sidebar(st)

    with st.spinner('Loading data…'):
        m  = load_monthly()
        i  = load_ipo()
        mo = load_momentum()

    _render_regime_banner()

    page_clean = page.split('  ', 1)[-1] if '  ' in page else page.lstrip('🏠🔄🚀📈📊 ')

    if 'Home' in page:
        render_home(m, i, mo)
    elif 'Monthly' in page:
        render_monthly(m)
    elif 'IPO' in page:
        render_ipo(i)
    elif 'Momentum' in page:
        render_momentum(mo)
    elif 'Insights' in page:
        render_insights(m, i, mo)
    elif 'History' in page:
        render_history(m, i, mo)


if __name__ == '__main__':
    main()
