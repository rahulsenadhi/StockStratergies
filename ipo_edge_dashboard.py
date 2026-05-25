"""
IPO Edge Strategy — Live Screener Dashboard
Shows all qualifying NSE IPO candidates with breakout signals and 3-stage pattern.

Run: streamlit run ipo_edge_dashboard.py
(Run ipo_edge_downloader.py first for cached data,
 or click Refresh to fetch live data directly.)
"""

import os
import sys
import warnings
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

warnings.filterwarnings('ignore')

# ═══════════════════════════════════════════════════════════════════════════════
#  CONFIG
# ═══════════════════════════════════════════════════════════════════════════════

DATA_FOLDER          = 'ipo_data'
BENCHMARK            = 'NIFTYBEES.NS'
LISTING_AGE_MAX      = 365
SKIP_DAYS            = 3
BASE_WINDOW          = 40
MIN_DAYS             = 43
EMA_PERIOD           = 10
VOL_MULTIPLIER       = 1.5
ALLOC_PER_STOCK      = 10_000
MEMORY_FILE          = 'MEMORY.md'
MIN_IPO_DAY_VALUE_CR = 10
PROMOTER_FILE        = 'ipo_promoter_quality.csv'

NSE_IPO_UNIVERSE = {
    'PREMIERENE.NS':  'Premier Energies',
    'KROSS.NS':       'Kross Limited',
    'BAJAJHFL.NS':    'Bajaj Housing Finance',
    'MANBA.NS':       'Manba Finance',
    'GARUDA.NS':      'Garuda Construction',
    'WAAREEENER.NS':  'Waaree Energies',
    'HYUNDAI.NS':     'Hyundai Motor India',
    'SWIGGY.NS':      'Swiggy',
    'SAGILITY.NS':    'Sagility India',
    'NTPCGREEN.NS':   'NTPC Green Energy',
    'AFCONS.NS':      'Afcons Infrastructure',
    'MOBIKWIK.NS':    'MobiKwik',
    'DOMS.NS':        'DOMS Industries',
    'HEXAWARE.NS':    'Hexaware Technologies',
    'STALLION.NS':    'Stallion India Fluorochemicals',
    'SEPC.NS':        'SEPC Limited',
}

SIGNAL_ORDER  = ['Live Breakout', 'Watch Zone', 'Forming Base', 'Too New', 'Avoid']
SIGNAL_COLORS = {
    'Live Breakout': '#00c853',
    'Watch Zone':    '#f9c200',
    'Forming Base':  '#7c9cff',
    'Too New':       '#8892a4',
    'Avoid':         '#ff3d3d',
}
SIGNAL_BG = {
    'Live Breakout': 'rgba(0,200,83,0.09)',
    'Watch Zone':    'rgba(249,194,0,0.09)',
    'Forming Base':  'rgba(124,156,255,0.07)',
    'Too New':       'rgba(136,146,164,0.05)',
    'Avoid':         'rgba(255,61,61,0.05)',
}

# ── 3-Stage pattern constants ─────────────────────────────────────────────────
STAGE_ORDER = ['Stage 3', 'In Trade', 'Stage 2', 'Stage 1', 'Failed', 'Too Early']
STAGE_COLORS = {
    'Stage 3':   '#00c853',
    'In Trade':  '#00e5ff',
    'Stage 2':   '#f9c200',
    'Stage 1':   '#7c9cff',
    'Failed':    '#ff3d3d',
    'Too Early': '#8892a4',
}
STAGE_BG = {
    'Stage 3':   'rgba(0,200,83,0.12)',
    'In Trade':  'rgba(0,229,255,0.08)',
    'Stage 2':   'rgba(249,194,0,0.10)',
    'Stage 1':   'rgba(124,156,255,0.08)',
    'Failed':    'rgba(255,61,61,0.07)',
    'Too Early': 'rgba(136,146,164,0.04)',
}
STAGE_LABELS = {
    'Stage 3':   'Stage 3 — Breakout Ready 🟢',
    'In Trade':  'In Trade ✅',
    'Stage 2':   'Stage 2 — Reclaiming 🟡',
    'Stage 1':   'Stage 1 — Building Base 🔵',
    'Failed':    'Failed ❌',
    'Too Early': 'Too Early',
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ═══════════════════════════════════════════════════════════════════════════════
#  PAGE CONFIG + CSS
# ═══════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title='IPO Edge — Live Screener',
    page_icon='🚀',
    layout='wide',
    initial_sidebar_state='collapsed',
)

st.markdown("""<style>
.main .block-container { padding-top: 0.7rem; padding-bottom: 1rem; max-width: 1440px; }
#MainMenu, footer, header { visibility: hidden; }

.metric-card {
    background: linear-gradient(135deg, #151927 0%, #1c2138 100%);
    border-radius: 10px; padding: 14px 16px; border: 1px solid #242d47;
    text-align: center; height: 90px; display: flex; flex-direction: column;
    justify-content: center;
}
.mv  { font-size: 1.65rem; font-weight: 700; line-height: 1.15; }
.ml  { font-size: 0.68rem; color: #6e7a90; text-transform: uppercase;
       letter-spacing: 0.07em; margin-top: 3px; }
.ml2 { font-size: 0.64rem; color: #6e7a90; margin-top: 2px; }

.stage-bar {
    background: #0d1121; border: 1px solid #242d47; border-radius: 10px;
    padding: 12px 18px; margin-bottom: 14px;
    display: flex; align-items: center; gap: 24px; flex-wrap: wrap;
}
.stage-pill {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 5px 14px; border-radius: 20px; font-size: 0.75rem; font-weight: 700;
    letter-spacing: 0.04em;
}
.stage-pill .cnt { font-size: 1.1rem; font-weight: 800; }

.breakout-card {
    background: #121623; border-radius: 11px; padding: 13px 14px;
    border: 1px solid #242d47; height: 215px; position: relative;
}
.bc-rank  { font-size: 0.62rem; color: #6e7a90; text-transform: uppercase; letter-spacing: 0.08em; }
.bc-co    { font-size: 0.82rem; font-weight: 600; color: #dde4f0; margin: 3px 0 1px; line-height: 1.2; }
.bc-tk    { font-size: 0.66rem; color: #6e7a90; margin-bottom: 5px; }
.bc-rs    { font-size: 1.2rem; font-weight: 700; line-height: 1; }
.bc-sub   { font-size: 0.63rem; color: #6e7a90; margin-top: 1px; }
.bc-price { font-size: 0.73rem; color: #8a96aa; margin-top: 5px; }
.bc-sig   { font-size: 0.62rem; padding: 2px 7px; border-radius: 4px;
            margin-top: 5px; display: inline-block; font-weight: 500; }
.bc-tags  { font-size: 0.62rem; color: #6e7a90; margin-top: 5px; line-height: 1.6; }

.sec-hdr { font-size: 0.7rem; font-weight: 700; color: #6e7a90;
           text-transform: uppercase; letter-spacing: 0.08em;
           padding-bottom: 6px; border-bottom: 1px solid #242d47; margin-bottom: 10px; }

.warn-box {
    background: rgba(249,194,0,0.08); border: 1px solid rgba(249,194,0,0.3);
    border-radius: 8px; padding: 8px 12px; font-size: 0.72rem; color: #c8a400;
    margin-bottom: 10px;
}
</style>""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  QUALITY FILTER HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=3600)
def _load_promoter_quality() -> tuple[dict, bool]:
    path = Path(BASE_DIR) / PROMOTER_FILE
    if not path.exists():
        return {}, False
    try:
        df = pd.read_csv(path)
        result = {}
        for _, row in df.iterrows():
            sym = str(row.get('Symbol', '')).strip().upper()
            if sym:
                backed = str(row.get('PromoterBacked', 'Unknown')).strip().upper()
                if backed not in ('YES', 'NO'):
                    backed = 'Unknown'
                result[sym] = {
                    'PromoterBacked': backed,
                    'Notes':          str(row.get('Notes', '')).strip(),
                }
        return result, True
    except Exception:
        return {}, False


@st.cache_data(ttl=3600)
def _get_listing_pe(ticker: str) -> float | None:
    try:
        info = yf.Ticker(ticker).info
        pe   = info.get('trailingPE') or info.get('forwardPE')
        if pe is not None and float(pe) > 0:
            return round(float(pe), 1)
        return None
    except Exception:
        return None


def _pe_color(pe: float | None) -> str:
    if pe is None:
        return '#6e7a90'
    if pe < 20:
        return '#00c853'
    if pe <= 40:
        return '#f9c200'
    return '#ff9800'


def _liquidity_label(value_cr: float) -> str:
    if value_cr >= MIN_IPO_DAY_VALUE_CR:
        return f'✅ Liquid (₹{value_cr:.1f}Cr)'
    return f'❌ Low Liq (₹{value_cr:.1f}Cr)'


def _promoter_label(backed: str) -> str:
    if backed == 'YES':
        return 'YES ✅'
    if backed == 'NO':
        return 'NO ❌'
    return 'Unknown ⚪'


# ═══════════════════════════════════════════════════════════════════════════════
#  CORE STRATEGY HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def compute_ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def compute_base(df: pd.DataFrame) -> dict | None:
    """Same logic as ipo_edge_backtest.py — kept in sync."""
    if len(df) < MIN_DAYS:
        return None
    base_slice   = df.iloc[SKIP_DAYS: SKIP_DAYS + BASE_WINDOW]
    vol_clean    = base_slice['Volume'].replace(0, np.nan).dropna()
    base_vol_avg = float(vol_clean.mean()) if len(vol_clean) > 0 else 1.0
    ipo_day_high = float(df['High'].iloc[0])
    base_high    = float(base_slice['High'].max())
    base_low     = float(base_slice['Low'].min())

    ipo_day_close    = float(df['Close'].iloc[0])
    ipo_day_vol      = float(df['Volume'].iloc[0])
    ipo_day_value_cr = ipo_day_close * ipo_day_vol / 1e7

    return {
        'ipo_day_high':     ipo_day_high,
        'base_high':        base_high,
        'base_low':         base_low,
        'base_vol_avg':     base_vol_avg,
        'breakout_level':   max(base_high, ipo_day_high),
        'ipo_day_value_cr': round(ipo_day_value_cr, 2),
        'liquidity_ok':     ipo_day_value_cr >= MIN_IPO_DAY_VALUE_CR,
    }


def detect_ipo_stage(df: pd.DataFrame, ipo_day_high: float,
                     breakout_level: float, base_low: float,
                     base_vol_avg: float) -> str:
    """
    Classify the current 3-stage IPO pattern.

    Returns one of: 'Stage 3', 'Stage 2', 'Stage 1', 'Failed', 'Too Early'.
    'In Trade' is overlaid in load_all_signals() by cross-referencing open backtest positions.

    Stage 1 — Building Base  : price < IPO Day High, volume contracting vs listing week
    Stage 2 — Reclaiming     : price > EMA10 and < breakout level (recovery in progress)
    Stage 3 — Breakout Ready : price > breakout level + volume > 1.5× 20-day avg
    Failed                   : price > 10% below base low (breakdown confirmed)
    """
    if len(df) < 5:
        return 'Too Early'

    close  = df['Close']
    volume = df['Volume']
    ema10  = compute_ema(close, EMA_PERIOD)

    latest_close = float(close.iloc[-1])
    latest_vol   = float(volume.iloc[-1])
    latest_ema   = float(ema10.iloc[-1])

    # Volume contraction: recent 5-day avg vs listing-week avg
    r5  = float(volume.iloc[-5:].replace(0, np.nan).mean())
    lw  = float(volume.iloc[:5].replace(0, np.nan).mean())
    if pd.isna(lw) or lw == 0:
        lw = r5 if not pd.isna(r5) else 1.0
    vol_contracting = (not pd.isna(r5)) and r5 < lw

    # Stage 3 volume: use base_vol_avg (same reference as entry trigger)
    vol_confirmed = (base_vol_avg > 0 and latest_vol >= VOL_MULTIPLIER * base_vol_avg)

    # Failed: >10% below base low
    if latest_close < base_low * 0.90:
        return 'Failed'

    # Stage 3: above breakout level with volume confirmation
    if latest_close > breakout_level and vol_confirmed:
        return 'Stage 3'

    # Stage 2: price reclaimed EMA10, still below breakout level
    if latest_close > latest_ema and latest_close < breakout_level:
        return 'Stage 2'

    # Stage 1: below IPO day high with contracting volume (base building)
    if latest_close <= ipo_day_high and vol_contracting:
        return 'Stage 1'

    # Default — consolidating, not yet classified as Stage 2
    return 'Stage 1'


def detect_signal(df: pd.DataFrame, base: dict | None, age_days: int) -> dict:
    """Return signal dict for the screener table."""
    latest_close = float(df['Close'].iloc[-1])
    latest_vol   = float(df['Volume'].iloc[-1])
    ema_series   = compute_ema(df['Close'], EMA_PERIOD)
    ema10        = float(ema_series.iloc[-1])
    ipo_day_high = float(df['High'].iloc[0])

    # FIX 3: use rolling 20-day volume average for vol_ratio (not static base_vol_avg)
    vol_20_series = df['Volume'].rolling(20).mean()
    vol_avg_20    = float(vol_20_series.iloc[-1]) if not pd.isna(vol_20_series.iloc[-1]) else 1.0

    result = {
        'Current_Price':   latest_close,
        'IPO_Day_High':    ipo_day_high,
        'Base_High':       None,
        'Breakout_Level':  None,
        'vs_Breakout_Pct': None,
        'Vol_Ratio':       None,
        'EMA10':           ema10,
        'Stop':            None,
        'Signal':          'Too New',
    }

    if age_days < SKIP_DAYS + 5:
        return result

    if base is None:
        result['Signal'] = 'Forming Base'
        return result

    vol_ratio = latest_vol / vol_avg_20 if vol_avg_20 > 0 else 0

    result['Base_High']       = base['base_high']
    result['Breakout_Level']  = base['breakout_level']
    result['vs_Breakout_Pct'] = (latest_close / base['breakout_level'] - 1) * 100
    result['Vol_Ratio']       = vol_ratio
    result['Stop']            = max(base['base_low'], latest_close * 0.92)

    is_breakout   = (latest_close > base['breakout_level']
                     and vol_ratio >= VOL_MULTIPLIER
                     and latest_close > ema10)
    is_watch      = (latest_close >= base['breakout_level'] * 0.97
                     or (vol_ratio >= 1.2 and latest_close > ema10))
    is_below_base = latest_close < base['base_low']

    if is_breakout:
        result['Signal'] = 'Live Breakout'
    elif is_watch:
        result['Signal'] = 'Watch Zone'
    elif is_below_base:
        result['Signal'] = 'Avoid'
    else:
        result['Signal'] = 'Forming Base'

    return result


def download_fresh_ohlcv(ticker: str, days_back: int = 420) -> pd.DataFrame | None:
    try:
        today = datetime.now().date()
        start = today - timedelta(days=days_back)
        raw   = yf.download(
            ticker,
            start=str(start),
            end=str(today + timedelta(days=1)),
            progress=False,
            auto_adjust=True,
        )
        if raw is None or raw.empty:
            return None
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.droplevel(1)
        needed = [c for c in ['Open', 'High', 'Low', 'Close', 'Volume'] if c in raw.columns]
        if len(needed) < 5:
            return None
        df = raw[needed].dropna(subset=['Close'])
        df.index = pd.to_datetime(df.index)
        df.index.name = 'Date'
        return df.sort_index()
    except Exception:
        return None


def refresh_all_data():
    Path(os.path.join(BASE_DIR, DATA_FOLDER)).mkdir(exist_ok=True)
    for ticker in list(NSE_IPO_UNIVERSE.keys()) + [BENCHMARK]:
        df = download_fresh_ohlcv(ticker)
        if df is not None and not df.empty:
            df.to_csv(os.path.join(BASE_DIR, DATA_FOLDER, f'{ticker}.csv'))


# ═══════════════════════════════════════════════════════════════════════════════
#  DATA LOADERS (cached)
# ═══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=120)
def load_all_signals() -> list[dict]:
    """
    Load OHLCV from ipo_data/, compute signals + 3-stage classification,
    and enrich with liquidity filter, promoter quality, and PE ratio.
    """
    today = datetime.now().date()
    rows  = []

    promoter_quality, _ = _load_promoter_quality()

    for ticker, company in NSE_IPO_UNIVERSE.items():
        path = os.path.join(BASE_DIR, DATA_FOLDER, f'{ticker}.csv')
        if not os.path.exists(path):
            continue
        try:
            df = pd.read_csv(path, index_col=0, parse_dates=True)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.droplevel(1)
            needed = ['Open', 'High', 'Low', 'Close', 'Volume']
            if not all(c in df.columns for c in needed):
                continue
            df = df[needed].dropna(subset=['Close']).sort_index()
            if len(df) < 3:
                continue
        except Exception:
            continue

        listing_date = df.index[0].date()
        age_days     = (today - listing_date).days

        if age_days > LISTING_AGE_MAX:
            continue

        base   = compute_base(df)
        signal = detect_signal(df, base, age_days)

        # ── IPO Day Liquidity ─────────────────────────────────────────────────
        if base is not None:
            ipo_val_cr   = base['ipo_day_value_cr']
            liquidity_ok = base['liquidity_ok']
        else:
            ipo_day_close = float(df['Close'].iloc[0])
            ipo_day_vol   = float(df['Volume'].iloc[0])
            ipo_val_cr    = round(ipo_day_close * ipo_day_vol / 1e7, 2)
            liquidity_ok  = ipo_val_cr >= MIN_IPO_DAY_VALUE_CR

        # ── 3-Stage Detection ─────────────────────────────────────────────────
        if base is not None:
            ipo_stage = detect_ipo_stage(
                df,
                base['ipo_day_high'],
                base['breakout_level'],
                base['base_low'],
                base['base_vol_avg'],
            )
        else:
            # Base not yet formed — classify using available data
            ipo_stage = detect_ipo_stage(
                df,
                ipo_day_high=float(df['High'].iloc[0]),
                breakout_level=float(df['High'].iloc[0]),
                base_low=float(df['Low'].min()),
                base_vol_avg=float(df['Volume'].replace(0, np.nan).mean()) or 1.0,
            )

        # ── Promoter Quality ──────────────────────────────────────────────────
        symbol       = ticker.replace('.NS', '').upper()
        pq_info      = promoter_quality.get(symbol, {})
        prom_backed  = pq_info.get('PromoterBacked', 'Unknown')
        promoter_str = _promoter_label(prom_backed)

        # ── PE at Listing (cached 1h) ─────────────────────────────────────────
        pe_val = _get_listing_pe(ticker)
        pe_str = f'{pe_val:.1f}' if pe_val is not None else '—'

        rows.append({
            'Ticker':           ticker,
            'Company':          company,
            'Listing_Date':     str(listing_date),
            'Age_Days':         age_days,
            'IPO_Day_Val_Cr':   ipo_val_cr,
            'Liquidity_OK':     liquidity_ok,
            'Liquidity':        _liquidity_label(ipo_val_cr),
            'Promoter_Backed':  prom_backed,
            'Promoter':         promoter_str,
            'PE':               pe_val,
            'PE_Str':           pe_str,
            'IPO_Stage':        ipo_stage,
            'IPO_Stage_Label':  STAGE_LABELS.get(ipo_stage, ipo_stage),
            **signal,
        })

    # Sort: Stage rank → Signal rank → PE (lower = better) → Age
    stage_rank  = {s: i for i, s in enumerate(STAGE_ORDER)}
    signal_rank = {s: i for i, s in enumerate(SIGNAL_ORDER)}
    rows.sort(key=lambda r: (
        stage_rank.get(r.get('IPO_Stage', 'Too Early'), 99),
        signal_rank.get(r['Signal'], 99),
        r['PE'] if r['PE'] is not None else 9999,
        r['Age_Days'],
    ))
    return rows


@st.cache_data(ttl=300)
def load_backtest_equity() -> pd.DataFrame:
    p = os.path.join(BASE_DIR, 'ipo_edge_equity.csv')
    if not os.path.exists(p):
        return pd.DataFrame()
    return pd.read_csv(p, parse_dates=['Date'])


@st.cache_data(ttl=300)
def load_trades() -> pd.DataFrame:
    p = os.path.join(BASE_DIR, 'ipo_edge_trades.csv')
    if not os.path.exists(p):
        return pd.DataFrame()
    return pd.read_csv(p)


# ═══════════════════════════════════════════════════════════════════════════════
#  MEMORY LOG
# ═══════════════════════════════════════════════════════════════════════════════

def write_ipo_memory_log(rows: list[dict]):
    memory_path = os.path.join(BASE_DIR, MEMORY_FILE)
    now         = datetime.now().strftime('%d %b %Y, %H:%M')

    breakouts = [r for r in rows if r['Signal'] == 'Live Breakout']
    watches   = [r for r in rows if r['Signal'] == 'Watch Zone']
    st3       = [r for r in rows if r.get('IPO_Stage') == 'Stage 3']
    st2       = [r for r in rows if r.get('IPO_Stage') == 'Stage 2']

    lines = [f'\n## {now} — IPO Edge Refresh\n\n']
    lines.append(
        f'**Live Breakouts:** {len(breakouts)} &nbsp;|&nbsp; '
        f'**Watch Zone:** {len(watches)} &nbsp;|&nbsp; '
        f'**Stage 3:** {len(st3)} &nbsp;|&nbsp; **Stage 2:** {len(st2)} &nbsp;|&nbsp; '
        f'**Total tracked:** {len(rows)}\n\n'
    )

    if breakouts:
        lines.append('### Live Breakout / Stage 3 Signals\n')
        lines.append('| Ticker | Company | Age | Stage | vs Breakout | Vol | Liquidity | Promoter |\n')
        lines.append('|--------|---------|----:|-------|------------:|----:|-----------|----------|\n')
        for r in breakouts:
            tk   = r['Ticker'].replace('.NS', '')
            vb   = f"{r['vs_Breakout_Pct']:+.1f}%" if r['vs_Breakout_Pct'] is not None else '—'
            vr   = f"{r['Vol_Ratio']:.2f}×"         if r['Vol_Ratio'] is not None else '—'
            liq  = r.get('Liquidity', '—')
            prom = r.get('Promoter', '—')
            stg  = r.get('IPO_Stage_Label', '—')
            lines.append(f'| {tk} | {r["Company"]} | {r["Age_Days"]}d | {stg} | {vb} | {vr} | {liq} | {prom} |\n')

    lines.append('\n---\n')

    if os.path.exists(memory_path):
        with open(memory_path, 'r', encoding='utf-8') as f:
            existing = f.read()
        marker  = '---\n'
        idx     = existing.find(marker)
        content = (existing[:idx + len(marker)] + ''.join(lines) + existing[idx + len(marker):]
                   if idx != -1 else existing + ''.join(lines))
    else:
        content = '# IPO Edge Activity Log\n\nNewest entries at the top.\n\n---\n' + ''.join(lines)

    with open(memory_path, 'w', encoding='utf-8') as f:
        f.write(content)


# ═══════════════════════════════════════════════════════════════════════════════
#  HEADER
# ═══════════════════════════════════════════════════════════════════════════════

hc1, hc2, hc3 = st.columns([5, 2.5, 0.8])
with hc1:
    st.markdown('### 🚀 &nbsp;IPO Edge — NSE IPO Live Screener')
with hc2:
    summary_path  = os.path.join(BASE_DIR, DATA_FOLDER, 'ipo_summary.csv')
    rankings_path = os.path.join(BASE_DIR, DATA_FOLDER, f'{list(NSE_IPO_UNIVERSE.keys())[0]}.csv')
    ts_src = summary_path if os.path.exists(summary_path) else rankings_path
    if os.path.exists(ts_src):
        mtime  = datetime.fromtimestamp(os.path.getmtime(ts_src))
        ts_str = mtime.strftime('Last updated: %d %b %Y, %H:%M')
    else:
        ts_str = 'No data yet — click Refresh'
    st.markdown(
        f"<p style='padding-top:13px; color:#6e7a90; font-size:0.78rem;'>{ts_str}</p>",
        unsafe_allow_html=True,
    )
with hc3:
    do_refresh = st.button('🔄 Refresh', width='stretch')

if do_refresh:
    with st.spinner('Fetching live IPO data from Yahoo Finance…'):
        refresh_all_data()
    rows_for_log = load_all_signals.__wrapped__()
    write_ipo_memory_log(rows_for_log)
    st.cache_data.clear()
    st.rerun()

_, prom_found = _load_promoter_quality()
if not prom_found:
    st.markdown(
        '<div class="warn-box">⚠️  <b>ipo_promoter_quality.csv</b> not found — '
        'Promoter Backed column will show "Unknown ⚪" for all stocks.</div>',
        unsafe_allow_html=True,
    )

# ═══════════════════════════════════════════════════════════════════════════════
#  LOAD SIGNALS + OVERLAY "IN TRADE" STATUS
# ═══════════════════════════════════════════════════════════════════════════════

rows      = load_all_signals()
trades_df = load_trades()

# Overlay "In Trade" for tickers with an open position in the backtest CSV
if not trades_df.empty and 'Status' in trades_df.columns:
    open_tickers = set(trades_df[trades_df['Status'] == 'Open']['Ticker'].tolist())
    for r in rows:
        if r['Ticker'] in open_tickers:
            r['IPO_Stage']       = 'In Trade'
            r['IPO_Stage_Label'] = STAGE_LABELS['In Trade']

# Re-sort after overlay (In Trade should be right after Stage 3)
stage_rank_map  = {s: i for i, s in enumerate(STAGE_ORDER)}
signal_rank_map = {s: i for i, s in enumerate(SIGNAL_ORDER)}
rows.sort(key=lambda r: (
    stage_rank_map.get(r.get('IPO_Stage', 'Too Early'), 99),
    signal_rank_map.get(r['Signal'], 99),
    r['PE'] if r['PE'] is not None else 9999,
    r['Age_Days'],
))

if not rows:
    st.warning('⚠️  No IPO data found in `ipo_data/`. Click **Refresh** to download.')
    st.stop()

# Stage counts
st3_rows   = [r for r in rows if r.get('IPO_Stage') == 'Stage 3']
in_tr_rows = [r for r in rows if r.get('IPO_Stage') == 'In Trade']
st2_rows   = [r for r in rows if r.get('IPO_Stage') == 'Stage 2']
st1_rows   = [r for r in rows if r.get('IPO_Stage') == 'Stage 1']
fail_rows  = [r for r in rows if r.get('IPO_Stage') == 'Failed']

breakouts  = [r for r in rows if r['Signal'] == 'Live Breakout']
watches    = [r for r in rows if r['Signal'] == 'Watch Zone']
forming    = [r for r in rows if r['Signal'] == 'Forming Base']
avoid      = [r for r in rows if r['Signal'] == 'Avoid']
liq_fail   = [r for r in rows if not r.get('Liquidity_OK', True)]

# ═══════════════════════════════════════════════════════════════════════════════
#  SNAPSHOT CARDS
# ═══════════════════════════════════════════════════════════════════════════════

st.markdown('<div class="sec-hdr">Today\'s IPO Snapshot</div>', unsafe_allow_html=True)
mc = st.columns(6)
snap_stats = [
    ('IPOs Tracked',   str(len(rows)),       '#7c9cff', 'within last 12 months'),
    ('Live Breakouts', str(len(breakouts)),   '#00c853', 'strong buy signals'),
    ('Watch Zone',     str(len(watches)),     '#f9c200', 'approaching breakout'),
    ('Forming Base',   str(len(forming)),     '#7c9cff', 'still consolidating'),
    ('Avoid',          str(len(avoid)),       '#ff3d3d', 'below base low'),
    ('Low Liquidity',  str(len(liq_fail)),    '#8892a4', f'< ₹{MIN_IPO_DAY_VALUE_CR}Cr IPO day'),
]
for col, (label, val, color, sub) in zip(mc, snap_stats):
    col.markdown(
        f'<div class="metric-card">'
        f'<div class="mv" style="color:{color};">{val}</div>'
        f'<div class="ml">{label}</div>'
        f'<div class="ml2">{sub}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

st.markdown("<div style='margin:14px 0'></div>", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
#  3-STAGE PATTERN SUMMARY BAR
# ═══════════════════════════════════════════════════════════════════════════════

def _stage_pill(stage_key: str, count: int) -> str:
    color = STAGE_COLORS.get(stage_key, '#8892a4')
    label = STAGE_LABELS.get(stage_key, stage_key)
    bg    = STAGE_BG.get(stage_key, 'rgba(136,146,164,0.08)')
    return (
        f'<span class="stage-pill" style="background:{bg};border:1px solid {color}30;">'
        f'<span class="cnt" style="color:{color};">{count}</span>'
        f'<span style="color:{color}; opacity:0.85;">{label}</span>'
        f'</span>'
    )


pills = (
    _stage_pill('Stage 3', len(st3_rows))
    + _stage_pill('In Trade', len(in_tr_rows))
    + _stage_pill('Stage 2', len(st2_rows))
    + _stage_pill('Stage 1', len(st1_rows))
    + _stage_pill('Failed',  len(fail_rows))
)
st.markdown(
    f'<div class="sec-hdr">3-Stage Pattern Summary</div>'
    f'<div class="stage-bar">{pills}</div>',
    unsafe_allow_html=True,
)

with st.expander("ℹ️ What do the stages mean?"):
    st.markdown("""
**Stage 1 — Building Base 🔵** The IPO has settled and is forming a price consolidation area.
The stock is not making new highs yet — it's "coiling up" for a potential move. Keep watching.

**Stage 2 — Reclaiming 🟡** The stock dipped below its base but is now climbing back.
It's showing recovery strength. Get it on your watchlist.

**Stage 3 — Breakout Ready 🟢** The stock is near or at its all-time high since listing, with rising volume.
This is the entry zone — the setup is complete and a breakout could happen any day.

**In Trade ✅** A position is already open from a previous signal. Watching for exit conditions.

**Failed ❌** The stock broke below its base low — the setup has failed. Stay away.

**Too Early** The IPO is too new (less than 40 trading days since listing). Not enough price history to evaluate.
    """)

# ═══════════════════════════════════════════════════════════════════════════════
#  BREAKOUT CARDS  (Stage 3 + Live Breakouts shown together)
# ═══════════════════════════════════════════════════════════════════════════════

# Show Stage 3 + In Trade cards (entry zone stocks)
entry_zone_rows = [r for r in rows if r.get('IPO_Stage') in ('Stage 3', 'In Trade')]
if entry_zone_rows:
    n_show = min(len(entry_zone_rows), 5)
    st.markdown(
        f'<div class="sec-hdr">Stage 3 — Breakout Ready &amp; In Trade &nbsp;—&nbsp; {n_show} Stock(s)</div>',
        unsafe_allow_html=True,
    )
    card_cols = st.columns(n_show)
    for i, r in enumerate(entry_zone_rows[:n_show]):
        stage     = r.get('IPO_Stage', 'Stage 3')
        stg_color = STAGE_COLORS.get(stage, '#00c853')
        stg_label = STAGE_LABELS.get(stage, stage)
        sig_color = SIGNAL_COLORS.get(r['Signal'], '#8892a4')

        vb    = f"{r['vs_Breakout_Pct']:+.2f}%" if r['vs_Breakout_Pct'] is not None else '—'
        vr    = f"{r['Vol_Ratio']:.1f}×"         if r['Vol_Ratio'] is not None else '—'
        stp   = f"Rs{r['Stop']:,.2f}"             if r['Stop'] is not None else '—'
        price = r['Current_Price']

        liq_ok   = r.get('Liquidity_OK', True)
        liq_tag  = f"₹{r['IPO_Day_Val_Cr']:.1f}Cr {'✅' if liq_ok else '❌'}"
        prom     = r.get('Promoter_Backed', 'Unknown')
        prom_tag = {'YES': 'Promoter ✅', 'NO': 'Promoter ❌'}.get(prom, 'Promoter ⚪')
        pe_val   = r.get('PE')
        pe_col   = _pe_color(pe_val)
        pe_tag   = f"PE: {r['PE_Str']}" if pe_val is not None else 'PE: —'

        card_cols[i].markdown(
            f'<div class="breakout-card" style="border-top:3px solid {stg_color};">'
            f'<div class="bc-rank">IPO — {r["Age_Days"]}d old</div>'
            f'<div class="bc-co">{r["Company"]}</div>'
            f'<div class="bc-tk">{r["Ticker"].replace(".NS","")}</div>'
            f'<div class="bc-rs" style="color:{stg_color};">{vb} above breakout</div>'
            f'<div class="bc-sub">Vol: {vr} &nbsp;·&nbsp; Stop: {stp}</div>'
            f'<div class="bc-price">Rs{price:,.2f} current price</div>'
            f'<div class="bc-tags">'
            f'  <span style="color:#6e7a90;">{liq_tag}</span> &nbsp;·&nbsp; '
            f'  <span style="color:#6e7a90;">{prom_tag}</span> &nbsp;·&nbsp; '
            f'  <span style="color:{pe_col};">{pe_tag}</span>'
            f'</div>'
            f'<div style="margin-top:6px;">'
            f'  <span class="bc-sig" style="color:{stg_color};border:1px solid {stg_color}40;'
            f'  background:{STAGE_BG.get(stage,"rgba(0,0,0,0.3)")};">{stg_label}</span>'
            f'  &nbsp;'
            f'  <span class="bc-sig" style="color:{sig_color};border:1px solid {sig_color}40;'
            f'  background:rgba(0,0,0,0.25);">{r["Signal"]}</span>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
    st.markdown("<div style='margin:16px 0'></div>", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN SCREENER TABLE
# ═══════════════════════════════════════════════════════════════════════════════

st.markdown('<div class="sec-hdr">All IPO Candidates — Ranked by Stage → Signal → PE</div>',
            unsafe_allow_html=True)


def fmt(val, fmt_str, fallback='—'):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return fallback
    return fmt_str.format(val)


n = len(rows)

col_rank    = list(range(1, n + 1))
col_ticker  = [r['Ticker'].replace('.NS', '') for r in rows]
col_company = [r['Company'] for r in rows]
col_age     = [f"{r['Age_Days']}d" for r in rows]
col_stage   = [r.get('IPO_Stage_Label', '—') for r in rows]
col_ipo_hi  = [fmt(r['IPO_Day_High'],    'Rs{:,.2f}') for r in rows]
col_base_hi = [fmt(r['Base_High'],       'Rs{:,.2f}') for r in rows]
col_price   = [fmt(r['Current_Price'],   'Rs{:,.2f}') for r in rows]
col_vs_brk  = [fmt(r['vs_Breakout_Pct'], '{:+.1f}%') for r in rows]
col_vol_rat = [fmt(r['Vol_Ratio'],        '{:.2f}x') for r in rows]
col_ema10   = [fmt(r['EMA10'],           'Rs{:,.2f}') for r in rows]
col_stop    = [fmt(r['Stop'],            'Rs{:,.2f}') for r in rows]
col_liq_val = [f"₹{r['IPO_Day_Val_Cr']:.1f}Cr" for r in rows]
col_liq_st  = ['✅ Liquid' if r.get('Liquidity_OK', True) else '❌ Low Liq' for r in rows]
col_prom    = [r.get('Promoter', 'Unknown ⚪') for r in rows]
col_pe      = [r.get('PE_Str', '—') for r in rows]
col_signal  = [r['Signal'] for r in rows]

# Per-row color lists
row_bg     = [SIGNAL_BG.get(r['Signal'], 'rgba(0,0,0,0)') for r in rows]
sig_colors = [SIGNAL_COLORS.get(r['Signal'], '#8892a4')   for r in rows]
stg_colors = [STAGE_COLORS.get(r.get('IPO_Stage', 'Too Early'), '#8892a4') for r in rows]
liq_colors = ['#00c853' if r.get('Liquidity_OK', True) else '#ff3d3d' for r in rows]
prom_colors = [
    '#00c853' if r.get('Promoter_Backed') == 'YES'
    else '#ff3d3d' if r.get('Promoter_Backed') == 'NO'
    else '#6e7a90'
    for r in rows
]
pe_colors = [_pe_color(r.get('PE')) for r in rows]

fig_tbl = go.Figure(data=[go.Table(
    columnwidth=[26, 62, 138, 46, 140, 76, 76, 76, 70, 60, 76, 76, 66, 68, 78, 50, 93],
    header=dict(
        values=[
            '<b>#</b>', '<b>Ticker</b>', '<b>Company</b>', '<b>Age</b>',
            '<b>Stage</b>',
            '<b>IPO High</b>', '<b>Base High</b>', '<b>Price</b>',
            '<b>vs Breakout</b>', '<b>Vol Ratio</b>', '<b>EMA10</b>', '<b>Stop</b>',
            '<b>IPO Day(Cr)</b>', '<b>Liquidity</b>',
            '<b>Promoter</b>', '<b>PE</b>',
            '<b>Signal</b>',
        ],
        fill_color='#161b2b',
        align=['center', 'left', 'left', 'center',
               'left',
               'right', 'right', 'right', 'right', 'right', 'right', 'right',
               'right', 'center', 'center', 'right',
               'center'],
        font=dict(color='#6e7a90', size=11),
        height=28,
        line_color='#242d47',
    ),
    cells=dict(
        values=[
            col_rank, col_ticker, col_company, col_age,
            col_stage,
            col_ipo_hi, col_base_hi, col_price,
            col_vs_brk, col_vol_rat, col_ema10, col_stop,
            col_liq_val, col_liq_st, col_prom, col_pe,
            col_signal,
        ],
        fill_color=[row_bg] * 17,
        align=['center', 'left', 'left', 'center',
               'left',
               'right', 'right', 'right', 'right', 'right', 'right', 'right',
               'right', 'center', 'center', 'right',
               'center'],
        font=dict(
            color=[
                ['#bcc6d8'] * n,   # rank
                ['#bcc6d8'] * n,   # ticker
                ['#8a96aa'] * n,   # company
                ['#bcc6d8'] * n,   # age
                stg_colors,        # stage (colored by stage)
                ['#bcc6d8'] * n,   # ipo high
                ['#bcc6d8'] * n,   # base high
                ['#bcc6d8'] * n,   # price
                sig_colors,        # vs breakout
                sig_colors,        # vol ratio
                ['#bcc6d8'] * n,   # ema10
                ['#bcc6d8'] * n,   # stop
                ['#bcc6d8'] * n,   # ipo day value
                liq_colors,        # liquidity
                prom_colors,       # promoter
                pe_colors,         # PE
                sig_colors,        # signal
            ],
            size=10,
        ),
        height=22,
        line_color='#242d47',
    ),
)])
fig_tbl.update_layout(
    height=max(300, n * 24 + 65),
    margin=dict(l=0, r=0, t=4, b=4),
    paper_bgcolor='rgba(0,0,0,0)',
)
st.plotly_chart(fig_tbl, width='stretch', config={'displayModeBar': False})

# ── Legend ────────────────────────────────────────────────────────────────────
st.markdown(
    '<div style="font-size:0.72rem; color:#6e7a90; margin-top:4px; line-height:2;">'
    '<b>Stages:</b> &nbsp;'
    '<span style="color:#00c853;">🟢 Stage 3</span> — above breakout level + volume confirmed &nbsp;&nbsp;'
    '<span style="color:#f9c200;">🟡 Stage 2</span> — reclaimed EMA10, below breakout &nbsp;&nbsp;'
    '<span style="color:#7c9cff;">🔵 Stage 1</span> — below IPO high, volume contracting &nbsp;&nbsp;'
    '<span style="color:#00e5ff;">✅ In Trade</span> — open position in backtest &nbsp;&nbsp;'
    '<span style="color:#ff3d3d;">❌ Failed</span> — broke below base low<br>'
    '<b>Signal:</b> &nbsp;'
    '<span style="color:#00c853;">Live Breakout</span> — all 3 conditions met today &nbsp;&nbsp;'
    '<span style="color:#f9c200;">Watch Zone</span> — within 3% of breakout &nbsp;&nbsp;'
    '<span style="color:#7c9cff;">Forming Base</span> — base window not yet complete &nbsp;&nbsp;'
    '<span style="color:#ff3d3d;">Avoid</span> — below base low &nbsp;&nbsp;'
    f'<span style="color:#6e7a90;">Liquidity: ≥ ₹{MIN_IPO_DAY_VALUE_CR}Cr IPO Day required</span> &nbsp;&nbsp;'
    '<span style="color:#00c853;">PE &lt;20</span> / <span style="color:#f9c200;">PE 20–40</span> / <span style="color:#ff9800;">PE &gt;40</span>'
    '</div>',
    unsafe_allow_html=True,
)

st.markdown("<div style='margin:18px 0'></div>", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
#  BACKTEST EQUITY CURVE
# ═══════════════════════════════════════════════════════════════════════════════

equity_df = load_backtest_equity()

if not equity_df.empty:
    st.markdown('<div class="sec-hdr">IPO Edge Backtest Performance (run ipo_edge_backtest.py to update)</div>',
                unsafe_allow_html=True)

    pv0 = float(equity_df['Portfolio_Value'].iloc[0])
    pvf = float(equity_df['Portfolio_Value'].iloc[-1])
    total_ret = (pvf / pv0 - 1) * 100

    fig_perf = go.Figure()
    strat_norm = equity_df['Portfolio_Value'] / pv0 * 100
    fig_perf.add_trace(go.Scatter(
        x=equity_df['Date'], y=strat_norm,
        name='IPO Edge Strategy',
        line=dict(color='#00c853', width=2.5),
        hovertemplate='%{x|%d %b %Y}  Strategy: %{y:.1f}<extra></extra>',
    ))
    if 'Benchmark_Value' in equity_df.columns:
        fig_perf.add_trace(go.Scatter(
            x=equity_df['Date'], y=equity_df['Benchmark_Value'],
            name='NiftyBees (Market)',
            line=dict(color='#7c9cff', width=2, dash='dot'),
            hovertemplate='%{x|%d %b %Y}  Market: %{y:.1f}<extra></extra>',
        ))
    fig_perf.add_hline(y=100, line_color='#3a4460', line_width=1, line_dash='dash')
    fig_perf.update_layout(
        height=280, margin=dict(l=0, r=0, t=6, b=6),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(12,15,22,0.7)',
        xaxis=dict(gridcolor='#242d47', gridwidth=0.5, zeroline=False,
                   tickfont=dict(color='#6e7a90', size=10)),
        yaxis=dict(gridcolor='#242d47', gridwidth=0.5, zeroline=False,
                   tickfont=dict(color='#6e7a90', size=10),
                   title='Growth (start = 100)', title_font=dict(color='#6e7a90', size=10)),
        legend=dict(bgcolor='rgba(0,0,0,0)', font=dict(color='#bcc6d8', size=12),
                    orientation='h', x=0, y=1.1),
        hovermode='x unified',
    )

    pc1, pc2 = st.columns([3, 1])
    with pc1:
        st.plotly_chart(fig_perf, width='stretch', config={'displayModeBar': False})
    with pc2:
        color = '#00c853' if total_ret >= 0 else '#ff3d3d'
        st.markdown(
            f'<div class="metric-card" style="margin-top:24px;">'
            f'<div class="mv" style="color:{color};">{total_ret:+.1f}%</div>'
            f'<div class="ml">Total Return</div>'
            f'<div class="ml2">IPO Edge Backtest</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

elif os.path.exists(os.path.join(BASE_DIR, DATA_FOLDER)):
    st.info('📊  Run `python ipo_edge_backtest.py` to generate the historical performance chart.')

# ═══════════════════════════════════════════════════════════════════════════════
#  RECENT TRADES TABLE
# ═══════════════════════════════════════════════════════════════════════════════

if not trades_df.empty:
    st.markdown('<div class="sec-hdr" style="margin-top:8px;">Recent Trades from Backtest</div>',
                unsafe_allow_html=True)

    show_df    = trades_df.sort_values('Entry_Date', ascending=False).head(15)
    pnl_colors = ['#00c853' if v >= 0 else '#ff3d3d' for v in show_df['PnL_Pct']]
    status_col = ['#00e5ff' if v == 'Open' else '#6e7a90' for v in show_df['Status']]

    has_liq   = 'IPO_Day_Value_Cr' in show_df.columns
    has_prom  = 'Promoter_Backed'  in show_df.columns
    has_stage = 'Entry_Stage'      in show_df.columns

    col_headers = ['Company', 'Ticker', 'Entry Date', 'Entry ₹',
                   'Exit Date', 'Exit ₹', 'P&L%', 'Exit Reason', 'Status']
    col_vals = [
        show_df['Company'],
        show_df['Ticker'].str.replace('.NS', '', regex=False),
        show_df['Entry_Date'],
        show_df['Entry_Price'].apply(lambda x: f'{x:,.2f}'),
        show_df['Exit_Date'],
        show_df['Exit_Price'].apply(lambda x: f'{x:,.2f}'),
        show_df['PnL_Pct'].apply(lambda x: f'{x:+.2f}%'),
        show_df['Exit_Reason'],
        show_df['Status'],
    ]
    col_widths = [85, 65, 70, 70, 70, 70, 60, 80, 60]
    col_align  = ['left', 'center', 'center', 'right', 'center', 'right', 'right', 'center', 'center']
    font_colors = [
        ['#8a96aa'] * len(show_df),
        ['#bcc6d8'] * len(show_df),
        ['#bcc6d8'] * len(show_df),
        ['#bcc6d8'] * len(show_df),
        ['#bcc6d8'] * len(show_df),
        ['#bcc6d8'] * len(show_df),
        pnl_colors,
        ['#6e7a90'] * len(show_df),
        status_col,
    ]

    if has_stage:
        col_headers.append('Entry Stage')
        col_vals.append(show_df['Entry_Stage'])
        col_widths.append(130)
        col_align.append('left')
        # Color Stage 3 entries green
        stage_fc = ['#00c853' if 'Stage 3' in str(v) else '#8892a4'
                    for v in show_df['Entry_Stage']]
        font_colors.append(stage_fc)

    if has_liq:
        col_headers.append('IPO Day(Cr)')
        col_vals.append(show_df['IPO_Day_Value_Cr'].apply(lambda x: f'₹{x:.1f}Cr' if pd.notna(x) else '—'))
        col_widths.append(70)
        col_align.append('right')
        font_colors.append(['#bcc6d8'] * len(show_df))

    if has_prom:
        col_headers.append('Promoter')
        col_vals.append(show_df['Promoter_Backed'].apply(
            lambda x: 'YES ✅' if x == 'YES' else ('NO ❌' if x == 'NO' else 'Unknown ⚪')
        ))
        col_widths.append(70)
        col_align.append('center')
        prom_fc = [
            '#00c853' if v == 'YES' else '#ff3d3d' if v == 'NO' else '#6e7a90'
            for v in show_df['Promoter_Backed']
        ]
        font_colors.append(prom_fc)

    fig_tr = go.Figure(data=[go.Table(
        columnwidth=col_widths,
        header=dict(
            values=[f'<b>{c}</b>' for c in col_headers],
            fill_color='#161b2b',
            align=col_align,
            font=dict(color='#6e7a90', size=11),
            height=26, line_color='#242d47',
        ),
        cells=dict(
            values=col_vals,
            fill_color='rgba(18,22,35,0.6)',
            align=col_align,
            font=dict(color=font_colors, size=10),
            height=21, line_color='#242d47',
        ),
    )])
    fig_tr.update_layout(
        height=min(450, len(show_df) * 23 + 50),
        margin=dict(l=0, r=0, t=4, b=4),
        paper_bgcolor='rgba(0,0,0,0)',
    )
    st.plotly_chart(fig_tr, width='stretch', config={'displayModeBar': False})

# ── Glossary ──────────────────────────────────────────────────────────────────
st.markdown("<div style='margin-top:24px'></div>", unsafe_allow_html=True)
with st.expander("📖 What do these terms mean? — Plain-English Glossary"):
    st.markdown("""
**IPO (Initial Public Offering)** — When a company first lists its shares on the stock exchange for the public to buy.
The IPO day price is what it first traded at after listing.

**Base** — A price consolidation zone formed in the first 40 days after listing. The stock trades in a tight range,
"digesting" the initial listing move before its next big move.

**Base High / Breakout Level** — The highest price the stock reached during its base-building phase.
When the stock closes above this level with high volume, that's the breakout signal — time to consider buying.

**IPO Day Value (₹Cr)** — The total rupee value of shares traded on the very first day of listing.
Higher value = more liquid stock. We only consider IPOs with ₹10Cr+ first-day trading value to ensure you can actually buy/sell without large price impact.

**Volume Ratio** — Today's trading volume ÷ the 40-day base average volume.
A ratio above 1.5× means unusual buying activity — confirming the breakout is real.

**EMA 10 (Exponential Moving Average)** — The 10-day weighted average price. Used as a short-term trend guide.
If price is above EMA 10, short-term momentum is up.

**Stop Loss** — The price at which you exit to limit your loss. For IPO Edge, this is set at the base low.
If price falls below the base it was building, the setup has failed — exit.

**Promoter Backed** — Whether the IPO was backed by a reputable promoter (established business house or PE firm).
YES ✅ = higher confidence. NO ❌ = promoter quality is a concern. Unknown ⚪ = not yet classified.

**PE Ratio (Price-to-Earnings)** — How expensive the stock is relative to its earnings. Lower PE = cheaper valuation.
Below 20 = cheap (green) · 20–40 = fair (yellow) · Above 40 = expensive (orange).

**P&L %** — Profit or Loss percentage on a trade. +10% means the exit price was 10% higher than entry.

**Equity Curve** — A chart showing how ₹10,000 invested per trade would have grown over time.
This is based on historical backtesting — past performance does not guarantee future results.
    """)
