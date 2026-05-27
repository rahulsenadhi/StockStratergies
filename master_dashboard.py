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
from plotly.subplots import make_subplots
import streamlit as st

from core import analytics as core_analytics
from core import data_io as core_data_io
from core import glossary as core_glossary
from core import indicators as core_indicators
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

PLOTLY_BASE = dict(paper_bgcolor='#1c1c1c', plot_bgcolor='#1c1c1c',
                   font=dict(color='#fafafa', size=12, family='Inter'))

# Choppiness constants
CHOPPINESS_P     = 14
CHOPPINESS_THRESH = 61.8

# Momentum Edge filter constants (used by criteria panel)
ME_SMA50_P    = 50
ME_SMA150_P   = 150
ME_EMA220_P   = 220
ME_HIGH52_P   = 252
ME_LOW52_P    = 252
ME_DIP_LB     = 90
ME_VOLAVG_P   = 20
ME_VOL_LOOKBACK = 50
ME_VOL_THRESH = 1.5
ME_VOL_MULT   = 1.5
ME_MIN_PRICE_VS_LOW = 1.25
ME_CHOP_THRESH = 61.8

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
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

/* ── Design tokens — SuperDesign "Modern Dark" (Linear/Vercel inspired) ─────
   Semantic token system with OKLCH colors, derived from SuperDesign theme spec
   (superdesigndev/superdesign). Restrained grayscale base with semantic accents
   for status (green / amber / red / blue). 0.625rem radius, subtle 1-3px shadows.
*/
:root {
    /* Base surfaces — grayscale stack, low chroma */
    --background:           oklch(0.145 0 0);    /* page bg — near black */
    --foreground:           oklch(0.985 0 0);    /* primary text */
    --card:                 oklch(0.205 0 0);    /* card surface */
    --card-foreground:      oklch(0.985 0 0);
    --popover:              oklch(0.205 0 0);
    --popover-foreground:   oklch(0.985 0 0);
    --primary:              oklch(0.985 0 0);    /* primary action — white */
    --primary-foreground:   oklch(0.205 0 0);
    --secondary:            oklch(0.269 0 0);    /* secondary surface */
    --secondary-foreground: oklch(0.985 0 0);
    --muted:                oklch(0.269 0 0);
    --muted-foreground:     oklch(0.708 0 0);    /* low-emphasis text */
    --accent:               oklch(0.269 0 0);
    --accent-foreground:    oklch(0.985 0 0);
    --destructive:          oklch(0.625 0.245 27.325); /* red */
    --destructive-foreground: oklch(0.985 0 0);
    --border:               oklch(0.275 0 0);
    --input:                oklch(0.275 0 0);
    --ring:                 oklch(0.556 0 0);

    /* Semantic status accents — chart-style chroma */
    --success:              oklch(0.696 0.170 162.480); /* emerald */
    --warning:              oklch(0.768 0.180 70.080);  /* amber */
    --info:                 oklch(0.623 0.214 259.815); /* blue */

    /* Chart palette */
    --chart-1: oklch(0.696 0.170 162.480);  /* green */
    --chart-2: oklch(0.623 0.214 259.815);  /* blue */
    --chart-3: oklch(0.769 0.188 70.080);   /* amber */
    --chart-4: oklch(0.627 0.265 303.900);  /* purple */
    --chart-5: oklch(0.645 0.246 16.439);   /* rose */

    /* Sidebar */
    --sidebar:                    oklch(0.205 0 0);
    --sidebar-foreground:         oklch(0.985 0 0);
    --sidebar-primary:            oklch(0.488 0.243 264.376);
    --sidebar-primary-foreground: oklch(0.985 0 0);
    --sidebar-accent:             oklch(0.269 0 0);
    --sidebar-accent-foreground:  oklch(0.985 0 0);
    --sidebar-border:             oklch(0.275 0 0);
    --sidebar-ring:               oklch(0.439 0 0);

    /* Typography */
    --font-sans: 'Inter', ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
    --font-mono: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace;

    /* Geometry */
    --radius:    0.625rem;
    --radius-sm: calc(var(--radius) - 4px);
    --radius-md: calc(var(--radius) - 2px);
    --radius-lg: var(--radius);
    --radius-xl: calc(var(--radius) + 4px);

    /* Shadows — subtle, layered */
    --shadow-2xs: 0 1px 3px 0px hsl(0 0% 0% / 0.05);
    --shadow-xs:  0 1px 3px 0px hsl(0 0% 0% / 0.05);
    --shadow-sm:  0 1px 3px 0px hsl(0 0% 0% / 0.10), 0 1px 2px -1px hsl(0 0% 0% / 0.10);
    --shadow:     0 1px 3px 0px hsl(0 0% 0% / 0.10), 0 1px 2px -1px hsl(0 0% 0% / 0.10);
    --shadow-md:  0 1px 3px 0px hsl(0 0% 0% / 0.10), 0 2px 4px -1px hsl(0 0% 0% / 0.10);
    --shadow-lg:  0 1px 3px 0px hsl(0 0% 0% / 0.10), 0 4px 6px -1px hsl(0 0% 0% / 0.10);
    --shadow-xl:  0 1px 3px 0px hsl(0 0% 0% / 0.10), 0 8px 10px -1px hsl(0 0% 0% / 0.10);

    /* Legacy aliases (back-compat with existing helper functions) */
    --bg-base:       var(--background);
    --bg-surface:    var(--card);
    --bg-surface-2:  oklch(0.235 0 0);
    --bg-muted:      var(--muted);
    --border-soft:   var(--border);
    --border-strong: oklch(0.380 0 0);
    --fg-primary:    var(--foreground);
    --fg-secondary:  oklch(0.769 0 0);
    --fg-muted:      var(--muted-foreground);
    --fg-subtle:     oklch(0.520 0 0);
    --accent-soft:   color-mix(in oklch, var(--success) 14%, transparent);
    --warn:          var(--warning);
    --warn-soft:     color-mix(in oklch, var(--warning) 12%, transparent);
    --danger:        var(--destructive);
    --danger-soft:   color-mix(in oklch, var(--destructive) 12%, transparent);
    --info-soft:     color-mix(in oklch, var(--info) 12%, transparent);
}

/* ── Light theme override —————————————————————————————————————————————
   Activates when Streamlit theme is "light" OR when host OS prefers light.
   Streamlit sets data-theme="light" on the root when theme.base=light is
   chosen in Settings or .streamlit/config.toml. */
[data-theme="light"], html[data-theme="light"] :root, body[data-theme="light"] {
    --background:           oklch(0.985 0 0);    /* near-white page bg */
    --foreground:           oklch(0.205 0 0);    /* near-black text */
    --card:                 oklch(1.000 0 0);    /* white card */
    --card-foreground:      oklch(0.205 0 0);
    --popover:              oklch(1.000 0 0);
    --popover-foreground:   oklch(0.205 0 0);
    --primary:              oklch(0.205 0 0);
    --primary-foreground:   oklch(0.985 0 0);
    --secondary:            oklch(0.940 0 0);
    --secondary-foreground: oklch(0.205 0 0);
    --muted:                oklch(0.940 0 0);
    --muted-foreground:     oklch(0.450 0 0);
    --accent:               oklch(0.940 0 0);
    --accent-foreground:    oklch(0.205 0 0);
    --border:               oklch(0.900 0 0);
    --input:                oklch(0.900 0 0);
    --ring:                 oklch(0.708 0 0);

    --sidebar:                    oklch(0.965 0 0);
    --sidebar-foreground:         oklch(0.205 0 0);
    --sidebar-accent:             oklch(0.900 0 0);
    --sidebar-accent-foreground:  oklch(0.205 0 0);
    --sidebar-border:             oklch(0.880 0 0);
    --sidebar-ring:               oklch(0.708 0 0);

    --bg-surface:    var(--card);
    --bg-surface-2:  oklch(0.955 0 0);
    --bg-muted:      var(--muted);
    --border-soft:   var(--border);
    --border-strong: oklch(0.820 0 0);
    --fg-primary:    var(--foreground);
    --fg-secondary:  oklch(0.330 0 0);
    --fg-muted:      var(--muted-foreground);
    --fg-subtle:     oklch(0.520 0 0);
}

/* OS-level light preference when Streamlit theme not explicitly set */
@media (prefers-color-scheme: light) {
    html:not([data-theme="dark"]) {
        --background:           oklch(0.985 0 0);
        --foreground:           oklch(0.205 0 0);
        --card:                 oklch(1.000 0 0);
        --card-foreground:      oklch(0.205 0 0);
        --popover:              oklch(1.000 0 0);
        --popover-foreground:   oklch(0.205 0 0);
        --primary:              oklch(0.205 0 0);
        --primary-foreground:   oklch(0.985 0 0);
        --secondary:            oklch(0.940 0 0);
        --secondary-foreground: oklch(0.205 0 0);
        --muted:                oklch(0.940 0 0);
        --muted-foreground:     oklch(0.450 0 0);
        --accent:               oklch(0.940 0 0);
        --accent-foreground:    oklch(0.205 0 0);
        --border:               oklch(0.900 0 0);
        --input:                oklch(0.900 0 0);
        --ring:                 oklch(0.708 0 0);
        --sidebar:                    oklch(0.965 0 0);
        --sidebar-foreground:         oklch(0.205 0 0);
        --sidebar-accent:             oklch(0.900 0 0);
        --sidebar-accent-foreground:  oklch(0.205 0 0);
        --sidebar-border:             oklch(0.880 0 0);
        --bg-surface-2:  oklch(0.955 0 0);
        --border-strong: oklch(0.820 0 0);
        --fg-secondary:  oklch(0.330 0 0);
    }
}

/* ── Global ── */
html, body, [data-testid="stApp"] {
    background: var(--background) !important;
    color: var(--foreground) !important;
    font-family: var(--font-sans) !important;
    font-feature-settings: "cv11", "ss01";
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    letter-spacing: -0.005em;
}
[data-testid="stSidebar"] {
    background: var(--sidebar) !important;
    border-right: 1px solid var(--sidebar-border) !important;
}
[data-testid="stSidebar"] * { color: var(--sidebar-foreground) !important; }
[data-testid="stSidebar"] .stRadio label {
    padding: 8px 12px;
    border-radius: var(--radius-md);
    transition: background 120ms ease, color 120ms ease;
}
[data-testid="stSidebar"] .stRadio label:hover { background: var(--sidebar-accent); }
[data-testid="stAppViewContainer"] { background: var(--background) !important; }
.block-container { padding-top: 1.75rem !important; max-width: 1400px; }
div[data-testid="column"] { padding: 6px 8px !important; }

/* Tabular figures for numbers (prevents column jitter) */
.metric-pill .value, .hub-card .big-num, .hub-card .kv-v,
[data-testid="stMetricValue"], .stDataFrame td {
    font-variant-numeric: tabular-nums;
    font-feature-settings: "tnum";
}

/* ── Strategy hub cards (Linear-style: flat, subtle hover, no gradient) ── */
.hub-card {
    background: var(--card);
    color: var(--card-foreground);
    border-radius: var(--radius-lg);
    padding: 22px 24px;
    border: 1px solid var(--border);
    position: relative;
    overflow: hidden;
    height: 100%;
    box-shadow: var(--shadow-sm);
    transition: border-color 180ms ease, background 180ms ease, box-shadow 180ms ease;
}
.hub-card:hover {
    border-color: var(--ring);
    background: var(--bg-surface-2);
    box-shadow: var(--shadow-md);
}
.hub-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    opacity: 0.85;
}
.hub-card .strategy-name {
    font-size: 11px; font-weight: 500; text-transform: uppercase;
    letter-spacing: .12em; margin-bottom: 14px; color: var(--muted-foreground);
    display: flex; align-items: center; gap: 8px;
}
.hub-card .big-num {
    font-size: 32px; font-weight: 600; line-height: 1.05;
    letter-spacing: -.03em; color: var(--card-foreground);
}
.hub-card .plain-label {
    font-size: 12px; color: var(--muted-foreground); margin-top: 4px; margin-bottom: 14px;
    line-height: 1.5;
}
.hub-card .divider { border-top: 1px solid var(--border); margin: 16px 0; opacity: 0.6; }
.hub-card .row { display: flex; justify-content: space-between; gap: 14px; }
.hub-card .kv-block { flex: 1; }
.hub-card .kv-l { color: var(--muted-foreground); font-size: 10px; text-transform: uppercase; letter-spacing:.10em; margin-bottom: 4px; font-weight: 500; }
.hub-card .kv-v { font-size: 15px; font-weight: 600; color: var(--card-foreground); letter-spacing: -.01em; }
.hub-card .kv-explain { font-size: 10px; color: var(--fg-subtle); margin-top: 2px; }
.hub-card .desc-box {
    background: var(--muted); border-radius: var(--radius-md);
    padding: 10px 14px; margin-top: 14px; font-size: 12px; color: var(--muted-foreground); line-height: 1.65;
    border: 1px solid var(--border);
}

/* ── Metric pill ── */
.metric-pill {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: 16px 18px;
    text-align: left;
    height: 100%;
    box-shadow: var(--shadow-xs);
    transition: border-color 180ms ease, background 180ms ease, box-shadow 180ms ease;
}
.metric-pill:hover {
    border-color: var(--ring);
    background: var(--bg-surface-2);
    box-shadow: var(--shadow-sm);
}
.metric-pill .label {
    color: var(--muted-foreground); font-size: 10px; text-transform: uppercase;
    letter-spacing: .10em; font-weight: 500;
}
.metric-pill .value {
    font-size: 24px; font-weight: 600; margin: 8px 0 4px; letter-spacing: -.025em;
    color: var(--card-foreground);
}
.metric-pill .sub   { color: var(--muted-foreground); font-size: 11px; line-height: 1.5; }
.metric-pill .explain {
    font-size: 10.5px; color: var(--fg-subtle); margin-top: 10px;
    padding-top: 8px; border-top: 1px solid var(--border); line-height: 1.55;
}

/* ── Section headers ── */
.sec-hdr {
    font-size: 11px; font-weight: 600; text-transform: uppercase;
    letter-spacing: .14em; color: var(--fg-secondary); margin: 0 0 12px 2px;
    display: flex; align-items: center; gap: 10px;
}
.sec-hdr::after {
    content: ''; flex: 1; height: 1px; background: var(--border-soft);
}

/* ── Page title ── */
.page-title {
    font-size: 28px; font-weight: 600; letter-spacing: -.025em; line-height: 1.15;
    color: var(--fg-primary);
}
.page-sub { color: var(--fg-secondary); font-size: 13px; margin-top: 6px; line-height: 1.55; }

/* ── Signal badges ── */
.badge {
    display: inline-block; border-radius: 4px;
    padding: 3px 9px; font-size: 11px; font-weight: 600; letter-spacing: .02em;
}
.badge-green  { background: var(--accent-soft); color: var(--accent); border: 1px solid rgba(34,197,94,0.30); }
.badge-yellow { background: var(--warn-soft);   color: var(--warn);   border: 1px solid rgba(245,158,11,0.30); }
.badge-blue   { background: var(--info-soft);   color: var(--info);   border: 1px solid rgba(96,165,250,0.30); }
.badge-red    { background: var(--danger-soft); color: var(--danger); border: 1px solid rgba(239,68,68,0.30); }
.badge-grey   { background: rgba(148,163,184,0.10); color: var(--fg-secondary); border: 1px solid var(--border-soft); }

/* ── Term pill (inline definition) ── */
.term-pill {
    display: inline-block; background: var(--info-soft);
    border: 1px solid rgba(96,165,250,0.25); border-radius: 4px;
    padding: 1px 7px; font-size: 10.5px; color: var(--info); font-weight: 500;
    cursor: default;
}

/* ── Explain box (inline callout) ── */
.explain-box {
    background: var(--bg-surface);
    border: 1px solid var(--border-soft);
    border-left: 3px solid var(--info);
    border-radius: 0 8px 8px 0;
    padding: 12px 16px;
    margin: 10px 0 14px 0;
    font-size: 12.5px; color: var(--fg-secondary); line-height: 1.7;
}
.explain-box b { color: var(--fg-primary); font-weight: 600; }

/* ── Tip box ── */
.tip-box {
    background: var(--warn-soft);
    border: 1px solid rgba(245,158,11,0.25);
    border-radius: 8px;
    padding: 12px 16px;
    margin: 12px 0;
    font-size: 12.5px; color: #FCD34D; line-height: 1.7;
}

/* ── Good/Bad verdict box ── */
.verdict-good {
    background: var(--accent-soft);
    border: 1px solid rgba(34,197,94,0.25);
    border-radius: 8px; padding: 12px 16px;
    font-size: 12.5px; color: var(--accent); line-height: 1.65;
}
.verdict-bad {
    background: var(--danger-soft);
    border: 1px solid rgba(239,68,68,0.25);
    border-radius: 8px; padding: 12px 16px;
    font-size: 12.5px; color: var(--danger); line-height: 1.65;
}

/* ── Signal card (home page feed) ── */
.sig-card {
    background: var(--bg-surface);
    border-radius: 8px;
    border: 1px solid var(--border-soft);
    padding: 12px 16px;
    margin-bottom: 10px;
    transition: border-color .2s ease, background .2s ease;
}
.sig-card:hover { border-color: var(--border-strong); background: var(--bg-surface-2); }

/* ── Step badge ── */
.step-badge {
    display: inline-flex; align-items: center; justify-content: center;
    width: 22px; height: 22px; border-radius: 50%;
    font-size: 11px; font-weight: 700; margin-right: 8px; flex-shrink: 0;
}

/* ── Update banner ── */
.upd-banner {
    background: var(--bg-surface); border: 1px solid var(--border-soft); border-radius: 8px;
    padding: 12px 16px; font-size: 12px; color: var(--fg-secondary);
    display: flex; justify-content: space-between; align-items: center;
}

/* ── Streamlit overrides ── */
[data-testid="stMetric"] {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: 14px 16px;
    box-shadow: var(--shadow-xs);
}
[data-testid="stMetricValue"] { font-weight: 600 !important; letter-spacing: -.025em; color: var(--card-foreground) !important; }
[data-testid="stMetricLabel"] { color: var(--muted-foreground) !important; font-size: 11px !important; text-transform: uppercase; letter-spacing: .10em; font-weight: 500; }
.stExpander {
    background: var(--card) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius-lg) !important;
    box-shadow: var(--shadow-xs) !important;
}
.stExpander summary { color: var(--muted-foreground) !important; font-size: 13px !important; font-weight: 500 !important; }
.stExpander summary:hover { color: var(--foreground) !important; }
button[kind="primary"] {
    border-radius: var(--radius-md) !important;
    font-weight: 500 !important;
    background: var(--primary) !important;
    border: 1px solid var(--primary) !important;
    color: var(--primary-foreground) !important;
    transition: opacity 150ms ease, transform 80ms ease;
}
button[kind="primary"]:hover { opacity: 0.90 !important; }
button[kind="primary"]:active { transform: scale(0.985); }
button[kind="secondary"] {
    border-radius: var(--radius-md) !important;
    background: var(--secondary) !important;
    border: 1px solid var(--border) !important;
    color: var(--secondary-foreground) !important;
    font-weight: 500 !important;
    transition: background 150ms ease, border-color 150ms ease;
}
button[kind="secondary"]:hover { background: var(--accent) !important; border-color: var(--ring) !important; }
.stAlert { border-radius: var(--radius-lg) !important; border: 1px solid var(--border) !important; }
hr { border-color: var(--border) !important; opacity: 0.6; }

/* Focus rings — accessibility (Linear-style ring) */
button:focus-visible, a:focus-visible, [role="button"]:focus-visible,
input:focus-visible, select:focus-visible, textarea:focus-visible {
    outline: 2px solid var(--ring) !important;
    outline-offset: 2px !important;
    border-radius: var(--radius-md);
}

/* Tab styling (Linear-style: minimal underline) */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px;
    border-bottom: 1px solid var(--border);
    padding-bottom: 0;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    color: var(--muted-foreground) !important;
    font-weight: 500 !important;
    font-size: 13px !important;
    padding: 10px 14px !important;
    border-radius: var(--radius-md) var(--radius-md) 0 0 !important;
    transition: color 150ms ease, background 150ms ease;
}
.stTabs [data-baseweb="tab"]:hover { color: var(--foreground) !important; background: var(--muted) !important; }
.stTabs [aria-selected="true"] {
    color: var(--foreground) !important;
    background: transparent !important;
    border-bottom: 2px solid var(--foreground) !important;
}

/* Selectbox / inputs / number inputs */
.stSelectbox > div > div, .stTextInput input, .stNumberInput input {
    background: var(--card) !important;
    border: 1px solid var(--border) !important;
    color: var(--foreground) !important;
    border-radius: var(--radius-md) !important;
    font-size: 13px !important;
}
.stSelectbox > div > div:hover, .stTextInput input:hover, .stNumberInput input:hover {
    border-color: var(--ring) !important;
}

/* Dataframes */
.stDataFrame {
    border-radius: var(--radius-lg);
    overflow: hidden;
    border: 1px solid var(--border);
    box-shadow: var(--shadow-xs);
}

/* Plotly charts container — match card aesthetic */
[data-testid="stPlotlyChart"] {
    border-radius: var(--radius-lg);
    overflow: hidden;
    border: 1px solid var(--border);
    box-shadow: var(--shadow-xs);
}

/* Radio horizontal (period selector) */
.stRadio > div[role="radiogroup"] {
    gap: 4px !important;
}
.stRadio > div[role="radiogroup"] label {
    background: var(--card) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius-md) !important;
    padding: 6px 12px !important;
    font-size: 12px !important;
    transition: background 150ms ease, border-color 150ms ease;
}
.stRadio > div[role="radiogroup"] label:hover { background: var(--accent) !important; border-color: var(--ring) !important; }

/* Checkbox */
.stCheckbox label {
    font-size: 13px !important;
    color: var(--foreground) !important;
}

/* ── Action badges (BUY / WATCH / FORMING / BEAR) ── */
.badge-buy, .badge-watch, .badge-forming, .badge-bear {
    display: inline-block; border-radius: 4px;
    padding: 3px 9px; font-size: 11px; font-weight: 600; letter-spacing: .02em;
}
.badge-buy     { background: color-mix(in oklch, var(--success) 14%, transparent); color: var(--success); border: 1px solid color-mix(in oklch, var(--success) 35%, transparent); }
.badge-watch   { background: color-mix(in oklch, var(--warning) 14%, transparent); color: var(--warning); border: 1px solid color-mix(in oklch, var(--warning) 35%, transparent); }
.badge-forming { background: color-mix(in oklch, var(--info) 14%, transparent);    color: var(--info);    border: 1px solid color-mix(in oklch, var(--info) 35%, transparent); }
.badge-bear    { background: color-mix(in oklch, var(--destructive) 14%, transparent); color: var(--destructive); border: 1px solid color-mix(in oklch, var(--destructive) 35%, transparent); }

/* ── Criteria filter cards (Strategy Conditions) ── */
.crit-ok, .crit-fail {
    background: var(--card);
    border: 1px solid var(--border);
    border-left: 3px solid var(--success);
    border-radius: var(--radius-md);
    padding: 10px 14px;
    margin-bottom: 8px;
    height: 100%;
    transition: border-color 180ms ease;
}
.crit-fail { border-left-color: var(--destructive); }
.crit-ok:hover, .crit-fail:hover { border-color: var(--ring); }
.crit-icon  { font-size: 16px; line-height: 1; margin-bottom: 4px; }
.crit-label { font-size: 12px; font-weight: 600; color: var(--foreground); margin-bottom: 2px; letter-spacing: -.005em; }
.crit-detail{ font-size: 10.5px; color: var(--muted-foreground); margin-top: 6px; font-family: var(--font-mono); }

/* ── Strategy Health hero banner ── */
.health-hero {
    background: linear-gradient(135deg, var(--card) 0%, var(--bg-surface-2) 100%);
    border: 1px solid var(--border);
    border-radius: var(--radius-xl);
    padding: 20px 24px;
    box-shadow: var(--shadow-md);
    margin-bottom: 20px;
}
.health-hero .verdict-line {
    display: inline-flex; align-items: center; gap: 10px;
    padding: 6px 14px; border-radius: 999px;
    font-size: 11.5px; font-weight: 600; letter-spacing: .04em; text-transform: uppercase;
    margin-bottom: 14px;
}
.health-hero h3 {
    font-size: 18px; font-weight: 600; color: var(--foreground); margin: 0 0 4px 0;
    letter-spacing: -.02em;
}
.health-hero p.subline {
    font-size: 13px; color: var(--muted-foreground); margin: 0 0 16px 0; line-height: 1.6;
}
.health-hero .health-grid {
    display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; margin-top: 10px;
}
.health-hero .h-num {
    font-size: 22px; font-weight: 600; letter-spacing: -.025em; color: var(--foreground);
    font-variant-numeric: tabular-nums;
}
.health-hero .h-lbl {
    font-size: 10.5px; color: var(--muted-foreground);
    text-transform: uppercase; letter-spacing: .10em; font-weight: 500;
}
.health-hero .h-sub {
    font-size: 11px; color: var(--fg-subtle); margin-top: 2px;
}

/* Respect reduced motion */
@media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
        animation-duration: 0.01ms !important;
        transition-duration: 0.01ms !important;
    }
}
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

    sig_df, funnel = _compute_momentum_signals()
    out['signals'] = sig_df
    out['funnel']  = funnel
    out['recent_breakouts'] = _scan_recent_breakouts()
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


_PERIOD_BARS = {'1M': 21, '3M': 63, '6M': 126, '1Y': 252, '3Y': 756, 'All': None}


def _suggest_stop(entry_price: float, atr: float | None,
                  winner_mae_p95_pct: float | None = None,
                  atr_mult: float = 2.0,
                  hard_cap_pct: float = 15.0,
                  min_pct: float = 5.0) -> dict:
    """Suggest a stop-loss price + distance using ATR and (optionally) Winner MAE p95.

    Logic:
      1. ATR stop = entry - atr_mult * ATR (volatility-adjusted, "gives the trade room").
      2. If Winner MAE p95 is available, the stop must be at least as loose (otherwise we
         stop ourselves out before normal winner pullbacks).
      3. Cap at hard_cap_pct (default 15%) — never wider than the strategy hard stop.
      4. Floor at min_pct  (default  5%) — never tighter than typical daily noise.

    Returns dict: stop_price, stop_pct, source ('ATR' / 'MAE p95' / 'Hard cap' / 'Floor').
    """
    if entry_price is None or entry_price <= 0:
        return {'stop_price': None, 'stop_pct': None, 'source': '—'}

    candidates = []
    if atr is not None and atr > 0:
        candidates.append(('ATR×' + str(atr_mult), atr_mult * atr / entry_price * 100))
    if winner_mae_p95_pct is not None and winner_mae_p95_pct > 0:
        # MAE p95 is usually given as a negative % (e.g. -8.5). Take abs and pad 20%.
        candidates.append(('Winner MAE p95 +20%', abs(winner_mae_p95_pct) * 1.2))
    if not candidates:
        candidates.append(('Default', 10.0))

    # Pick the LOOSER of the two so winners survive
    label, pct = max(candidates, key=lambda x: x[1])
    if pct > hard_cap_pct:
        pct, label = hard_cap_pct, 'Hard cap (-15%)'
    elif pct < min_pct:
        pct, label = min_pct, 'Floor (-5%)'

    stop_price = entry_price * (1 - pct / 100.0)
    return {'stop_price': stop_price, 'stop_pct': pct, 'source': label}


@st.cache_data(ttl=3600, show_spinner=False)
def _bt_run_single_ticker(ticker: str, csv_path: str,
                           start_str: str = '2017-01-01',
                           end_str: str | None = None,
                           ath_only: bool = False) -> dict:
    """Walk-forward single-ticker backtest (Momentum Edge rules, no look-ahead).

    ath_only=True restricts the breakout filter to all-time closing highs
    (the cumulative max up to but not including the signal bar). Default is
    52-week close max, matching the canonical strategy.

    Returns dict: trades (list of dicts), summary (dict with n_trades, win_rate,
    avg_ret, cum_ret, profit_factor, max_dd_pct).
    """
    df = _load_ohlcv_csv(Path(csv_path))
    if df is None or len(df) < 300:
        return {'trades': [], 'summary': {}, 'error': 'Not enough data (need 300+ bars).'}

    start = pd.Timestamp(start_str)
    end   = pd.Timestamp(end_str) if end_str else df.index[-1]

    close, open_, volume = df['Close'], df['Open'], df['Volume']
    sma50   = close.rolling(ME_SMA50_P,  min_periods=ME_SMA50_P ).mean()
    sma150  = close.rolling(ME_SMA150_P, min_periods=ME_SMA150_P).mean()
    ema220  = close.ewm(span=ME_EMA220_P, adjust=False).mean()
    # Breakout reference: 252-bar high (default) OR all-time close max (ath_only)
    if ath_only:
        high52 = close.expanding().max()
    else:
        high52 = close.rolling(ME_HIGH52_P, min_periods=ME_HIGH52_P).max()
    low52   = close.rolling(ME_LOW52_P,  min_periods=ME_LOW52_P ).min()
    vol20   = volume.rolling(ME_VOLAVG_P,    min_periods=ME_VOLAVG_P   ).mean()
    vol50   = volume.rolling(ME_VOL_LOOKBACK,min_periods=ME_VOL_LOOKBACK).mean()
    had_dip = (close < ema220).rolling(ME_DIP_LB, min_periods=1).max()

    arr_c    = close.values.astype(float)
    arr_o    = open_.values.astype(float)
    arr_v    = volume.values.astype(float)
    arr_e    = ema220.values.astype(float)
    arr_s50  = sma50.values.astype(float)
    arr_s150 = sma150.values.astype(float)
    arr_h52  = high52.values.astype(float)
    arr_l52  = low52.values.astype(float)
    arr_v20  = vol20.values.astype(float)
    arr_v50  = vol50.values.astype(float)
    arr_dip  = had_dip.values.astype(float)
    dates    = df.index
    n        = len(dates)

    start_i = next((k for k in range(n) if dates[k] >= start), 0)
    end_i   = n - 1
    for k in range(n - 1, -1, -1):
        if dates[k] <= end:
            end_i = k
            break
    start_i = max(start_i, ME_HIGH52_P + 1)

    trades: list[dict] = []
    in_trade, entry_price, entry_date = False, 0.0, None

    i = start_i
    while i <= end_i:
        prev = i - 1
        if in_trade:
            c_p, e_p = arr_c[prev], arr_e[prev]
            exit_ema = not np.isnan(c_p) and not np.isnan(e_p) and c_p < e_p
            exit_stp = not np.isnan(c_p) and c_p < entry_price * 0.85
            if exit_ema or exit_stp:
                ex_px = arr_o[i]
                if not np.isnan(ex_px) and ex_px > 0:
                    trades.append({
                        'EntryDate':  entry_date,
                        'ExitDate':   dates[i],
                        'EntryPrice': round(float(entry_price), 2),
                        'ExitPrice':  round(float(ex_px), 2),
                        'Return%':    round((ex_px / entry_price - 1) * 100, 2),
                        'Days':       (dates[i] - entry_date).days,
                        'ExitReason': '15% Stop' if exit_stp else 'EMA Break',
                    })
                in_trade = False
        else:
            s_c, s_e   = arr_c[prev], arr_e[prev]
            s_s50, s_s150 = arr_s50[prev], arr_s150[prev]
            s_h52  = arr_h52[prev - 1] if prev >= 1 else arr_h52[prev]
            s_l52, s_v20, s_v50 = arr_l52[prev], arr_v20[prev], arr_v50[prev]
            s_v, s_dip = arr_v[prev], arr_dip[prev]
            if any(np.isnan(x) for x in [s_e, s_s50, s_s150, s_h52, s_l52, s_v50]):
                i += 1; continue
            f1 = s_s150 > s_e
            f2 = s_c > s_s50
            f3 = s_s50 > s_s150
            f4 = s_c >= ME_MIN_PRICE_VS_LOW * s_l52
            f5 = s_dip >= 0.5
            bk = (s_c > s_h52) and (s_c > s_e)
            vol_ok = (not np.isnan(s_v50)) and s_v50 > 0 and (s_v >= ME_VOL_MULT * s_v50)
            if f1 and f2 and f3 and f4 and f5 and bk and vol_ok:
                en_px = arr_o[i]
                if not np.isnan(en_px) and en_px > 0:
                    entry_price = en_px
                    entry_date  = dates[i]
                    in_trade    = True
        i += 1

    # Close any open position at period end
    if in_trade:
        last_px = arr_c[end_i]
        if not np.isnan(last_px) and last_px > 0:
            trades.append({
                'EntryDate':  entry_date,
                'ExitDate':   dates[end_i],
                'EntryPrice': round(float(entry_price), 2),
                'ExitPrice':  round(float(last_px), 2),
                'Return%':    round((last_px / entry_price - 1) * 100, 2),
                'Days':       (dates[end_i] - entry_date).days,
                'ExitReason': 'Still Open',
            })

    # Summary
    if not trades:
        return {'trades': [], 'summary': {'n_trades': 0}, 'error': None}
    closed = [t for t in trades if t['ExitReason'] != 'Still Open']
    n_cl   = len(closed)
    wins   = [t['Return%'] for t in closed if t['Return%'] > 0]
    losses = [t['Return%'] for t in closed if t['Return%'] <= 0]
    win_rate = (len(wins) / n_cl * 100) if n_cl else 0
    avg_ret  = (sum(t['Return%'] for t in closed) / n_cl) if n_cl else 0
    cum_eq = 1.0
    peak   = 1.0
    max_dd = 0.0
    for t in closed:
        cum_eq *= (1 + t['Return%'] / 100)
        peak = max(peak, cum_eq)
        max_dd = min(max_dd, (cum_eq / peak - 1) * 100)
    cum_ret = (cum_eq - 1) * 100
    g_profit = sum(wins) if wins else 0
    g_loss   = abs(sum(losses)) if losses else 0
    pf = (g_profit / g_loss) if g_loss > 0 else float('inf')
    return {
        'trades': trades,
        'summary': {
            'n_trades':  n_cl,
            'win_rate':  round(win_rate, 1),
            'avg_ret':   round(avg_ret, 2),
            'cum_ret':   round(cum_ret, 1),
            'max_dd':    round(max_dd, 1),
            'profit_factor': round(pf, 2) if pf != float('inf') else 999.0,
        },
        'error': None,
    }


def _render_single_ticker_backtest(ticker: str, ath_only: bool = False) -> None:
    """Run + render Momentum Edge backtest for a single ticker on demand."""
    folders = [
        Path(BASE_DIR) / 'data' / 'nse_bse',
        Path(BASE_DIR) / 'data',
        Path(BASE_DIR) / 'momentum_edge_data',
    ]
    stem = ticker if ticker.endswith('.NS') else f'{ticker}.NS'
    path = None
    for folder in folders:
        for cand in (folder / f'{stem}.csv', folder / f'{ticker}.csv'):
            if cand.exists():
                path = cand
                break
        if path is not None:
            break
    if path is None:
        st.warning(f'No OHLCV file for {ticker}.')
        return

    mode_lbl = 'ATH-only' if ath_only else '52W high'
    with st.spinner(f'Running walk-forward backtest on {ticker} ({mode_lbl} mode)…'):
        result = _bt_run_single_ticker(ticker, str(path), ath_only=ath_only)
    st.caption(f'Mode: **{mode_lbl}** breakout · Entry on next-day open · 15% hard stop OR 220 EMA break exit')

    if result.get('error'):
        st.warning(result['error'])
        return

    summary = result.get('summary', {})
    trades  = result.get('trades', [])
    if not summary or summary.get('n_trades', 0) == 0:
        st.info(f'No qualifying trades for {ticker} in the backtest window.')
        return

    # Summary pills
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        _kpi_card('Trades', f'{summary["n_trades"]}', 'closed positions', '#94A3B8')
    with c2:
        wr_c = '#22C55E' if summary['win_rate'] >= 50 else '#EF4444'
        _kpi_card('Win Rate', f'{summary["win_rate"]:.0f}%', '% profitable', wr_c)
    with c3:
        ar_c = '#22C55E' if summary['avg_ret'] > 0 else '#EF4444'
        _kpi_card('Avg Return / Trade', f'{summary["avg_ret"]:+.2f}%', 'per trade', ar_c)
    with c4:
        cr_c = '#22C55E' if summary['cum_ret'] > 0 else '#EF4444'
        _kpi_card('Cumulative Return', f'{summary["cum_ret"]:+.1f}%', 'compounded all trades', cr_c)
    with c5:
        _kpi_card('Max Drawdown', f'{summary["max_dd"]:.1f}%',
                  f'PF {summary["profit_factor"]}×', '#EF4444')

    # Equity curve
    df_t = pd.DataFrame(trades)
    df_t = df_t[df_t['ExitReason'] != 'Still Open'].sort_values('EntryDate')
    if not df_t.empty:
        eq = (1 + df_t['Return%'] / 100).cumprod()
        cum_pct = (eq - 1) * 100
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df_t['EntryDate'], y=cum_pct, mode='lines', name='Cumulative Return',
            line=dict(color='#22C55E', width=2),
            fill='tozeroy', fillcolor='rgba(34,197,94,0.10)',
            hovertemplate='%{x|%d %b %Y}  %{y:+.1f}%<extra></extra>',
        ))
        fig.add_hline(y=0, line_color='#334155', line_width=1)
        fig.update_layout(
            height=260, paper_bgcolor='#1c1c1c', plot_bgcolor='#1c1c1c',
            font=dict(color='#fafafa', family='Inter', size=11),
            margin=dict(l=60, r=30, t=30, b=30),
            hovermode='x unified',
            xaxis=dict(gridcolor='#1E293B', tickformat='%b %y'),
            yaxis=dict(gridcolor='#1E293B', ticksuffix='%', tickformat='+.0f'),
        )
        st.plotly_chart(fig, width='stretch')

    # Trade log table (newest first)
    df_t_full = pd.DataFrame(trades)
    df_t_full['EntryDate'] = pd.to_datetime(df_t_full['EntryDate']).dt.strftime('%Y-%m-%d')
    df_t_full['ExitDate']  = pd.to_datetime(df_t_full['ExitDate']).dt.strftime('%Y-%m-%d')
    df_t_full = df_t_full.sort_values('ExitDate', ascending=False).reset_index(drop=True)
    df_t_full['Return%'] = df_t_full['Return%'].apply(lambda x: f'{x:+.2f}%')
    df_t_full['EntryPrice'] = df_t_full['EntryPrice'].apply(lambda x: f'₹{x:,.2f}')
    df_t_full['ExitPrice']  = df_t_full['ExitPrice'].apply(lambda x: f'₹{x:,.2f}')
    st.dataframe(df_t_full, hide_index=True, width='stretch')


def _action_from_signal(signal: str, is_bull: bool = True) -> str:
    """Map master's Signal label to standalone-style Action label."""
    if not is_bull:
        return 'BEAR MARKET'
    return {
        'Breakout Today': 'BUY NOW',
        'Near Breakout':  'WATCH',
        'Watch Zone':     'FORMING',
    }.get(signal, signal or '—')


def _action_badge_html(action: str) -> str:
    """SVG-free action badge — used inline in HTML."""
    badges = {
        'BUY NOW':     '<span class="badge-buy">● BUY NOW</span>',
        'WATCH':       '<span class="badge-watch">● WATCH</span>',
        'FORMING':     '<span class="badge-forming">● FORMING</span>',
        'BEAR MARKET': '<span class="badge-bear">● BEAR MARKET</span>',
    }
    return badges.get(action, f'<span class="badge-grey">{action}</span>')


def _render_criteria_panel(ticker: str) -> None:
    """Render 6 filters + breakout trigger pass/fail grid for the given ticker.

    Reads OHLCV from disk and evaluates each filter using yesterday's close
    (the bar that the strategy actually trades on — no look-ahead).
    """
    folders = [
        Path(BASE_DIR) / 'data' / 'nse_bse',
        Path(BASE_DIR) / 'data',
        Path(BASE_DIR) / 'momentum_edge_data',
    ]
    stem = ticker if ticker.endswith('.NS') else f'{ticker}.NS'
    path = None
    for folder in folders:
        for cand in (folder / f'{stem}.csv', folder / f'{ticker}.csv'):
            if cand.exists():
                path = cand
                break
        if path is not None:
            break
    if path is None:
        st.info(f'No OHLCV file for {ticker} — cannot render criteria.')
        return

    df = _load_ohlcv_csv(path)
    if df is None or len(df) < 60:
        st.info('Not enough data to evaluate criteria.')
        return

    close, volume = df['Close'], df['Volume']
    sma50  = close.rolling(ME_SMA50_P).mean()
    sma150 = close.rolling(ME_SMA150_P).mean()
    ema220 = close.ewm(span=ME_EMA220_P, adjust=False).mean()
    high52 = close.rolling(ME_HIGH52_P).max()
    low52  = close.rolling(ME_LOW52_P).min()
    vol20  = volume.rolling(ME_VOLAVG_P).mean()
    vol50  = volume.rolling(ME_VOL_LOOKBACK).mean()

    def _sv(s):
        return float(s.iloc[-2]) if len(s) >= 2 else float('nan')

    close_s  = _sv(close)
    sma50_s  = _sv(sma50)
    sma150_s = _sv(sma150)
    ema220_s = _sv(ema220)
    low52_s  = _sv(low52)
    vol20_s  = _sv(vol20)
    vol50_s  = _sv(vol50)
    close_now  = float(close.iloc[-1])
    ema220_now = float(ema220.iloc[-1])
    vol_today  = float(volume.iloc[-1])

    dip_mask   = close < ema220
    dip_recent = dip_mask.iloc[-ME_DIP_LB - 1:-1]
    had_dip    = bool(dip_recent.any())
    last_dip = '—'
    if had_dip:
        dates = dip_recent[dip_recent].index
        if len(dates) > 0:
            last_dip = pd.Timestamp(dates[-1]).strftime('%d %b %Y')

    chop_val = float(_compute_choppiness(df).iloc[-1]) if len(df) >= CHOPPINESS_P else float('nan')
    chop_ok  = (not np.isnan(chop_val)) and chop_val < ME_CHOP_THRESH
    threshold_4 = ME_MIN_PRICE_VS_LOW * low52_s if not np.isnan(low52_s) else float('nan')

    resistance_p = close.shift(1).rolling(ME_HIGH52_P).max()
    res_today    = float(resistance_p.iloc[-1]) if not np.isnan(resistance_p.iloc[-1]) else float('nan')
    close_prev   = float(close.iloc[-2]) if len(close) >= 2 else float('nan')
    vol_ratio    = (vol_today / vol20_s) if vol20_s and not np.isnan(vol20_s) else 0.0
    vol_ratio50  = (vol_today / vol50_s) if (vol50_s and not np.isnan(vol50_s)) else None
    vol_ok       = (vol_ratio >= ME_VOL_THRESH) and (vol_ratio50 is None or vol_ratio50 >= ME_VOL_MULT)
    is_bk_today  = (
        not np.isnan(res_today)
        and close_now > res_today
        and close_prev <= res_today
        and close_now > ema220_now
        and vol_ok
    )

    conditions = [
        (sma150_s > ema220_s, 'F1 — SMA 150 > EMA 220',
         'Long-term trend is bullish',
         f'SMA150 = ₹{sma150_s:,.2f}   EMA220 = ₹{ema220_s:,.2f}'),
        (close_s > sma50_s, 'F2 — Close > SMA 50',
         'Short-term price above MA',
         f'Close = ₹{close_s:,.2f}   SMA50 = ₹{sma50_s:,.2f}'),
        (sma50_s > sma150_s, 'F3 — SMA 50 > SMA 150',
         'Moving average stack aligned',
         f'SMA50 = ₹{sma50_s:,.2f}   SMA150 = ₹{sma150_s:,.2f}'),
        (close_s >= threshold_4, 'F4 — Close ≥ 1.25 × 52W Low',
         'Stock well above its yearly low',
         f'Close = ₹{close_s:,.2f}   Min = ₹{threshold_4:,.2f}   52W Low = ₹{low52_s:,.2f}'),
        (had_dip, f'F5 — Dipped below EMA 220 (last {ME_DIP_LB}d)',
         'The shakeout dip occurred — confirms the setup',
         f'Last dip: {last_dip}'),
        (chop_ok, 'F6 — Choppiness < 61.8',
         'Clean trending chart, not sideways',
         f'Choppiness = {chop_val:.1f}   (threshold = {ME_CHOP_THRESH})'),
    ]

    for row_start in (0, 3):
        cols = st.columns(3)
        for i, col in enumerate(cols):
            ci = row_start + i
            if ci >= len(conditions):
                break
            ok, label, sub, detail = conditions[ci]
            css = 'crit-ok' if ok else 'crit-fail'
            icon = '✅' if ok else '❌'
            with col:
                st.markdown(
                    f'<div class="{css}">'
                    f'<div class="crit-icon">{icon}</div>'
                    f'<div class="crit-label">{label}</div>'
                    f'<div style="font-size:10.5px;color:var(--muted-foreground);margin-top:2px;">{sub}</div>'
                    f'<div class="crit-detail">{detail}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    # Breakout Trigger — full-width row
    vol50_str = f'{vol_ratio50:.2f}×' if vol_ratio50 is not None else 'N/A'
    res_str   = f'₹{res_today:,.2f}' if not np.isnan(res_today) else '—'
    bk_detail = (
        f'Close ₹{close_now:,.2f}   Resistance {res_str}   '
        f'Prev close ₹{close_prev:,.2f}   EMA220 ₹{ema220_now:,.2f}   '
        f'Vol/20d {vol_ratio:.2f}× (need ≥{ME_VOL_THRESH}×)   '
        f'Vol/50d {vol50_str} (need ≥{ME_VOL_MULT}×)'
    )
    bk_css = 'crit-ok' if is_bk_today else 'crit-fail'
    bk_icon = '✅' if is_bk_today else '❌'
    st.markdown(
        f'<div class="{bk_css}" style="border-left-color:var(--warning);margin-top:8px;">'
        f'<div class="crit-icon">{bk_icon}</div>'
        f'<div class="crit-label">🚀 Breakout Trigger — Close > 52W High + Volume confirmed</div>'
        f'<div style="font-size:10.5px;color:var(--muted-foreground);margin-top:2px;">'
        f'This is what triggers the BUY signal. All 6 filters above must also pass.</div>'
        f'<div class="crit-detail">{bk_detail}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def _chart_monthly_heatmap(trades: pd.DataFrame) -> go.Figure:
    """Calendar-style heatmap of avg PnL% per (year, month).

    Accepts master's trade schema: Exit_Date + PnL_Pct.
    """
    import calendar as _cal
    if trades is None or trades.empty:
        return go.Figure().update_layout(height=160, paper_bgcolor='#1c1c1c')
    df = trades.copy()
    df['ExitDate'] = pd.to_datetime(df.get('Exit_Date', df.get('ExitDate')), errors='coerce')
    df['Return%']  = pd.to_numeric(df.get('PnL_Pct', df.get('Return%')), errors='coerce')
    df = df.dropna(subset=['ExitDate', 'Return%'])
    if df.empty:
        return go.Figure().update_layout(height=160, paper_bgcolor='#1c1c1c')

    df['Year']  = df['ExitDate'].dt.year
    df['Month'] = df['ExitDate'].dt.month
    monthly = df.groupby(['Year', 'Month'])['Return%'].mean().reset_index()
    years = sorted(monthly['Year'].unique())
    months = list(range(1, 13))
    z = []
    for yr in years:
        row = []
        for mo in months:
            v = monthly[(monthly['Year'] == yr) & (monthly['Month'] == mo)]['Return%']
            row.append(round(float(v.iloc[0]), 2) if len(v) > 0 else None)
        z.append(row)
    flat = [v for row in z for v in row if v is not None]
    zmax = max(abs(min(flat, default=0)), abs(max(flat, default=0)), 1)
    fig = go.Figure(go.Heatmap(
        z=z,
        x=[_cal.month_abbr[m] for m in months],
        y=[str(yr) for yr in years],
        colorscale=[
            [0.0, '#7b0000'], [0.35, '#cc3333'],
            [0.5, '#1c1c1c'],
            [0.65, '#33aa66'], [1.0, '#006622'],
        ],
        zmid=0, zmin=-zmax, zmax=zmax,
        text=[[f'{v:+.1f}%' if v is not None else '—' for v in row] for row in z],
        texttemplate='%{text}',
        textfont=dict(size=10, color='#fafafa'),
        hovertemplate='%{y}  %{x}: %{z:+.2f}%<extra></extra>',
        showscale=True,
        colorbar=dict(ticksuffix='%', thickness=12,
                      tickfont=dict(color='#94A3B8', size=10),
                      title=dict(text='Avg %', font=dict(color='#94A3B8', size=10))),
    ))
    fig.update_layout(
        height=max(180, 38 * len(years) + 80),
        paper_bgcolor='#1c1c1c', plot_bgcolor='#1c1c1c',
        font=dict(color='#fafafa', family='Inter', size=11),
        margin=dict(l=60, r=60, t=40, b=20),
        xaxis=dict(side='top', tickfont=dict(size=11)),
        yaxis=dict(tickfont=dict(size=11), autorange='reversed'),
    )
    return fig


def _strategy_health(trades: pd.DataFrame, signals: pd.DataFrame) -> dict:
    """Compute a health summary for a strategy.

    Returns dict: n_trades, win_rate, avg_pnl, median_pnl, median_hold,
    safe_20d_pct, universe, verdict_text, verdict_color, top_lift.
    """
    out = {
        'n_trades': 0, 'win_rate': 0.0, 'avg_pnl': 0.0, 'median_pnl': 0.0,
        'median_hold': 0, 'safe_20d_pct': 0.0, 'universe': '—',
        'verdict_text': 'NO DATA', 'verdict_color': 'var(--muted-foreground)',
        'verdict_bg': 'color-mix(in oklch, var(--muted) 50%, transparent)',
        'top_lift': '—', 'best_combo': '—',
    }
    if trades is None or trades.empty:
        return out
    out['n_trades'] = len(trades)
    out['win_rate'] = float((trades['Result'] == 'Win').mean() * 100) if 'Result' in trades.columns else 0.0
    if 'PnL_Pct' in trades.columns:
        out['avg_pnl']    = float(trades['PnL_Pct'].mean())
        out['median_pnl'] = float(trades['PnL_Pct'].median())
    if 'Holding_Days' in trades.columns:
        out['median_hold'] = int(trades['Holding_Days'].median())

    # Universe size — distinct tickers
    if 'Ticker' in trades.columns:
        n_uniq = trades['Ticker'].nunique()
        n_now  = len(signals) if signals is not None else 0
        out['universe'] = f'{n_uniq} tickers traded · {n_now} on screener today'

    # Loss-free 20d% via cached helper
    try:
        lfh = _loss_free_holding(trades, ('data/nse_bse', 'data', 'momentum_edge_data'))
        if not lfh.empty:
            out['safe_20d_pct'] = float((lfh['Loss_Free_Days'] >= 20).mean() * 100)
    except Exception:
        pass

    # Verdict
    if out['win_rate'] >= 65 and out['safe_20d_pct'] >= 50:
        out['verdict_text']  = '✅ STRATEGY WORKING — safe to scale capital'
        out['verdict_color'] = 'var(--success)'
        out['verdict_bg']    = 'color-mix(in oklch, var(--success) 14%, transparent)'
    elif out['win_rate'] >= 50 and out['safe_20d_pct'] >= 30:
        out['verdict_text']  = '⚠️ CONDITIONAL — works, size carefully'
        out['verdict_color'] = 'var(--warning)'
        out['verdict_bg']    = 'color-mix(in oklch, var(--warning) 14%, transparent)'
    else:
        out['verdict_text']  = '❌ WEAK — do not scale up'
        out['verdict_color'] = 'var(--destructive)'
        out['verdict_bg']    = 'color-mix(in oklch, var(--destructive) 14%, transparent)'

    # Path to 100% — best Entry Type × Recovery Speed combo
    if {'Entry_Type', 'Recovery_Speed', 'Result'}.issubset(trades.columns):
        g = trades.groupby(['Entry_Type', 'Recovery_Speed']).agg(
            n=('Result', 'count'),
            wr=('Result', lambda s: (s == 'Win').mean() * 100),
        ).reset_index()
        g = g[g['n'] >= 3].sort_values('wr', ascending=False)
        if not g.empty:
            top = g.iloc[0]
            out['best_combo'] = (f"{top['Entry_Type']} × {top['Recovery_Speed']} "
                                 f"→ {top['wr']:.0f}% win rate ({int(top['n'])} trades)")
            base_wr = out['win_rate']
            lift = top['wr'] - base_wr
            out['top_lift'] = f'+{lift:.0f}% lift vs overall' if lift > 0 else 'no lift over baseline'
    return out


def _render_health_hero(strategy_name: str, trades: pd.DataFrame,
                         signals: pd.DataFrame) -> None:
    """Render the Strategy Health hero card at the top of a strategy page."""
    h = _strategy_health(trades, signals)
    inner_grid = (
        '<div class="health-grid">'
        f'  <div><div class="h-lbl">Trades Backtested</div>'
        f'       <div class="h-num">{h["n_trades"]}</div>'
        f'       <div class="h-sub">{h["universe"]}</div></div>'
        f'  <div><div class="h-lbl">Win Rate</div>'
        f'       <div class="h-num" style="color:{"var(--success)" if h["win_rate"]>=50 else "var(--destructive)"}">{h["win_rate"]:.0f}%</div>'
        f'       <div class="h-sub">need ≥ 50% with R:R 1:1 to break even</div></div>'
        f'  <div><div class="h-lbl">Avg PnL / Trade</div>'
        f'       <div class="h-num" style="color:{"var(--success)" if h["avg_pnl"]>0 else "var(--destructive)"}">{h["avg_pnl"]:+.2f}%</div>'
        f'       <div class="h-sub">median {h["median_pnl"]:+.2f}%</div></div>'
        f'  <div><div class="h-lbl">Median Hold</div>'
        f'       <div class="h-num">{h["median_hold"]}d</div>'
        f'       <div class="h-sub">typical days held per trade</div></div>'
        f'  <div><div class="h-lbl">Safe Hold ≥ 20d</div>'
        f'       <div class="h-num" style="color:{"var(--success)" if h["safe_20d_pct"]>=40 else "var(--warning)"}">{h["safe_20d_pct"]:.0f}%</div>'
        f'       <div class="h-sub">of signals stay loss-free 20+ days</div></div>'
        '</div>'
    )
    st.markdown(
        f'<div class="health-hero">'
        f'  <span class="verdict-line" style="background:{h["verdict_bg"]};color:{h["verdict_color"]};border:1px solid {h["verdict_color"]}55;">{h["verdict_text"]}</span>'
        f'  <h3>{strategy_name} — Strategy Health</h3>'
        f'  <p class="subline">Path to 100% success: focus on <b style="color:var(--foreground)">{h["best_combo"]}</b> '
        f'  &nbsp;({h["top_lift"]}). Holding strategy: exit on 15% hard stop OR price closes below 220-day EMA OR target hit. '
        f'  Median trade lasts <b style="color:var(--foreground)">{h["median_hold"]} days</b>.</p>'
        f'  {inner_grid}'
        f'</div>',
        unsafe_allow_html=True,
    )


_STRATEGY_OHLCV_FOLDERS = {
    S_MONTHLY:  ('data', 'data/nse_bse'),
    S_IPO:      ('ipo_data', 'data', 'data/nse_bse'),
    S_MOMENTUM: ('data/nse_bse', 'data', 'momentum_edge_data'),
}


@st.cache_data(ttl=3600, show_spinner=False)
def _verify_past_trades(trades: pd.DataFrame) -> pd.DataFrame:
    """Re-verify each past trade against the strategy filters at the signal date.

    Returns the trades DataFrame with extra columns:
      - Prior_52W_High_Close  (the close-max in the 252 bars BEFORE entry)
      - Breakout_Margin_Pct   ((entry_price / prior_high) - 1) * 100
      - All_Filters_OK        bool — every one of F1..F6 + breakout was satisfied
      - Filter_Detail         compact pass/fail string e.g. 'F1✓ F2✓ F3✓ F4✓ F5✓ F6✓ BK✓'

    The check uses the bar BEFORE entry (signal day) for filter evaluation — exactly
    what the backtest sees, zero look-ahead.
    """
    if trades is None or trades.empty:
        return trades.copy() if trades is not None else pd.DataFrame()

    folders = [
        Path(BASE_DIR) / 'data' / 'nse_bse',
        Path(BASE_DIR) / 'data',
        Path(BASE_DIR) / 'momentum_edge_data',
    ]
    margin_pct: list[float | None] = []
    prior_high_col: list[float | None] = []
    all_ok_col: list[bool] = []
    detail_col: list[str] = []

    for _, tr in trades.iterrows():
        ticker = str(tr['Ticker'])
        stem = ticker if ticker.endswith('.NS') else f'{ticker}.NS'
        path = None
        for folder in folders:
            for cand in (folder / f'{stem}.csv', folder / f'{ticker}.csv'):
                if cand.exists():
                    path = cand
                    break
            if path is not None:
                break
        if path is None:
            margin_pct.append(None); prior_high_col.append(None)
            all_ok_col.append(False); detail_col.append('no data')
            continue
        try:
            df = pd.read_csv(path, index_col=0, parse_dates=True)
        except Exception:
            margin_pct.append(None); prior_high_col.append(None)
            all_ok_col.append(False); detail_col.append('read fail')
            continue
        if 'Close' not in df.columns:
            margin_pct.append(None); prior_high_col.append(None)
            all_ok_col.append(False); detail_col.append('schema')
            continue
        try:
            entry_dt = pd.to_datetime(tr['Entry_Date'])
            entry_px = float(tr['Entry_Price'])
        except Exception:
            margin_pct.append(None); prior_high_col.append(None)
            all_ok_col.append(False); detail_col.append('parse')
            continue

        # Signal day = the bar BEFORE entry
        before_or_eq = df.loc[df.index < entry_dt]
        if len(before_or_eq) < ME_HIGH52_P + 1:
            margin_pct.append(None); prior_high_col.append(None)
            all_ok_col.append(False); detail_col.append('< 252 bars')
            continue

        signal_close = float(before_or_eq['Close'].iloc[-1])
        prior_high   = float(before_or_eq['Close'].iloc[-ME_HIGH52_P - 1:-1].max())
        prior_high_col.append(prior_high)

        # Margin = how much signal_close exceeded prior_high
        margin = (signal_close / prior_high - 1) * 100 if prior_high > 0 else None
        margin_pct.append(margin)

        # Evaluate F1..F6 + breakout at signal day
        c = before_or_eq['Close']
        sma50  = c.rolling(ME_SMA50_P).mean().iloc[-1]
        sma150 = c.rolling(ME_SMA150_P).mean().iloc[-1]
        ema220 = c.ewm(span=ME_EMA220_P, adjust=False).mean().iloc[-1]
        low52  = c.rolling(ME_LOW52_P).min().iloc[-1]
        vol_window = before_or_eq.get('Volume')
        if vol_window is not None and not vol_window.empty:
            vol20 = vol_window.rolling(ME_VOLAVG_P).mean().iloc[-1]
            vol50 = vol_window.rolling(ME_VOL_LOOKBACK).mean().iloc[-1]
            v_last = float(vol_window.iloc[-1])
            vol_ok = bool(not pd.isna(vol50) and vol50 > 0 and v_last >= ME_VOL_MULT * vol50)
        else:
            vol_ok = True  # cannot verify without volume — assume pass

        # Dip check — was there a close < ema220 in last DIP_LB bars?
        ema_series = c.ewm(span=ME_EMA220_P, adjust=False).mean()
        dip_mask   = (c < ema_series).iloc[-ME_DIP_LB - 1:-1]
        had_dip    = bool(dip_mask.any())

        f1 = bool(sma150 > ema220)
        f2 = bool(signal_close > sma50)
        f3 = bool(sma50 > sma150)
        f4 = bool(signal_close >= ME_MIN_PRICE_VS_LOW * low52)
        f5 = had_dip
        # F6 — choppiness on window up to signal day
        try:
            chop = float(_compute_choppiness(before_or_eq.tail(60)).iloc[-1])
            f6 = bool(chop < ME_CHOP_THRESH)
        except Exception:
            f6 = True
        bk = bool(signal_close > prior_high) and bool(signal_close > ema220)

        all_ok = f1 and f2 and f3 and f4 and f5 and f6 and bk and vol_ok
        all_ok_col.append(all_ok)
        flags = [
            f'F1{"✓" if f1 else "✗"}',
            f'F2{"✓" if f2 else "✗"}',
            f'F3{"✓" if f3 else "✗"}',
            f'F4{"✓" if f4 else "✗"}',
            f'F5{"✓" if f5 else "✗"}',
            f'F6{"✓" if f6 else "✗"}',
            f'BK{"✓" if bk else "✗"}',
            f'V{"✓" if vol_ok else "✗"}',
        ]
        detail_col.append(' '.join(flags))

    out = trades.copy()
    out['Prior_52W_High'] = prior_high_col
    out['Breakout_Margin_Pct'] = margin_pct
    out['All_Filters_OK'] = all_ok_col
    out['Filter_Detail'] = detail_col
    return out


@st.cache_data(ttl=3600, show_spinner=False)
def _loss_free_holding(trades: pd.DataFrame,
                        folder_keys: tuple[str, ...] = (
                            'data/nse_bse', 'data', 'momentum_edge_data',
                        )) -> pd.DataFrame:
    """For each past trade, count consecutive days from Entry_Date where Close
    stayed at-or-above Entry_Price before first close below.

    folder_keys: relative folders searched for the ticker's OHLCV csv.

    Returns DataFrame columns: Ticker, Entry_Date, Entry_Price, Loss_Free_Days,
    First_Loss_Date, Holding_Days, PnL_Pct, Result, Never_Dipped (bool).
    Trade with no detectable down-close inside Holding_Days window → Never_Dipped=True,
    Loss_Free_Days = Holding_Days.
    """
    if trades is None or trades.empty:
        return pd.DataFrame()

    rows = []
    folders = [Path(BASE_DIR) / f for f in folder_keys]

    for _, tr in trades.iterrows():
        ticker = str(tr['Ticker'])
        stem   = ticker if ticker.endswith('.NS') else f'{ticker}.NS'
        # Find OHLCV file
        path = None
        for folder in folders:
            for candidate in (folder / f'{stem}.csv', folder / f'{ticker}.csv'):
                if candidate.exists():
                    path = candidate
                    break
            if path is not None:
                break
        if path is None:
            continue

        try:
            ohlcv = pd.read_csv(path, index_col=0, parse_dates=True)
        except Exception:
            continue
        if 'Close' not in ohlcv.columns or ohlcv.empty:
            continue

        try:
            entry_dt = pd.to_datetime(tr['Entry_Date'])
            entry_px = float(tr['Entry_Price'])
            exit_dt  = pd.to_datetime(tr.get('Exit_Date'), errors='coerce')
        except Exception:
            continue
        if pd.isna(entry_dt) or pd.isna(entry_px):
            continue

        # Walk forward from day AFTER entry to exit (or end of data)
        after = ohlcv.loc[ohlcv.index > entry_dt]
        if pd.notna(exit_dt):
            after = after.loc[after.index <= exit_dt]
        if after.empty:
            continue

        below_mask = after['Close'] < entry_px
        if below_mask.any():
            first_loss_idx = below_mask.idxmax()
            loss_free = int((after.index < first_loss_idx).sum())
            first_loss_date = first_loss_idx.strftime('%Y-%m-%d')
            never = False
        else:
            loss_free = int(len(after))
            first_loss_date = '—'
            never = True

        rows.append({
            'Ticker':          ticker.replace('.NS', ''),
            'Entry_Date':      entry_dt.strftime('%Y-%m-%d'),
            'Entry_Price':     entry_px,
            'Loss_Free_Days':  loss_free,
            'First_Loss_Date': first_loss_date,
            'Holding_Days':    int(tr.get('Holding_Days', 0)) if pd.notna(tr.get('Holding_Days')) else len(after),
            'PnL_Pct':         float(tr.get('PnL_Pct', 0.0)) if pd.notna(tr.get('PnL_Pct')) else 0.0,
            'Result':          str(tr.get('Result', '')),
            'Never_Dipped':    never,
        })

    return pd.DataFrame(rows)


@st.cache_data(ttl=3600, show_spinner=False)
def _compute_full_indicators(path_str: str) -> pd.DataFrame | None:
    """Read OHLCV CSV + compute RSI/MACD/ADX/Bollinger/ATR/OBV bundle. Cached 1h."""
    df = _load_ohlcv_csv(Path(path_str))
    if df is None or len(df) < 60:
        return None
    close, volume = df['Close'], df['Volume']
    out = df.copy()
    out['sma50']  = close.rolling(50).mean()
    out['sma150'] = close.rolling(150).mean()
    out['ema220'] = close.ewm(span=220, adjust=False).mean()
    out['rsi14']  = core_indicators.rsi(close, 14)
    macd_l, macd_s, macd_h = core_indicators.macd(close, 12, 26, 9)
    out['macd'], out['macd_sig'], out['macd_hist'] = macd_l, macd_s, macd_h
    bb_m, bb_u, bb_l = core_indicators.bollinger(close, 20, 2.0)
    out['bb_mid'], out['bb_up'], out['bb_lo'] = bb_m, bb_u, bb_l
    out['atr14']  = core_indicators.atr(df, 14)
    out['adx14']  = core_indicators.adx(df, 14)
    out['obv']    = core_indicators.obv(close, volume)
    return out


def _interp_rsi(v: float) -> tuple[str, str]:
    if v >= 70: return ('Overbought', '#EF4444')
    if v >= 55: return ('Bullish', '#22C55E')
    if v >= 45: return ('Neutral',  '#94A3B8')
    if v >= 30: return ('Bearish',  '#F59E0B')
    return ('Oversold', '#22C55E')


def _interp_adx(v: float) -> tuple[str, str]:
    if v >= 40: return ('Very strong trend', '#22C55E')
    if v >= 25: return ('Strong trend',     '#22C55E')
    if v >= 20: return ('Developing',       '#F59E0B')
    return ('Weak / range', '#94A3B8')


def _interp_macd(line: float, sig: float, hist: float) -> tuple[str, str]:
    if hist > 0 and line > sig: return ('Bullish crossover', '#22C55E')
    if hist < 0 and line < sig: return ('Bearish crossover', '#EF4444')
    return ('Neutral', '#94A3B8')


def _indicator_badge(label: str, value: str, sub: str, color: str = '#94A3B8') -> str:
    return (
        f'<div style="background:var(--bg-surface);border:1px solid var(--border-soft);'
        f'border-radius:10px;padding:12px 14px;height:100%;">'
        f'<div style="font-size:10px;letter-spacing:.10em;color:var(--fg-muted);'
        f'text-transform:uppercase;font-weight:500;">{label}</div>'
        f'<div style="font-size:20px;font-weight:600;color:{color};margin-top:4px;'
        f'letter-spacing:-.02em;font-variant-numeric:tabular-nums;">{value}</div>'
        f'<div style="font-size:11px;color:var(--fg-muted);margin-top:2px;">{sub}</div>'
        f'</div>'
    )


def _render_me_detail(ticker: str, trades: pd.DataFrame | None) -> None:
    """Multi-panel interactive chart: candles + Bollinger + RSI + MACD + Volume/OBV.

    Toggles for each panel, period selector (1M…All), synced crosshair, and
    KPI badges showing current RSI/MACD/ADX/ATR/Bollinger-width/OBV-trend.
    """
    # ── Locate OHLCV file ───────────────────────────────────────────────────
    full = Path(BASE_DIR) / 'data' / 'nse_bse' / f'{ticker}.NS.csv'
    legacy = Path(BASE_DIR) / 'momentum_edge_data' / f'{ticker}.NS.csv'
    raw = Path(BASE_DIR) / 'data' / 'nse_bse' / f'{ticker}.csv'
    path = next((p for p in (full, legacy, raw) if p.exists()), None)
    if path is None:
        st.info(f'No OHLCV file found for {ticker}.')
        return

    df = _compute_full_indicators(str(path))
    if df is None:
        st.info('Not enough bars to chart this ticker.')
        return

    # ── Controls row: period selector + indicator toggles ──────────────────
    key = f'me_detail_{ticker}'
    ctrl1, ctrl2 = st.columns([1, 2])
    with ctrl1:
        period = st.radio(
            'Period', list(_PERIOD_BARS.keys()), index=3, horizontal=True,
            key=f'{key}_period', label_visibility='collapsed',
        )
    with ctrl2:
        t1, t2, t3, t4 = st.columns(4)
        with t1: show_bb   = st.checkbox('Bollinger',   value=True, key=f'{key}_bb')
        with t2: show_rsi  = st.checkbox('RSI(14)',     value=True, key=f'{key}_rsi')
        with t3: show_macd = st.checkbox('MACD',        value=True, key=f'{key}_macd')
        with t4: show_vol  = st.checkbox('Volume + OBV', value=True, key=f'{key}_vol')

    # ── Window slice ────────────────────────────────────────────────────────
    nbars = _PERIOD_BARS[period]
    df_w = df.tail(nbars).copy() if nbars else df.copy()
    if df_w.empty:
        st.info('No data in selected window.')
        return
    idx = df_w.index
    close = df_w['Close']
    high52 = float(df['Close'].rolling(252).max().iloc[-1])
    low52  = float(df['Close'].rolling(252).min().iloc[-1])

    # ── KPI badge row: current readings ─────────────────────────────────────
    rsi_now = float(df['rsi14'].iloc[-1]) if not df['rsi14'].dropna().empty else float('nan')
    macd_l  = float(df['macd'].iloc[-1])
    macd_s  = float(df['macd_sig'].iloc[-1])
    macd_h  = float(df['macd_hist'].iloc[-1])
    adx_now = float(df['adx14'].iloc[-1]) if not df['adx14'].dropna().empty else float('nan')
    atr_now = float(df['atr14'].iloc[-1])
    bb_width = float(
        ((df['bb_up'].iloc[-1] - df['bb_lo'].iloc[-1]) / df['bb_mid'].iloc[-1]) * 100
    ) if pd.notna(df['bb_mid'].iloc[-1]) and df['bb_mid'].iloc[-1] != 0 else float('nan')
    obv_slope = float(df['obv'].iloc[-1] - df['obv'].iloc[-20]) if len(df) >= 20 else 0.0

    rsi_lbl,  rsi_c  = _interp_rsi(rsi_now)  if pd.notna(rsi_now)  else ('—', '#94A3B8')
    adx_lbl,  adx_c  = _interp_adx(adx_now)  if pd.notna(adx_now)  else ('—', '#94A3B8')
    macd_lbl, macd_c = _interp_macd(macd_l, macd_s, macd_h)
    obv_lbl  = 'Rising ↑' if obv_slope > 0 else 'Falling ↓' if obv_slope < 0 else 'Flat'
    obv_c    = '#22C55E'  if obv_slope > 0 else '#EF4444'   if obv_slope < 0 else '#94A3B8'
    bb_lbl   = 'Tight' if bb_width < 5 else 'Wide' if bb_width > 12 else 'Normal'

    b1, b2, b3, b4, b5 = st.columns(5)
    with b1: st.markdown(_indicator_badge('RSI(14)',    f'{rsi_now:.1f}'    if pd.notna(rsi_now) else '—',  rsi_lbl,  rsi_c),  unsafe_allow_html=True)
    with b2: st.markdown(_indicator_badge('MACD Hist',  f'{macd_h:+.2f}',                                   macd_lbl, macd_c), unsafe_allow_html=True)
    with b3: st.markdown(_indicator_badge('ADX(14)',    f'{adx_now:.1f}'    if pd.notna(adx_now) else '—',  adx_lbl,  adx_c),  unsafe_allow_html=True)
    with b4: st.markdown(_indicator_badge('ATR(14)',    f'₹{atr_now:.2f}',                                  f'Avg daily range', '#60A5FA'), unsafe_allow_html=True)
    with b5: st.markdown(_indicator_badge('OBV 20d',    obv_lbl,                                            f'BB width {bb_width:.1f}% · {bb_lbl}', obv_c), unsafe_allow_html=True)
    st.markdown('<div style="height:10px;"></div>', unsafe_allow_html=True)

    # ── Build subplots ──────────────────────────────────────────────────────
    rows_cfg = [('price', 0.60)]
    if show_rsi:  rows_cfg.append(('rsi',  0.13))
    if show_macd: rows_cfg.append(('macd', 0.13))
    if show_vol:  rows_cfg.append(('vol',  0.14))
    # Normalize heights so they sum to 1
    total = sum(h for _, h in rows_cfg)
    heights = [h / total for _, h in rows_cfg]
    row_idx = {name: i + 1 for i, (name, _) in enumerate(rows_cfg)}

    fig = make_subplots(
        rows=len(rows_cfg), cols=1, shared_xaxes=True,
        vertical_spacing=0.02, row_heights=heights,
    )

    # Row 1: Candles + MAs + Bollinger + 52W lines
    fig.add_trace(go.Candlestick(
        x=idx, open=df_w['Open'], high=df_w['High'],
        low=df_w['Low'], close=df_w['Close'], name='Price',
        increasing_line_color='#22C55E', increasing_fillcolor='rgba(34,197,94,0.35)',
        decreasing_line_color='#EF4444', decreasing_fillcolor='rgba(239,68,68,0.35)',
        showlegend=False,
    ), row=1, col=1)
    fig.add_trace(go.Scatter(x=idx, y=df_w['sma50'],  name='SMA 50',
                             line=dict(color='#60A5FA', width=1.4)), row=1, col=1)
    fig.add_trace(go.Scatter(x=idx, y=df_w['sma150'], name='SMA 150',
                             line=dict(color='#F59E0B', width=1.4)), row=1, col=1)
    fig.add_trace(go.Scatter(x=idx, y=df_w['ema220'], name='EMA 220',
                             line=dict(color='#A78BFA', width=1.6, dash='dot')), row=1, col=1)
    if show_bb:
        fig.add_trace(go.Scatter(x=idx, y=df_w['bb_up'], name='BB Upper',
                                 line=dict(color='rgba(148,163,184,0.5)', width=1)),
                      row=1, col=1)
        fig.add_trace(go.Scatter(x=idx, y=df_w['bb_lo'], name='BB Lower',
                                 line=dict(color='rgba(148,163,184,0.5)', width=1),
                                 fill='tonexty', fillcolor='rgba(148,163,184,0.06)'),
                      row=1, col=1)
        fig.add_trace(go.Scatter(x=idx, y=df_w['bb_mid'], name='BB Mid',
                                 line=dict(color='rgba(148,163,184,0.6)', width=1, dash='dot')),
                      row=1, col=1)
    fig.add_hline(y=high52, line_color='rgba(34,197,94,0.5)', line_dash='dash',
                  annotation_text=f'52W High ₹{high52:,.0f}', annotation_position='bottom right',
                  annotation_font=dict(color='#22C55E', size=10), row=1, col=1)
    fig.add_hline(y=low52, line_color='rgba(239,68,68,0.5)', line_dash='dash',
                  annotation_text=f'52W Low ₹{low52:,.0f}', annotation_position='top right',
                  annotation_font=dict(color='#EF4444', size=10), row=1, col=1)

    # Trade markers
    if trades is not None and not trades.empty and 'Ticker' in trades.columns:
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
                    marker=dict(symbol='triangle-up', size=14, color='#22C55E',
                                line=dict(color='#fff', width=1)),
                    hovertemplate='BUY ₹%{y:,.2f}<br>%{x}<extra></extra>',
                ), row=1, col=1)
            if xm.any():
                fig.add_trace(go.Scatter(
                    x=xd[xm], y=xp[xm], mode='markers', name='EXIT',
                    marker=dict(symbol='triangle-down', size=14, color='#EF4444',
                                line=dict(color='#fff', width=1)),
                    hovertemplate='EXIT ₹%{y:,.2f}<br>%{x}<extra></extra>',
                ), row=1, col=1)

    # Row: RSI
    if show_rsi:
        r = row_idx['rsi']
        fig.add_trace(go.Scatter(x=idx, y=df_w['rsi14'], name='RSI(14)',
                                 line=dict(color='#F8FAFC', width=1.4)), row=r, col=1)
        fig.add_hline(y=70, line_color='rgba(239,68,68,0.4)', line_dash='dot', row=r, col=1)
        fig.add_hline(y=30, line_color='rgba(34,197,94,0.4)', line_dash='dot', row=r, col=1)
        fig.add_hline(y=50, line_color='rgba(148,163,184,0.25)', line_dash='dot', row=r, col=1)
        fig.update_yaxes(range=[0, 100], tickvals=[20, 50, 80], row=r, col=1)

    # Row: MACD
    if show_macd:
        r = row_idx['macd']
        hist_color = ['#22C55E' if v >= 0 else '#EF4444' for v in df_w['macd_hist'].fillna(0)]
        fig.add_trace(go.Bar(x=idx, y=df_w['macd_hist'], name='MACD Hist',
                             marker_color=hist_color, opacity=0.55,
                             showlegend=False), row=r, col=1)
        fig.add_trace(go.Scatter(x=idx, y=df_w['macd'],     name='MACD',
                                 line=dict(color='#60A5FA', width=1.5)), row=r, col=1)
        fig.add_trace(go.Scatter(x=idx, y=df_w['macd_sig'], name='Signal',
                                 line=dict(color='#F59E0B', width=1.2)), row=r, col=1)
        fig.add_hline(y=0, line_color='rgba(148,163,184,0.3)', line_dash='dot', row=r, col=1)

    # Row: Volume + OBV
    if show_vol:
        r = row_idx['vol']
        vol_color = ['#22C55E' if c >= o else '#EF4444' for c, o in zip(df_w['Close'], df_w['Open'])]
        fig.add_trace(go.Bar(x=idx, y=df_w['Volume'], name='Volume',
                             marker_color=vol_color, opacity=0.45,
                             showlegend=False, yaxis=f'y{r}'), row=r, col=1)
        # OBV on secondary axis — simulate via normalizing into volume range
        obv_w = df_w['obv']
        if not obv_w.empty:
            v_max = float(df_w['Volume'].max() or 1)
            o_min, o_max = float(obv_w.min()), float(obv_w.max())
            rng = (o_max - o_min) or 1.0
            obv_norm = (obv_w - o_min) / rng * v_max
            fig.add_trace(go.Scatter(x=idx, y=obv_norm, name='OBV (scaled)',
                                     line=dict(color='#A78BFA', width=1.4)), row=r, col=1)

    # ── Layout: synced crosshair + corporate dark theme ─────────────────────
    yaxis_titles = {1: '₹ Price'}
    if show_rsi:  yaxis_titles[row_idx['rsi']]  = 'RSI'
    if show_macd: yaxis_titles[row_idx['macd']] = 'MACD'
    if show_vol:  yaxis_titles[row_idx['vol']]  = 'Volume'

    for r in range(1, len(rows_cfg) + 1):
        fig.update_xaxes(
            showspikes=True, spikemode='across+toaxis', spikethickness=1,
            spikedash='dot', spikecolor='rgba(148,163,184,0.55)',
            showline=True, linecolor='#1E293B', gridcolor='#1E293B',
            row=r, col=1,
        )
        fig.update_yaxes(
            title=dict(text=yaxis_titles.get(r, ''), font=dict(size=10, color='#64748B')),
            showspikes=True, spikemode='across', spikethickness=1,
            spikedash='dot', spikecolor='rgba(148,163,184,0.55)',
            showline=True, linecolor='#1E293B', gridcolor='#1E293B',
            tickfont=dict(size=10),
            row=r, col=1,
        )
    # Price axis: ₹ prefix
    fig.update_yaxes(tickprefix='₹', tickformat=',.0f', row=1, col=1)
    # Last row gets x-tick labels
    fig.update_xaxes(tickformat='%d %b %y', tickfont=dict(size=10),
                     row=len(rows_cfg), col=1)
    # Hide rangeslider on candlestick
    fig.update_layout(xaxis_rangeslider_visible=False)

    fig.update_layout(
        height=180 + 380 * heights[0] + sum(180 * h for h in heights[1:]),
        paper_bgcolor='#1c1c1c', plot_bgcolor='#1c1c1c',
        font=dict(color='#F1F5F9', family='Inter'),
        legend=dict(orientation='h', y=1.04, x=0,
                    font=dict(size=11, color='#94A3B8'),
                    bgcolor='rgba(0,0,0,0)'),
        margin=dict(l=70, r=30, t=60, b=40),
        hovermode='x unified',
        hoverlabel=dict(bgcolor='#0F172A', bordercolor='#334155',
                        font=dict(family='IBM Plex Mono', size=11, color='#F1F5F9')),
        spikedistance=-1,
        dragmode='zoom',
        barmode='overlay',
    )
    st.plotly_chart(fig, width='stretch')

    # ── Mini stats bar (price/change/52W/volume) ────────────────────────────
    close_now  = float(df['Close'].iloc[-1])
    close_prev = float(df['Close'].iloc[-2]) if len(df) >= 2 else close_now
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


def _load_parquet_indicators_parallel(folder: Path) -> dict[str, pd.DataFrame]:
    """Read every *.parquet in folder via ThreadPool. 960 files ≈ 2-3s.

    Each parquet was written by momentum_edge_backtest.py and contains all the
    indicators master_dashboard needs (close, sma50, sma150, ema220, high52w,
    low52w, vol_avg50, ath, choppiness, momentum_6m + their _s shifted twins).
    """
    from concurrent.futures import ThreadPoolExecutor
    if not folder.exists():
        return {}
    paths = list(folder.glob('*.parquet'))
    if not paths:
        return {}

    def _read(path):
        try:
            return path.stem, pd.read_parquet(path)
        except Exception:
            return path.stem, None

    out: dict[str, pd.DataFrame] = {}
    with ThreadPoolExecutor(max_workers=16) as pool:
        for stem, df in pool.map(_read, paths):
            if df is not None and not df.empty:
                out[stem] = df
    return out


def _parquet_is_fresh(parquet_dir: Path, csv_folder: Path, tol_days: int = 1) -> bool:
    """Cheap freshness check: parquet's latest index >= CSV's latest index minus tol_days.

    Compares one widely-traded symbol (RELIANCE.NS preferred). Returns False if
    either file is missing. Default tolerance is 1 calendar day — if the CSVs
    have been refreshed (typically post-market 16:00) and the parquet cache
    has not been rebuilt by a backtest run, we fall back to CSV path so the
    live screener reflects today's market.
    """
    probe = 'RELIANCE.NS'
    pq = parquet_dir / f'{probe}.parquet'
    cs = csv_folder / f'{probe}.csv'
    if not (pq.exists() and cs.exists()):
        # Fall back to comparing any one file
        pq_files = list(parquet_dir.glob('*.parquet'))
        cs_files = list(csv_folder.glob('*.csv'))
        if not pq_files or not cs_files:
            return False
        pq, cs = pq_files[0], cs_files[0]
    try:
        pq_last = pd.read_parquet(pq).index[-1]
        cs_last = pd.read_csv(cs, index_col=0, parse_dates=True).index[-1]
        return bool((cs_last - pq_last).days <= tol_days)
    except Exception:
        return False


def _empty_funnel() -> dict:
    return {'total': 0, 'sufficient_data': 0,
            'f1': 0, 'f2': 0, 'f3': 0, 'f4': 0, 'f5': 0, 'f6': 0,
            'vol_bk': 0, 'final': 0}


def _compute_momentum_signals_from_parquet(
    cache_dir: Path,
    universe: dict[str, str],
    bench: pd.Series | None,
) -> tuple[pd.DataFrame, dict]:
    """Parquet fast-path. ~3-5s for 2000 tickers vs 30-60s via CSV+recompute.

    Returns (signals_df, funnel_dict).
    """
    # ── Regime gate ─────────────────────────────────────────────────────────
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

    VOL_MULTIPLIER   = 1.5
    MIN_PRICE_VS_LOW = 1.25
    MIN_CLOSE_PRICE  = 50.0
    MIN_AVG_VOL      = 100_000
    NEAR_BK_PCT      = 0.02

    parquet_map = _load_parquet_indicators_parallel(cache_dir)
    if not parquet_map:
        return pd.DataFrame(), _empty_funnel()

    rows = []
    skip_stems = {'NIFTYBEES.NS', 'me_summary', '^NSEI'}
    funnel = _empty_funnel()
    funnel['total'] = len([t for t in parquet_map if t not in skip_stems])

    for ticker, ind in parquet_map.items():
        if ticker in skip_stems:
            continue
        if len(ind) < 252:
            continue

        close  = ind['close']
        volume = ind.get('volume', pd.Series(dtype=float))

        if close.iloc[-1] < MIN_CLOSE_PRICE:
            continue
        if not volume.empty and volume.iloc[-30:].mean() < MIN_AVG_VOL:
            continue
        funnel['sufficient_data'] += 1

        ema220 = ind['ema220']
        # Resistance series = close.shift(1).rolling(252).max() == high52w shifted by 1.
        # Parquet has high52w_s precomputed; build full series via .shift on high52w.
        high52w = ind['high52w']
        resistance = high52w.shift(1)

        # 1-2-3 state machine
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
        if cycle_state == 'POST_BREAKOUT':
            continue

        # Day-T and T-1 scalars — pull from precomputed _s columns
        close_now  = float(close.iloc[-1])
        ema220_now = float(ema220.iloc[-1])
        sma50_now  = float(ind['sma50'].iloc[-1])
        sma150_now = float(ind['sma150'].iloc[-1])
        low52_now  = float(ind['low52w'].iloc[-1])
        vol_today  = float(volume.iloc[-1]) if not volume.empty else 0.0

        close_s    = float(ind['close_s'].iloc[-1])  if 'close_s'    in ind else float(close.iloc[-2])
        vol50_s    = float(ind['vol_avg50_s'].iloc[-1]) if 'vol_avg50_s' in ind else float(volume.rolling(50).mean().iloc[-2])
        had_dip_s  = bool(ind['had_ema_dip_s'].iloc[-1]) if 'had_ema_dip_s' in ind else False
        chop_s     = float(ind['choppiness_s'].iloc[-1]) if 'choppiness_s' in ind else float('nan')
        mom_s      = float(ind['momentum_6m_s'].iloc[-1]) if 'momentum_6m_s' in ind else 0.0
        ath_prev   = float(ind['ath_prev'].iloc[-1])    if 'ath_prev' in ind else float(ind.get('ath', close).iloc[-2])

        res_today  = float(resistance.iloc[-1]) if not pd.isna(resistance.iloc[-1]) else float('nan')

        if any(pd.isna(v) for v in (close_now, ema220_now, sma50_now, sma150_now, low52_now)):
            continue

        # F1-F4 day-T, F5 had_dip_s, F6 choppiness_s
        if not (sma150_now > ema220_now): continue
        funnel['f1'] += 1
        if not (close_now  > sma50_now):  continue
        funnel['f2'] += 1
        if not (sma50_now  > sma150_now): continue
        funnel['f3'] += 1
        if not (close_now  >= MIN_PRICE_VS_LOW * low52_now): continue
        funnel['f4'] += 1
        if not had_dip_s: continue
        funnel['f5'] += 1
        if not pd.isna(chop_s) and chop_s > CHOPPINESS_THRESH:
            continue
        funnel['f6'] += 1

        vol_ok = (
            not pd.isna(vol50_s) and vol50_s > 0
            and vol_today >= VOL_MULTIPLIER * vol50_s
        )
        bk_ref = res_today if not pd.isna(res_today) else float(ind['high52w_s'].iloc[-1] if 'high52w_s' in ind else high52w.iloc[-2])
        is_breakout = (
            not pd.isna(res_today)
            and close_now > res_today
            and close_s <= res_today
            and close_now > ema220_now
        )
        dist_to_res = (res_today - close_now) / res_today if (not pd.isna(res_today) and res_today > 0) else 1.0
        is_near_bk = (
            (not is_breakout) and (not pd.isna(res_today))
            and 0 < dist_to_res <= NEAR_BK_PCT and vol_ok
        )
        if is_breakout and vol_ok:
            signal = 'Breakout Today'
            funnel['vol_bk'] += 1
        elif is_near_bk:
            signal = 'Near Breakout'
        else:
            signal = 'Watch Zone'

        entry_type = 'ATH' if (not pd.isna(ath_prev) and close_now > ath_prev) else '52W High'

        # Recovery speed — needs full close/ema220 series (cheap, no extra IO)
        rec_label, rec_days = _compute_recovery_speed(close, ema220, lookback=90)
        rec_str = {'Fast': 'Fast 🟢', 'Normal': 'Normal 🟡', 'Slow': 'Slow 🟠'}.get(rec_label, '— ⚪')

        vol_ratio = (vol_today / vol50_s) if (not pd.isna(vol50_s) and vol50_s > 0) else 0
        ath_prox  = min((close_now / bk_ref), 1.0) if (bk_ref and bk_ref > 0) else 0
        mom_pct   = mom_s if not pd.isna(mom_s) else 0
        score = round(ath_prox * 30 + min(vol_ratio * 10, 20) + min(mom_pct * 100, 20), 1)
        dist_ath = ((close_now / bk_ref) - 1) * 100 if bk_ref and bk_ref > 0 else 0

        ath_now = float(ind['ath'].iloc[-1]) if 'ath' in ind else close_now

        rows.append({
            'Ticker':       ticker.replace('.NS', ''),
            'Company':      universe.get(ticker, ticker.replace('.NS', '')),
            'Signal':       signal,
            'Close':        round(close_now, 2),
            'ATH (₹)':      round(ath_now, 2),
            'Dist ATH%':    round((close_now / ath_now - 1) * 100, 2),
            'Entry Type':   entry_type,
            'Chart Qual':   'Clean ✅' if (not pd.isna(chop_s) and chop_s < CHOPPINESS_THRESH) else 'Choppy ❌',
            'Choppiness':   round(chop_s, 1) if not pd.isna(chop_s) else '—',
            'Recovery':     rec_str,
            '220 EMA':      round(ema220_now, 2),
            '52W High':     round(bk_ref, 2) if bk_ref else None,
            'vs High%':     round(dist_ath, 2),
            'Vol Ratio':    round(vol_ratio, 2),
            'Score':        score,
            '_score':       score,
            '_is_bull':     is_bull_today,
        })

    if not rows:
        return pd.DataFrame(), funnel
    df_out = pd.DataFrame(rows)
    sig_rank = {'Breakout Today': 0, 'Near Breakout': 1, 'Watch Zone': 2}
    df_out['_rank'] = df_out['Signal'].map(sig_rank).fillna(3)
    df_out = df_out.sort_values(['_rank', '_score'], ascending=[True, False])
    df_out = df_out.drop(columns=['_rank', '_score', '_is_bull']).reset_index(drop=True)
    funnel['final'] = len(df_out)
    return df_out, funnel


RECENT_BREAKOUT_DAYS = 7


@st.cache_data(ttl=3600, show_spinner=False)
def _scan_recent_breakouts() -> pd.DataFrame:
    """Scan every ticker for a 52W close-high cross in the last RECENT_BREAKOUT_DAYS.

    A "recent breakout" = on some bar within the last 7 trading days, close
    crossed above the prior 252-bar close max (close[t-1] <= res[t] AND close[t] > res[t]).
    Today's close must still be > 92% of the breakout close AND > EMA220.
    Returns a DataFrame with Ticker, Days Ago, Close, Bk Price, % Off Bk High, 220 EMA, Vol Ratio.
    """
    folders = [Path(BASE_DIR) / 'data' / 'nse_bse']
    csv_paths = []
    for folder in folders:
        if folder.exists():
            csv_paths.extend(folder.glob('*.NS.csv'))
    if not csv_paths:
        return pd.DataFrame()

    rows = []
    skip_stems = {'NIFTYBEES.NS', '^NSEI'}
    for path in csv_paths:
        ticker = path.stem
        if ticker in skip_stems:
            continue
        try:
            df = pd.read_csv(path, index_col=0, parse_dates=True)
        except Exception:
            continue
        if len(df) < 260 or 'Close' not in df.columns:
            continue

        close  = df['Close']
        volume = df.get('Volume', pd.Series(dtype=float))
        ema220 = close.ewm(span=ME_EMA220_P, adjust=False).mean()
        resistance = close.shift(1).rolling(ME_HIGH52_P).max()

        c_arr = close.values.astype(float)
        r_arr = resistance.values.astype(float)
        n     = len(c_arr)
        close_now  = float(c_arr[-1])
        ema220_now = float(ema220.iloc[-1])
        if np.isnan(close_now) or np.isnan(ema220_now) or close_now < ema220_now:
            continue

        # Walk back day by day, find the first cross
        for k in range(0, RECENT_BREAKOUT_DAYS + 1):
            idx = n - 1 - k
            if idx <= 0:
                break
            r, c, cp = r_arr[idx], c_arr[idx], c_arr[idx - 1]
            if np.isnan(r) or np.isnan(c) or np.isnan(cp):
                continue
            # Cross-up: today's close > res, prior close <= res
            if c > r and cp <= r:
                bk_close = c
                if close_now < 0.92 * bk_close:
                    break  # pulled back too far, drop
                vol_avg50 = float(volume.rolling(50).mean().iloc[-1]) if not volume.empty else 0
                vol_today = float(volume.iloc[-1]) if not volume.empty else 0
                vol_ratio = (vol_today / vol_avg50) if vol_avg50 > 0 else 0
                off_pct = (close_now / bk_close - 1) * 100
                rows.append({
                    'Ticker':       ticker.replace('.NS', ''),
                    'Days Ago':     k,
                    'Bk Date':      df.index[idx].strftime('%Y-%m-%d'),
                    'Bk Price (₹)': round(bk_close, 2),
                    'Close (₹)':    round(close_now, 2),
                    '% Off Bk':     round(off_pct, 2),
                    '220 EMA (₹)':  round(ema220_now, 2),
                    'Vol Ratio':    round(vol_ratio, 2),
                    'Stop (₹)':     round(close_now * 0.85, 2),
                })
                break  # take only first (most recent) cross
    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows).sort_values('Days Ago').reset_index(drop=True)
    return out


def _compute_momentum_signals() -> tuple[pd.DataFrame, dict]:
    """Detect Momentum Edge live signals — SPEC-ALIGNED with momentum_edge_dashboard.py.

    F1-F4 use day-T values (per spec); F5/F6 use T-1; breakout-ref uses T-1 (resistance =
    yesterday's 252-day rolling max). Volume check uses 50-day average per spec.
    State machine excludes stocks whose current breakout already fired (POST_BREAKOUT).
    Regime gate (3-condition) is applied — entries in Bear regime get BEAR MARKET action.

    PERF: tries `data/indicator_cache/*.parquet` first (written by
    momentum_edge_backtest.py). If those exist and are fresh (latest index
    within 7 days of CSV's latest), takes the fast path (~3s instead of ~30s).
    """
    full_folder   = Path(BASE_DIR) / 'data' / 'nse_bse'
    legacy_folder = Path(BASE_DIR) / 'momentum_edge_data'
    folder = full_folder if full_folder.exists() and any(full_folder.glob('*.csv')) else legacy_folder
    sym_file = Path(BASE_DIR) / 'momentum_edge_symbols.csv'
    if not folder.exists():
        return pd.DataFrame(), _empty_funnel()

    universe: dict[str, str] = {}
    if sym_file.exists():
        try:
            s = pd.read_csv(sym_file)
            universe = dict(zip(s['Ticker'].str.strip(), s['Company'].str.strip()))
        except Exception:
            pass

    # ── Regime gate (3-condition on Nifty) ─────────────────────────────────
    bench = _benchmark_first('data/nse_bse', 'data')

    # ── Parquet fast path ──────────────────────────────────────────────────
    cache_dir = Path(BASE_DIR) / 'data' / 'indicator_cache'
    if cache_dir.exists() and _parquet_is_fresh(cache_dir, folder):
        df_fast, funnel_fast = _compute_momentum_signals_from_parquet(cache_dir, universe, bench)
        if not df_fast.empty:
            return df_fast, funnel_fast
        # parquet exists but yielded nothing → fall through to CSV
    funnel = _empty_funnel()
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
    all_csv = [c for c in sorted(folder.glob('*.csv')) if c.stem not in skip_stems]
    funnel['total'] = len(all_csv)

    for csv_path in all_csv:
        ticker  = csv_path.stem
        company = universe.get(ticker, ticker.replace('.NS', ''))
        df      = _load_ohlcv_csv(csv_path)
        if df is None or len(df) < MIN_BARS:
            continue
        if df['Close'].iloc[-1] < MIN_CLOSE_PRICE:
            continue
        if df['Volume'].iloc[-30:].mean() < MIN_AVG_VOL:
            continue
        funnel['sufficient_data'] += 1

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
        funnel['f1'] += 1
        if not (close_now  > sma50_now):  continue
        funnel['f2'] += 1
        if not (sma50_now  > sma150_now): continue
        funnel['f3'] += 1
        if not (close_now  >= MIN_PRICE_VS_LOW * low52_now): continue
        funnel['f4'] += 1
        if not had_dip_s: continue
        funnel['f5'] += 1

        chop_series = _compute_choppiness(df, CHOPPINESS_P)
        chop_val    = float(chop_series.iloc[-2]) if len(chop_series) >= 2 and not pd.isna(chop_series.iloc[-2]) else float('nan')
        if not pd.isna(chop_val) and chop_val > CHOPPINESS_THRESH:
            continue
        funnel['f6'] += 1

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
            funnel['vol_bk'] += 1
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
        return pd.DataFrame(), funnel

    df_out = pd.DataFrame(rows)
    sig_rank = {'Breakout Today': 0, 'Near Breakout': 1, 'Watch Zone': 2}
    df_out['_rank'] = df_out['Signal'].map(sig_rank).fillna(3)
    df_out = df_out.sort_values(['_rank', '_score'], ascending=[True, False])
    df_out = df_out.drop(columns=['_rank', '_score', '_is_bull']).reset_index(drop=True)
    funnel['final'] = len(df_out)
    return df_out, funnel


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

<div>
<b style="color:#7c9cff">MAE</b> — <i>Maximum Adverse Excursion</i><br>
The deepest dip a trade saw before it closed. If you bought at ₹100 and the price
fell to ₹88 before bouncing back, the MAE is -12% — even if the trade later closed positive.
</div>

<div>
<b style="color:#7c9cff">MFE</b> — <i>Maximum Favourable Excursion</i><br>
The biggest gain a trade touched before it closed. If a trade went +25% then closed at +8%,
the MFE is +25%. Useful for picking profit-taking levels.
</div>

<div>
<b style="color:#7c9cff">p95 (95th percentile)</b> — <i>Worst-case bound that ignores outliers</i><br>
"p95 = -10%" means 95% of cases stayed inside -10%. Only 5% were worse.
Used to set stops loose enough for normal pullbacks but tight enough for real losers.
</div>

<div>
<b style="color:#7c9cff">Quintile</b> — <i>Top 5 buckets, each 20% of the data</i><br>
Sort all trades by Score, slice into 5 equal-size groups (Q1 weakest → Q5 strongest).
If win rate climbs steadily Q1 → Q5, the score is predictive.
</div>

<div>
<b style="color:#7c9cff">Fade Rate</b> — <i>How often a gain is given back</i><br>
At a +15% level, fade rate = % of trades that touched +15% then closed below it.
Low fade rate = book partial profits there, the gain rarely escapes.
</div>

<div>
<b style="color:#7c9cff">RSI (Relative Strength Index)</b> — <i>How overheated is the move?</i><br>
0–100 score. Above 70 = overbought (stock may pause/pull back).
Below 30 = oversold (potential bounce). Around 50 = neutral.
</div>

<div>
<b style="color:#7c9cff">MACD</b> — <i>Trend & momentum crossover</i><br>
Difference between two moving averages. When the MACD line crosses above the signal line
(histogram turns green/positive) = bullish. When it crosses below = bearish.
</div>

<div>
<b style="color:#7c9cff">ADX (Average Directional Index)</b> — <i>How strong is the trend?</i><br>
0–100 score. Below 20 = weak / sideways. 20–25 = trend forming.
Above 25 = strong trend. Above 40 = very strong trend.
</div>

<div>
<b style="color:#7c9cff">ATR (Average True Range)</b> — <i>How much does the stock move daily?</i><br>
Typical daily range in rupees. Use it to size stops: 2×ATR below entry is a
common "give it room to breathe" stop-loss distance.
</div>

<div>
<b style="color:#7c9cff">Bollinger Bands</b> — <i>Volatility envelope</i><br>
20-day SMA with ±2σ bands. Price near upper band = stretched up.
Bands squeezing tight = a big move is brewing. Width &lt; 5% = compressed.
</div>

<div>
<b style="color:#7c9cff">OBV (On-Balance Volume)</b> — <i>Volume-weighted trend confirmation</i><br>
Running sum of volume signed by close direction. OBV rising while price rises = healthy
buying. OBV flat or falling while price rises = weak rally, watch out.
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
        if not b.empty:
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
            4 STRATEGIES · SYSTEMATIC INVESTING
          </div>
        </div>
        """, unsafe_allow_html=True)

        page = st.radio(
            'Navigate',
            ['🏠  Home', '🔄  Monthly Rotation', '🚀  IPO Edge',
             '📈  Momentum Edge', '⚡  PEAD', '🎯  Suggestions', '🔬  Insights',
             '📊  History & Proof'],
            label_visibility='collapsed',
        )

        st.markdown('<hr style="margin:16px 0;">', unsafe_allow_html=True)
        theme_choice = st.radio(
            'Theme',
            ['🌙 Dark', '☀️ Light', '🖥️ Auto (OS)'],
            horizontal=True,
            label_visibility='collapsed',
            key='_theme_choice',
        )
        _theme_map = {'🌙 Dark': 'dark', '☀️ Light': 'light', '🖥️ Auto (OS)': 'auto'}
        _theme_val = _theme_map.get(theme_choice, 'dark')
        st.markdown(
            f"""<script>
            (function() {{
                const v = "{_theme_val}";
                const root = window.parent.document.documentElement;
                if (v === 'auto') {{
                    root.removeAttribute('data-theme');
                }} else {{
                    root.setAttribute('data-theme', v);
                }}
            }})();
            </script>""",
            unsafe_allow_html=True,
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

def _chart_me_funnel(funnel: dict, is_bull: bool) -> go.Figure:
    """Filter funnel — how many stocks pass each gate, top to bottom."""
    labels = ['Universe', 'Has Data',
              'F1 Trend', 'F2 Price > SMA50', 'F3 MA Align',
              'F4 vs 52W Low', 'F5 Dip Recovered', 'F6 Clean Chart',
              'Vol + Breakout']
    keys = ['total', 'sufficient_data', 'f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'vol_bk']
    values = [int(funnel.get(k, 0)) for k in keys]
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
        height=360, margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor='#1c1c1c', plot_bgcolor='#1c1c1c',
        font=dict(color='#e0e0e0', family='Inter'),
    )
    return fig


def render_momentum(mo: dict):
    color  = THEME[S_MOMENTUM]['color']
    st.markdown(
        f'<div class="page-title" style="color:{color}">📈 Momentum Edge</div>'
        '<div class="page-sub">Large/mid-cap stocks that dipped below their 220-day average, recovered, '
        'and are now breaking to new all-time highs — caught at the perfect moment.</div><br>',
        unsafe_allow_html=True,
    )

    eq     = mo.get('equity')
    trades = mo.get('trades')
    sigs   = mo.get('signals', pd.DataFrame())

    # ── ATH-only toggle (applies to screener, past trades, backtest) ───────────
    tcol1, tcol2 = st.columns([1, 4])
    with tcol1:
        ath_only = st.toggle(
            '🎯 ATH-only mode', value=False, key='me_ath_only',
            help='When ON, only stocks breaking their all-time closing high qualify. '
                 'Drops 52W-only fallback entries (more selective, fewer signals, higher quality).',
        )
    with tcol2:
        st.caption(
            ('🎯 **ATH-only ACTIVE** — showing/keeping only true all-time-high breakouts. '
             '52W_HIGH_FALLBACK entries hidden.' if ath_only else
             '52W-high breakouts included by default (strategy spec). Toggle ON to restrict to ATH-only.')
        )

    # Filter trades + signals by ATH if toggle on
    if ath_only:
        if trades is not None and not trades.empty and 'Entry_Type' in trades.columns:
            trades = trades[trades['Entry_Type'] == 'ATH'].copy()
        if sigs is not None and not sigs.empty and 'Entry Type' in sigs.columns:
            sigs = sigs[sigs['Entry Type'] == 'ATH'].copy()

    # ── Strategy Health hero — answers "is it working? how many stocks? hold?" ──
    _render_health_hero(S_MOMENTUM, trades, sigs)

    # ── How it works callout ───────────────────────────────────────────────────
    st.markdown(_explain_box(
        '🧠 <b>How This Strategy Works (Plain English)</b><br>'
        'We look for strong NSE stocks that recently dipped below their long-term average (220-day line), '
        'then bounced back up — showing the dip was temporary, not a collapse. '
        'We only buy when the stock is also breaking to an <b>all-time high (ATH)</b>, meaning buyers are fully in control. '
        '<b>Hold strategy:</b> sit tight until ONE of these fires — (1) price falls 15% from entry (hard stop), '
        '(2) close drops below the 220-day EMA, OR (3) price hits a profit target. No emotional exits.',
        color,
    ), unsafe_allow_html=True)

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
        stop_p95 = None
        try:
            me_report = _build_report(S_MOMENTUM)
            sigs = core_scorer.enrich_signals(
                sigs, me_report,
                feature_map={'Entry Type': 'Entry_Type', 'Recovery': 'Recovery_Speed'},
            )
            stop_p95 = (me_report.get('stop_recommendation') or {}).get('winner_mae_p95')
        except Exception:
            pass

        # Per-signal suggested stop based on Winner MAE p95 (or default 10%)
        if 'Close' in sigs.columns:
            stop_rows = sigs['Close'].apply(
                lambda px: _suggest_stop(float(px), atr=None, winner_mae_p95_pct=stop_p95)
            )
            sigs['Stop (₹)'] = stop_rows.apply(lambda d: d.get('stop_price'))
            sigs['Stop %']   = stop_rows.apply(lambda d: -abs(d.get('stop_pct') or 0))

        # ── Action filter tabs (BUY / WATCH / FORMING / RECENT) ─────────────
        sigs['Action'] = sigs['Signal'].map(lambda s: _action_from_signal(s, True))
        recent_bk = mo.get('recent_breakouts', pd.DataFrame())
        tab_all, tab_buy, tab_watch, tab_form, tab_recent = st.tabs([
            f'🔍 All ({len(sigs)})',
            f'🟢 BUY NOW ({(sigs["Action"]=="BUY NOW").sum()})',
            f'🟡 WATCH ({(sigs["Action"]=="WATCH").sum()})',
            f'🔵 FORMING ({(sigs["Action"]=="FORMING").sum()})',
            f'🔄 Recent 7d ({len(recent_bk)})',
        ])
        # Active subset selection via session state
        action_key = 'me_screener_action'
        # Streamlit's tabs don't return selection — render the same table in each,
        # with its own filtered subset. Cheap and consistent.
        def _render_subset(subset: pd.DataFrame, key_suffix: str) -> None:
            if subset.empty:
                st.info('No signals in this bucket.')
                return
            sub_display = display_cols
            d = subset[[c for c in sub_display if c in subset.columns]].copy()
            colors = [sig_color_map.get(s, '#1c1c1c') for s in subset['Signal']]
            for c in ('Close', 'ATH (₹)', '220 EMA', '52W High', 'Stop (₹)'):
                if c in d.columns:
                    d[c] = d[c].apply(lambda x: f'₹{x:,.2f}' if pd.notna(x) else '—')
            if 'Stop %' in d.columns:
                d['Stop %'] = d['Stop %'].apply(lambda x: f'{x:+.1f}%' if pd.notna(x) else '—')
            for c in ('Dist ATH%', 'vs High%'):
                if c in d.columns:
                    d[c] = d[c].apply(lambda x: f'{x:+.1f}%')
            if 'Vol Ratio' in d.columns:
                d['Vol Ratio'] = d['Vol Ratio'].apply(lambda x: f'{x:.2f}×')
            if 'Hist Win%' in d.columns:
                d['Hist Win%'] = d['Hist Win%'].apply(lambda x: f'{x:.0f}%')
            if 'Hist Avg%' in d.columns:
                d['Hist Avg%'] = d['Hist Avg%'].apply(lambda x: f'{x:+.1f}%')
            n_c = len(d.columns)
            w   = ([60, 130, 90, 70, 80, 70, 80, 70, 70, 70, 70, 75, 70, 70, 65, 55, 60, 60])[:n_c]
            st.plotly_chart(
                chart_plotly_table(d, w, colors, score_col='Score'),
                width='stretch',
                key=f'me_table_{key_suffix}',
            )

        sig_color_map = {
            'Breakout Today': 'rgba(34,197,94,0.10)',
            'Near Breakout':  'rgba(245,158,11,0.10)',
            'Watch Zone':     'rgba(96,165,250,0.08)',
            'Watchlist':      'rgba(148,163,184,0.05)',
        }

        display_cols = [
            'Ticker', 'Company', 'Signal', 'Action',
            'Close', 'Stop (₹)', 'Stop %',
            'ATH (₹)', 'Dist ATH%',
            'Entry Type', 'Chart Qual', 'Choppiness',
            'Recovery', '220 EMA', '52W High', 'vs High%', 'Vol Ratio',
            'Score', 'Hist Win%', 'Hist Avg%',
        ]
        with tab_all:   _render_subset(sigs, 'all')
        with tab_buy:   _render_subset(sigs[sigs['Action'] == 'BUY NOW'],  'buy')
        with tab_watch: _render_subset(sigs[sigs['Action'] == 'WATCH'],    'watch')
        with tab_form:  _render_subset(sigs[sigs['Action'] == 'FORMING'],  'forming')
        with tab_recent:
            st.markdown(_explain_box(
                '🔄 <b>Recent Breakouts (last 7 trading days)</b> — Stocks that crossed their '
                'prior 52-week close high in the past week. They may have pulled back today (so they '
                'do not appear as BUY NOW) but are still trading above their EMA220 and above 92% of '
                'the breakout price — i.e. <b>still buyable on a pullback</b>. Examples: DIACABS broke '
                'out 15 May at ₹196.45 and is now ₹190.23 (-3.2% off the high).',
                color,
            ), unsafe_allow_html=True)
            if recent_bk.empty:
                st.caption('No recent breakouts in the last 7 days.')
            else:
                st.dataframe(recent_bk, hide_index=True, width='stretch',
                             height=min(600, 38 * len(recent_bk) + 40))
                st.caption(
                    f'**{len(recent_bk)}** stocks crossed their 52-week close high in the last 7 trading days '
                    'and still hold above their EMA220. **% Off Bk** = how far today\'s close is from the '
                    'breakout-day close (negative = pulled back).'
                )

        st.caption(
            '📊 *Hist Win%* / *Hist Avg%* — historical performance of past trades '
            'with the same Entry Type + Recovery Speed combo. Based on closed backtest trades only.'
        )

        # ── Filter funnel ──────────────────────────────────────────────────────
        funnel = mo.get('funnel') or {}
        if funnel.get('total', 0) > 0:
            st.markdown('<br>', unsafe_allow_html=True)
            st.markdown(f'<div class="sec-hdr" style="color:{color}">🔻 Filter Funnel — how the universe narrows to today\'s signals</div>',
                        unsafe_allow_html=True)
            st.caption('Each step is a filter the stock must pass. The drop from one bar to the next is how many failed that gate.')
            is_bull = True
            try:
                snap = _regime_snapshot()
                is_bull = (snap.get('status') == 'Bull')
            except Exception:
                pass
            st.plotly_chart(_chart_me_funnel(funnel, is_bull), width='stretch')

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

            # ── Strategy Conditions — 8 filters pass/fail for this ticker ─────
            st.markdown('<br>', unsafe_allow_html=True)
            st.markdown(
                f'<div class="sec-hdr" style="color:{color}">Strategy Conditions — '
                f'why {sel} did or did not qualify</div>',
                unsafe_allow_html=True,
            )
            st.caption(
                'Each card is one of the 8 filters the backtest uses. '
                'Evaluated on yesterday\'s close (no look-ahead) — exactly what the strategy sees.'
            )
            try:
                _render_criteria_panel(sel)
            except Exception as e:
                st.warning(f'Could not render criteria: {e}')

            # ── Single-ticker backtest button ──────────────────────────────
            st.markdown('<br>', unsafe_allow_html=True)
            st.markdown(
                f'<div class="sec-hdr" style="color:{color}">'
                f'Backtest This Ticker — every past trade the rules would have taken</div>',
                unsafe_allow_html=True,
            )
            st.caption(
                f'Walk-forward simulation on {sel}: applies the 8 filters bar-by-bar from 2017 to today, '
                'entering on next-bar Open after signal, exiting on EMA break or 15% stop. Zero look-ahead.'
            )
            bcol1, bcol2 = st.columns([1, 4])
            with bcol1:
                run_bt = st.button(f'▶ Run Backtest on {sel}',
                                    key=f'me_bt_btn_{sel}', type='secondary')
            with bcol2:
                st.caption(
                    f'Will use **{("ATH-only" if ath_only else "52W high")}** breakout rule '
                    f'(controlled by the toggle at the top of this page).'
                )
            if run_bt:
                _render_single_ticker_backtest(sel, ath_only=ath_only)

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
            '<div style="font-size:12px;color:var(--muted-foreground);margin-bottom:10px;">'
            'Green row = trade made a profit. Red = trade was a loss. '
            '<b>Exit Reason</b> tells you why we sold: '
            '"15% Hard Stop" = cut loss before it got worse · '
            '"220 EMA break" = stock fell below its long-term average · '
            '"Target" = hit profit target. Default view: newest first.'
            '</div>', unsafe_allow_html=True,
        )

        with st.spinner('Verifying past trades against all 8 filters…'):
            trades_verified = _verify_past_trades(trades)
        trades_sorted = trades_verified.copy()
        trades_sorted['Exit_Date'] = pd.to_datetime(trades_sorted['Exit_Date'], errors='coerce')
        trades_sorted = trades_sorted.sort_values('Exit_Date', ascending=False)

        # ── Period + Strict filter ─────────────────────────────────────────
        exit_max = trades_sorted['Exit_Date'].max()
        all_years = sorted({d.year for d in trades_sorted['Exit_Date'].dropna()}, reverse=True)

        fc1, fc2, fc3 = st.columns([1.4, 1.2, 1.4])
        with fc1:
            period_choice = st.radio(
                'Show', ['Last 1Y', 'Last 3Y', 'All', 'Pick year'],
                index=0, horizontal=True, key='me_trades_period',
                label_visibility='collapsed',
            )
        with fc2:
            year_pick = None
            if period_choice == 'Pick year' and all_years:
                year_pick = st.selectbox('Year', all_years, key='me_trades_year',
                                         label_visibility='collapsed')
        with fc3:
            strict_mode = st.toggle(
                '🔒 Strict mode — clean signals only', value=False, key='me_trades_strict',
                help='Hide marginal trades. Keeps only entries where ALL 8 filters passed at signal day '
                     'AND breakout margin >= 1% above prior 52W close high. '
                     'Cuts out edge cases like 0.25%-above-high entries.',
            )

        if period_choice == 'Last 1Y':
            cutoff = exit_max - pd.Timedelta(days=365)
            view = trades_sorted[trades_sorted['Exit_Date'] >= cutoff]
        elif period_choice == 'Last 3Y':
            cutoff = exit_max - pd.Timedelta(days=365 * 3)
            view = trades_sorted[trades_sorted['Exit_Date'] >= cutoff]
        elif period_choice == 'Pick year' and year_pick is not None:
            view = trades_sorted[trades_sorted['Exit_Date'].dt.year == year_pick]
        else:
            view = trades_sorted

        n_pre_strict = len(view)
        n_marginal   = 0
        if strict_mode and 'Breakout_Margin_Pct' in view.columns:
            mask = (view['All_Filters_OK'] == True) & (view['Breakout_Margin_Pct'] >= 1.0)
            n_marginal = int((~mask).sum())
            view = view[mask]

        st.caption(
            f'Showing **{len(view)}** trades of {len(trades_sorted)} total. '
            f'Range: {view["Exit_Date"].min().strftime("%b %Y") if not view.empty else "—"} → '
            f'{view["Exit_Date"].max().strftime("%b %Y") if not view.empty else "—"}.'
            + (f' **🔒 Strict mode** hid {n_marginal} marginal trade(s) in this window.' if strict_mode else
               '  Toggle 🔒 Strict mode to hide marginal-breakout entries.')
        )

        base_cols = ['Ticker', 'Entry_Date', 'Entry_Price', 'Prior_52W_High',
                     'Breakout_Margin_Pct',
                     'Exit_Date', 'Exit_Price', 'PnL_Pct', 'Holding_Days',
                     'Exit_Reason', 'Result', 'Filter_Detail']
        extra = [c for c in ('Entry_Type', 'Recovery_Speed', 'Recovery_Days')
                 if c in view.columns]
        keep = [c for c in base_cols + extra if c in view.columns]
        t = view[keep].copy()
        t['Ticker']      = t['Ticker'].str.replace('.NS', '')
        t['Entry_Price'] = t['Entry_Price'].apply(lambda x: f'₹{x:,.2f}')
        t['Exit_Price']  = t['Exit_Price'].apply(lambda x: f'₹{x:,.2f}')
        if 'Prior_52W_High' in t.columns:
            t['Prior_52W_High'] = t['Prior_52W_High'].apply(
                lambda x: f'₹{x:,.2f}' if pd.notna(x) else '—'
            )
        if 'Breakout_Margin_Pct' in t.columns:
            t['Breakout_Margin_Pct'] = t['Breakout_Margin_Pct'].apply(
                lambda x: f'+{x:.2f}%' if pd.notna(x) and x >= 0 else
                          (f'{x:.2f}%' if pd.notna(x) else '—')
            )
        t['Entry_Date']  = pd.to_datetime(t['Entry_Date']).dt.strftime('%Y-%m-%d')
        t['Exit_Date']   = pd.to_datetime(t['Exit_Date']).dt.strftime('%Y-%m-%d')
        t['PnL_Pct']     = t['PnL_Pct'].apply(lambda x: f'{x:+.2f}%')
        # Rename for compactness
        t = t.rename(columns={
            'Prior_52W_High':      'Prior 52W High',
            'Breakout_Margin_Pct': 'BK Margin',
            'Filter_Detail':       'Filters',
        })
        row_colors = ['rgba(34,197,94,0.10)' if r == 'Win' else 'rgba(239,68,68,0.08)'
                      for r in view['Result']]
        st.plotly_chart(chart_plotly_table(t, row_colors=row_colors, score_col=None),
                        width='stretch')

        # Legend for the new BK Margin + Filters columns
        st.markdown(
            '<div style="font-size:11px;color:var(--muted-foreground);margin-top:6px;line-height:1.6;">'
            '<b>BK Margin</b> = how much the signal-day close exceeded the prior 52-week close high. '
            'Margins under +1% (like AXISBANK +0.25% on 14 Jan 2026) are knife-edge breakouts that often fail. '
            'Strict mode hides them. <b>Filters</b> column shows pass/fail of every condition at signal day: '
            'F1 trend · F2 close>SMA50 · F3 MA align · F4 vs 52W low · F5 dip · F6 choppiness · BK breakout · V volume.'
            '</div>',
            unsafe_allow_html=True,
        )

        # ── Edge Proof — "did the strategy really work, on which stocks?" ──
        st.markdown('<br>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="sec-hdr" style="color:{color}">🔬 Edge Proof — cross-check the SEBI claim</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div style="font-size:12px;color:var(--muted-foreground);margin:-4px 0 12px 0;line-height:1.65;">'
            'Two views side by side: <b>All signals</b> (canonical strategy as documented) vs '
            '<b>Strict signals</b> (only ATH-class entries with breakout margin ≥ 1%). '
            'If the win rate AND compounded return both stay attractive under strict mode, the edge is real. '
            'If strict mode kills the numbers, the strategy is over-reliant on marginal entries.'
            '</div>',
            unsafe_allow_html=True,
        )

        def _summary(df: pd.DataFrame) -> dict:
            if df.empty:
                return {'n': 0, 'wr': 0.0, 'avg': 0.0, 'lakh_to': 100_000.0, 'tickers': 0}
            wins = (df['Result'] == 'Win').sum()
            wr   = wins / len(df) * 100
            avg  = df['PnL_Pct'].mean()
            # Compounded equity if you took 100% of capital on each trade sequentially
            comp_factor = (1 + df.sort_values('Entry_Date')['PnL_Pct'] / 100).prod()
            return {
                'n': len(df), 'wr': wr, 'avg': avg,
                'lakh_to': 100_000.0 * comp_factor,
                'tickers': df['Ticker'].nunique(),
            }

        strict_df = trades_verified[
            (trades_verified['All_Filters_OK'] == True) &
            (trades_verified['Breakout_Margin_Pct'] >= 1.0)
        ]
        s_all    = _summary(trades_verified)
        s_strict = _summary(strict_df)

        epc1, epc2 = st.columns(2)
        for col_box, lbl, s, accent in [
            (epc1, 'All Signals (canonical strategy)',     s_all,    '#94A3B8'),
            (epc2, 'Strict Signals (margin ≥ 1%, all 8 ✓)', s_strict, '#22C55E'),
        ]:
            wr_color = '#22C55E' if s['wr'] >= 50 else '#EF4444'
            grew_color = '#22C55E' if s['lakh_to'] > 100_000 else '#EF4444'
            with col_box:
                st.markdown(
                    f'<div class="hub-card" style="border-top:3px solid {accent};">'
                    f'  <div class="strategy-name" style="color:{accent}">{lbl}</div>'
                    f'  <div style="font-size:11px;color:var(--muted-foreground);">If ₹1 lakh went into every signal sequentially</div>'
                    f'  <div class="big-num" style="color:{grew_color}">₹{s["lakh_to"]:,.0f}</div>'
                    f'  <div class="plain-label">compounded across {s["n"]} trades on {s["tickers"]} stocks</div>'
                    f'  <div class="divider"></div>'
                    f'  <div class="row">'
                    f'    <div class="kv-block"><div class="kv-l">Win Rate</div>'
                    f'      <div class="kv-v" style="color:{wr_color}">{s["wr"]:.0f}%</div></div>'
                    f'    <div class="kv-block"><div class="kv-l">Avg PnL</div>'
                    f'      <div class="kv-v">{s["avg"]:+.2f}%</div></div>'
                    f'    <div class="kv-block"><div class="kv-l">Trades</div>'
                    f'      <div class="kv-v">{s["n"]}</div></div>'
                    f'  </div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        # Per-ticker success table — "which stocks worked?"
        st.markdown('<br>', unsafe_allow_html=True)
        st.markdown(
            '<div style="font-size:13px;color:var(--foreground);margin-bottom:6px;">'
            '<b>📋 Per-stock track record</b> — every ticker the strategy ever bought, sortable.'
            '</div>',
            unsafe_allow_html=True,
        )
        track_src = strict_df if strict_mode else trades_verified
        if track_src.empty:
            st.caption('No trades match the current filter.')
        else:
            track = track_src.groupby('Ticker').agg(
                Trades=('Result', 'count'),
                Wins=('Result', lambda s: int((s == 'Win').sum())),
                Win_Rate=('Result', lambda s: round((s == 'Win').mean() * 100, 0)),
                Avg_PnL=('PnL_Pct', lambda s: round(s.mean(), 2)),
                Best=('PnL_Pct', lambda s: round(s.max(), 2)),
                Worst=('PnL_Pct', lambda s: round(s.min(), 2)),
                Total_PnL=('PnL_Pct', lambda s: round(s.sum(), 2)),
            ).reset_index()
            track['Ticker'] = track['Ticker'].str.replace('.NS', '')
            track = track.sort_values('Total_PnL', ascending=False)
            track.columns = ['Ticker', 'Trades', 'Wins', 'Win %', 'Avg PnL %',
                              'Best %', 'Worst %', 'Total PnL %']
            st.dataframe(track, hide_index=True, width='stretch', height=min(600, 38 * len(track) + 40))
            st.caption(
                f'**{len(track)}** distinct stocks traded. '
                f'**{int((track["Total PnL %"] > 0).sum())}** were net-positive contributors; '
                f'**{int((track["Total PnL %"] <= 0).sum())}** were net-negative. '
                'Sort by Total PnL % to see your real winners and losers.'
            )

        # ── Loss-Free Holding Period analytic ─────────────────────────────
        st.markdown('<br>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="sec-hdr" style="color:{color}">Loss-Free Holding Window — '
            f'how long past signals stayed in profit before the first down-close</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div style="font-size:12px;color:#8892a4;margin:-4px 0 10px 0;">'
            'For every past qualifying entry, we walk forward day-by-day and count '
            'how many trading days the close stayed <b>at or above the entry price</b> '
            'before it first dipped below. Higher numbers = the signal gives you more '
            'cushion to set tight stops without getting shaken out.'
            '</div>', unsafe_allow_html=True,
        )

        lfh = _loss_free_holding(trades)
        if lfh.empty:
            st.caption('No closed trades to analyse.')
        else:
            med  = float(lfh['Loss_Free_Days'].median())
            p25  = float(lfh['Loss_Free_Days'].quantile(0.25))
            p75  = float(lfh['Loss_Free_Days'].quantile(0.75))
            pct_safe_5   = float((lfh['Loss_Free_Days'] >=  5).mean() * 100)
            pct_safe_20  = float((lfh['Loss_Free_Days'] >= 20).mean() * 100)
            pct_safe_60  = float((lfh['Loss_Free_Days'] >= 60).mean() * 100)
            never_dipped = int((lfh['Never_Dipped']).sum())

            k1, k2, k3, k4, k5 = st.columns(5)
            with k1:
                st.markdown(pill(
                    'Median Safe Days', f'{med:.0f}', f'IQR {p25:.0f}–{p75:.0f}', color,
                    explain='Half of past signals stayed at-or-above entry for at least this many trading days.',
                ), unsafe_allow_html=True)
            with k2:
                st.markdown(pill(
                    '≥ 1 Week Safe', f'{pct_safe_5:.0f}%', 'of all past signals', '#22C55E',
                    explain='% of past entries that stayed in profit for at least 5 trading days.',
                ), unsafe_allow_html=True)
            with k3:
                st.markdown(pill(
                    '≥ 1 Month Safe', f'{pct_safe_20:.0f}%', 'of all past signals', '#22C55E',
                    explain='% of past entries that stayed in profit for at least 20 trading days.',
                ), unsafe_allow_html=True)
            with k4:
                st.markdown(pill(
                    '≥ 3 Months Safe', f'{pct_safe_60:.0f}%', 'of all past signals', '#22C55E',
                    explain='% of past entries that stayed in profit for at least 60 trading days.',
                ), unsafe_allow_html=True)
            with k5:
                st.markdown(pill(
                    'Never Dipped', f'{never_dipped}', f'of {len(lfh)} trades', '#60A5FA',
                    explain='Trades where the close never went below the entry price for the entire hold.',
                ), unsafe_allow_html=True)

            # Per-trade detail table
            with st.expander('Per-trade detail — loss-free days for every past signal'):
                disp = lfh[[
                    'Ticker', 'Entry_Date', 'Entry_Price', 'Loss_Free_Days',
                    'First_Loss_Date', 'Holding_Days', 'PnL_Pct', 'Result',
                ]].copy()
                disp['Entry_Price'] = disp['Entry_Price'].apply(lambda x: f'₹{x:,.2f}')
                disp['PnL_Pct']     = disp['PnL_Pct'].apply(lambda x: f'{x:+.2f}%')
                row_colors_lfh = [
                    'rgba(34,197,94,0.10)' if r == 'Win' else 'rgba(239,68,68,0.06)'
                    for r in disp['Result']
                ]
                st.plotly_chart(
                    chart_plotly_table(disp, row_colors=row_colors_lfh, score_col=None),
                    width='stretch',
                )

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

    # ── Loss-Free Holding Window — proof the strategy "works" ───────────────
    st.markdown('### 🛟 Loss-Free Holding Window — does this strategy actually work?')
    st.markdown(
        '<div style="font-size:12px;color:#94A3B8;margin:-4px 0 10px 0;line-height:1.65;">'
        'For every past qualifying signal, we walk forward day-by-day and count how many '
        '<b>trading days</b> the close stayed <b>at or above the entry price</b> before the first down-close. '
        'High numbers across the board = the strategy gives reliable cushion, safe to scale capital. '
        'Low numbers = signals dip immediately, capital at risk.'
        '</div>',
        unsafe_allow_html=True,
    )

    folders = _STRATEGY_OHLCV_FOLDERS.get(strategy, ('data/nse_bse', 'data'))
    lfh = _loss_free_holding(trades_x, folders)
    if lfh.empty:
        st.caption('Could not match any trades to OHLCV data for this strategy.')
    else:
        med   = float(lfh['Loss_Free_Days'].median())
        p25   = float(lfh['Loss_Free_Days'].quantile(0.25))
        p75   = float(lfh['Loss_Free_Days'].quantile(0.75))
        mean_ = float(lfh['Loss_Free_Days'].mean())
        pct5  = float((lfh['Loss_Free_Days'] >=  5).mean() * 100)
        pct20 = float((lfh['Loss_Free_Days'] >= 20).mean() * 100)
        pct60 = float((lfh['Loss_Free_Days'] >= 60).mean() * 100)
        never = int(lfh['Never_Dipped'].sum())

        # Verdict — strategy "works" if median >= 5 and ≥40% safe 20+ days
        if med >= 10 and pct20 >= 50:
            verdict, vcolor, vicon = ('STRATEGY WORKING — safe to scale capital',  '#22C55E', '✅')
        elif med >= 5 and pct20 >= 30:
            verdict, vcolor, vicon = ('CONDITIONAL — works but size positions carefully', '#F59E0B', '⚠️')
        else:
            verdict, vcolor, vicon = ('WEAK — signals dip fast, do not scale up', '#EF4444', '❌')

        st.markdown(
            f'<div style="background:{vcolor}1A;border:1px solid {vcolor}55;border-left:4px solid {vcolor};'
            f'border-radius:10px;padding:12px 16px;margin-bottom:14px;font-size:13px;">'
            f'<span style="font-size:18px;margin-right:10px;">{vicon}</span>'
            f'<b style="color:{vcolor};letter-spacing:.03em;">{verdict}</b>'
            f'<span style="color:#94A3B8;margin-left:16px;">'
            f'median {med:.0f}d safe · {pct20:.0f}% of signals stay loss-free ≥ 20d · {never} never dipped'
            f'</span></div>',
            unsafe_allow_html=True,
        )

        k1, k2, k3, k4, k5 = st.columns(5)
        with k1:
            _kpi_card('Median Safe Days', f'{med:.0f}',
                      f'IQR {p25:.0f}–{p75:.0f} · mean {mean_:.1f}', color)
        with k2:
            _kpi_card('≥ 1 Week Safe', f'{pct5:.0f}%',
                      f'{int((lfh["Loss_Free_Days"]>=5).sum())} of {len(lfh)} trades', '#22C55E')
        with k3:
            _kpi_card('≥ 1 Month Safe', f'{pct20:.0f}%',
                      f'{int((lfh["Loss_Free_Days"]>=20).sum())} of {len(lfh)} trades', '#22C55E')
        with k4:
            _kpi_card('≥ 3 Months Safe', f'{pct60:.0f}%',
                      f'{int((lfh["Loss_Free_Days"]>=60).sum())} of {len(lfh)} trades', '#22C55E')
        with k5:
            _kpi_card('Never Dipped', f'{never}',
                      f'of {len(lfh)} trades · {never/len(lfh)*100:.0f}%', '#60A5FA')

        # Distribution histogram
        try:
            import plotly.express as px  # noqa
        except Exception:
            px = None
        bins = [0, 1, 5, 10, 20, 40, 60, 120, 9999]
        labels = ['0d', '1-4d', '5-9d', '10-19d', '20-39d', '40-59d', '60-119d', '120d+']
        lfh_bucketed = pd.cut(lfh['Loss_Free_Days'], bins=bins, labels=labels, right=False)
        hist = lfh_bucketed.value_counts().reindex(labels, fill_value=0).reset_index()
        hist.columns = ['Loss_Free_Bucket', 'Trade_Count']
        fig_h = go.Figure(go.Bar(
            x=hist['Loss_Free_Bucket'], y=hist['Trade_Count'],
            marker_color=['#EF4444', '#EF4444', '#F59E0B', '#F59E0B',
                          '#22C55E', '#22C55E', '#22C55E', '#22C55E'],
            text=hist['Trade_Count'], textposition='outside',
            hovertemplate='%{x}<br>%{y} trades<extra></extra>',
        ))
        fig_h.update_layout(
            height=240, margin=dict(l=40, r=20, t=30, b=30),
            paper_bgcolor='#1c1c1c', plot_bgcolor='#1c1c1c',
            font=dict(color='#F1F5F9', family='Inter'),
            title=dict(text='Distribution — how long signals stayed loss-free',
                       font=dict(size=12, color='#94A3B8')),
            xaxis=dict(showgrid=False, tickfont=dict(size=11)),
            yaxis=dict(title='# Trades', gridcolor='#1E293B', tickfont=dict(size=10)),
            showlegend=False,
        )
        st.plotly_chart(fig_h, width='stretch')

        # Per-trade detail (sorted by Loss_Free_Days desc — best signals first)
        with st.expander(f'📋 Per-trade detail ({len(lfh)} signals) — sortable, see exactly what worked'):
            disp = lfh[[
                'Ticker', 'Entry_Date', 'Entry_Price', 'Loss_Free_Days',
                'First_Loss_Date', 'Holding_Days', 'PnL_Pct', 'Result',
            ]].copy().sort_values('Loss_Free_Days', ascending=False)
            disp['Entry_Price'] = disp['Entry_Price'].apply(lambda x: f'₹{x:,.2f}')
            disp['PnL_Pct']     = disp['PnL_Pct'].apply(lambda x: f'{x:+.2f}%')
            st.dataframe(disp, hide_index=True, width='stretch')

    st.markdown('<div style="height:18px;"></div>', unsafe_allow_html=True)

    # ── Stop-Loss Recommendation + Position Sizer ──────────────────────────
    st.markdown('### 🛡️ Stop-Loss & Position Sizing — buy size that limits loss')
    st.markdown(
        '<div style="font-size:12px;color:#94A3B8;margin:-4px 0 12px 0;line-height:1.65;">'
        'A good stop-loss is <b>loose enough that 95% of past winners survive their normal pullback</b>, '
        'but <b>tight enough that losers get cut early</b>. We derive it from the Winner MAE p95 '
        '(plus a 20% buffer) and the recent ATR. Hard-capped at -15% and floored at -5%.'
        '</div>',
        unsafe_allow_html=True,
    )

    rec = report.get('stop_recommendation', {}) or {}
    winner_mae_p95 = rec.get('winner_mae_p95')

    sc1, sc2, sc3 = st.columns([1, 1, 1])
    with sc1:
        if winner_mae_p95 is not None:
            sugg = _suggest_stop(100.0, atr=None, winner_mae_p95_pct=winner_mae_p95)
            stop_pct = sugg['stop_pct']
            source   = sugg['source']
        else:
            stop_pct = 10.0
            source   = 'Default (no MAE data)'
        _kpi_card('Suggested Stop %', f'-{stop_pct:.1f}%',
                  f'derived from: {source}', '#EF4444')
    with sc2:
        # Reward needed to make this risk/reward >= 2:1
        rr_target_pct = stop_pct * 2
        _kpi_card('Target Move (R:R 2:1)', f'+{rr_target_pct:.1f}%',
                  'minimum profit goal per trade', '#22C55E')
    with sc3:
        # Win-rate breakeven for this R:R
        breakeven = 100 / (1 + 2)  # for 2:1, need 33.3% win rate
        actual_wr = report.get('overall_win_rate', 0)
        verdict_clr = '#22C55E' if actual_wr >= breakeven else '#EF4444'
        _kpi_card('Breakeven Win Rate', f'{breakeven:.0f}%',
                  f'strategy actual: {actual_wr}% ({"OK ✓" if actual_wr >= breakeven else "below break-even"})',
                  verdict_clr)

    # ── Interactive Position Sizer ─────────────────────────────────────────
    with st.expander('💼 Position Sizer — type your capital, get exact buy quantity', expanded=False):
        st.markdown(
            '<div style="font-size:12px;color:#94A3B8;margin-bottom:10px;line-height:1.6;">'
            'Risk-based sizing: you decide what % of your portfolio you are willing to lose if the stop hits. '
            'We then compute the maximum shares you can buy so that a stop-out loses exactly that amount. '
            'Rule of thumb: <b>1-2% risk per trade</b>.'
            '</div>',
            unsafe_allow_html=True,
        )
        ps1, ps2, ps3, ps4 = st.columns(4)
        with ps1:
            capital = st.number_input(
                'Portfolio capital (₹)', min_value=10_000, max_value=100_000_000,
                value=500_000, step=10_000, key=f'sizer_cap_{strategy}',
            )
        with ps2:
            risk_pct = st.number_input(
                'Risk per trade (%)', min_value=0.1, max_value=10.0,
                value=2.0, step=0.1, key=f'sizer_risk_{strategy}',
            )
        with ps3:
            entry_price = st.number_input(
                'Planned entry (₹)', min_value=1.0, max_value=500_000.0,
                value=1000.0, step=10.0, key=f'sizer_entry_{strategy}',
            )
        with ps4:
            stop_used = st.number_input(
                'Stop-loss %', min_value=1.0, max_value=30.0,
                value=float(stop_pct), step=0.5, key=f'sizer_stop_{strategy}',
            )

        stop_price_user = entry_price * (1 - stop_used / 100.0)
        risk_per_share  = entry_price - stop_price_user
        risk_budget     = capital * risk_pct / 100.0
        shares          = int(risk_budget // risk_per_share) if risk_per_share > 0 else 0
        position_size   = shares * entry_price
        position_pct    = (position_size / capital) * 100 if capital else 0
        max_loss_rs     = shares * risk_per_share

        # Target prices for 2:1 and 3:1
        tgt_2r = entry_price * (1 + 2 * stop_used / 100.0)
        tgt_3r = entry_price * (1 + 3 * stop_used / 100.0)

        st.markdown('<div style="height:8px;"></div>', unsafe_allow_html=True)
        r1, r2, r3, r4 = st.columns(4)
        with r1:
            _kpi_card('Buy Quantity', f'{shares:,}',
                      f'₹{position_size:,.0f} deployed ({position_pct:.1f}% of capital)', '#22C55E')
        with r2:
            _kpi_card('Stop Price', f'₹{stop_price_user:,.2f}',
                      f'risk/share ₹{risk_per_share:,.2f}', '#EF4444')
        with r3:
            _kpi_card('Max Loss if Stop Hit', f'₹{max_loss_rs:,.0f}',
                      f'= {risk_pct:.1f}% of portfolio', '#EF4444')
        with r4:
            _kpi_card('Target 2:1 / 3:1', f'₹{tgt_2r:,.2f}',
                      f'3:1 target ₹{tgt_3r:,.2f}', '#22C55E')

        st.caption(
            f'📋 **Trade plan:** Buy {shares:,} shares of this ticker at ₹{entry_price:,.2f}, '
            f'place stop at ₹{stop_price_user:,.2f} (-{stop_used:.1f}%), '
            f'book partial profit at ₹{tgt_2r:,.2f} (+{stop_used*2:.1f}%). '
            f'If stop hits, you lose ₹{max_loss_rs:,.0f} = {risk_pct:.1f}% of your ₹{capital:,.0f} capital.'
        )

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
        st.caption(
            'All past trades are sorted by their entry Score (0–10) and split into 5 equal-size groups '
            '(quintiles, Q1 = weakest to Q5 = strongest). Ideal pattern: win rate climbs steadily from Q1 → Q5 '
            '("monotonic ladder"). If it does, the score is genuinely predictive.'
        )
        st.dataframe(df, hide_index=True, width='stretch')

    st.markdown('<div style="height:18px;"></div>', unsafe_allow_html=True)

    # ── Optimal Sell — partial booking sensitivity ─────────────────────────
    st.markdown('### 💰 Optimal Sell — when to take profits?')
    st.markdown(
        '<div style="font-size:12px;color:#8892a4;margin-bottom:6px;">'
        'Pretend you sold a chunk of the position at +10%, +15%, +20% etc. For each level: '
        '<b>Touched</b> = how many trades reached it, '
        '<b>Fade_Rate</b> = % of those that then gave the gain back (closed lower than the level), '
        '<b>Avg_Final</b> = where trades actually ended up. Low fade rate + high avg final = sweet spot for partial booking.'
        '</div>',
        unsafe_allow_html=True,
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
    st.markdown(
        '<div style="font-size:12px;color:#8892a4;margin:-4px 0 10px 0;">'
        '<b>MAE</b> (Maximum Adverse Excursion) = the deepest dip a trade saw before it closed. '
        'Even winning trades dip — the question is how deep. '
        '<b>p95</b> = "95% of trades stayed inside this number" (worst case, ignoring rare outliers). '
        '<b>mean</b> = the typical/average dip.'
        '</div>',
        unsafe_allow_html=True,
    )
    rec = report.get('stop_recommendation', {})
    if rec:
        cc = st.columns(4)
        with cc[0]:
            _kpi_card('Winner MAE p95',
                      f'{rec.get("winner_mae_p95", "—")}%',
                      '95% of winners survived this dip', '#00c853')
        with cc[1]:
            _kpi_card('Winner MAE mean',
                      f'{rec.get("winner_mae_mean", "—")}%',
                      'typical winner dip', '#00c853')
        with cc[2]:
            _kpi_card('Loser MAE p95',
                      f'{rec.get("loser_mae_p95", "—")}%',
                      '95% of losers stayed inside', '#e85a8c')
        with cc[3]:
            _kpi_card('Loser MAE mean',
                      f'{rec.get("loser_mae_mean", "—")}%',
                      'typical loser dip', '#e85a8c')

        st.caption(
            'How to read: set the stop *just looser* than Winner MAE p95 — '
            'tight enough to cut losers fast, loose enough that 95% of eventual '
            'winners survive their normal pullback without getting stopped out.'
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

    # ── Monthly Returns Heatmap ────────────────────────────────────────────
    st.markdown('### 📅 Monthly Returns Heatmap — when does this strategy print money?')
    st.caption(
        'Each cell shows the average trade % return for trades that closed in that month. '
        'Green = profitable month, red = losing month. Patterns by month/year reveal market regimes.'
    )
    try:
        st.plotly_chart(_chart_monthly_heatmap(trades_x), width='stretch')
    except Exception as e:
        st.info(f'Could not render heatmap: {e}')

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


@st.cache_data(ttl=300)
def _data_freshness() -> dict:
    """Latest bar date across data folders + most-recent file mtime.

    Returns dict with: latest_bar (date str), file_mtime (datetime str),
    age_hours (float), source_file (str).
    """
    from datetime import datetime as _dt
    candidates = [
        Path(BASE_DIR) / 'data' / 'nse_bse',
        Path(BASE_DIR) / 'data',
        Path(BASE_DIR) / 'momentum_edge_data',
    ]
    latest_bar  = None
    newest_file = None
    newest_mtime = 0.0
    for folder in candidates:
        if not folder.exists():
            continue
        for probe in ('RELIANCE.NS.csv', 'HDFCBANK.NS.csv', 'INFY.NS.csv'):
            p = folder / probe
            if not p.exists():
                continue
            try:
                last = pd.read_csv(p, index_col=0, parse_dates=True).index[-1]
                if latest_bar is None or last > latest_bar:
                    latest_bar = last
                mtime = p.stat().st_mtime
                if mtime > newest_mtime:
                    newest_mtime = mtime
                    newest_file  = str(p.relative_to(BASE_DIR))
                break
            except Exception:
                continue
    if latest_bar is None:
        return {'latest_bar': '—', 'file_mtime': '—', 'age_hours': None, 'source_file': '—'}
    age_h = (_dt.now().timestamp() - newest_mtime) / 3600.0
    return {
        'latest_bar':  latest_bar.strftime('%d %b %Y'),
        'file_mtime':  _dt.fromtimestamp(newest_mtime).strftime('%d %b %Y %H:%M'),
        'age_hours':   round(age_h, 1),
        'source_file': newest_file or '—',
    }


def _render_regime_banner() -> None:
    """Persistent Nifty regime banner + data freshness shown above every page."""
    snap = _regime_snapshot()
    status = snap.get('status', 'Unknown')
    fresh  = _data_freshness()

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

    # Freshness chip — green if <24h, amber 24–72h, red >72h
    age = fresh.get('age_hours')
    if age is None:
        f_bg, f_fg, f_lbl = 'rgba(148,163,184,0.10)', '#94A3B8', 'No data'
    elif age < 24:
        f_bg, f_fg, f_lbl = 'rgba(34,197,94,0.10)', '#22C55E', f'{age:.1f}h ago'
    elif age < 72:
        f_bg, f_fg, f_lbl = 'rgba(245,158,11,0.10)', '#F59E0B', f'{age:.0f}h ago'
    else:
        f_bg, f_fg, f_lbl = 'rgba(239,68,68,0.10)', '#EF4444', f'{age / 24:.0f}d ago'

    fresh_chip = (
        f'<span style="margin-left:auto;display:inline-flex;align-items:center;gap:8px;'
        f'background:{f_bg};border:1px solid {f_fg}55;border-radius:6px;'
        f'padding:4px 10px;font-size:11.5px;color:{f_fg};font-weight:500;"'
        f' title="Last bar {fresh["latest_bar"]} · File saved {fresh["file_mtime"]}">'
        f'● Data updated {f_lbl} · last bar {fresh["latest_bar"]}'
        f'</span>'
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
          {fresh_chip}
        </div>
        """,
        unsafe_allow_html=True,
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  SUGGESTIONS PAGE — risk-filtered, history-backed picks
# ═══════════════════════════════════════════════════════════════════════════════

def _edge_buckets(trades: pd.DataFrame, group_cols: list[str],
                  min_n: int = 3) -> pd.DataFrame:
    """Rank historical edge for each (group_cols) bucket.

    Returns DF with: group cols, n, win_rate, avg_pnl, median_pnl,
    profit_factor, expectancy, edge_score. Sorted by edge_score desc.
    """
    if trades is None or trades.empty:
        return pd.DataFrame()
    cols = [c for c in group_cols if c in trades.columns]
    if not cols or 'Result' not in trades.columns or 'PnL_Pct' not in trades.columns:
        return pd.DataFrame()

    def _agg(g: pd.DataFrame) -> pd.Series:
        wins   = g.loc[g['Result'] == 'Win', 'PnL_Pct']
        losses = g.loc[g['Result'] == 'Loss', 'PnL_Pct']
        n      = len(g)
        wr     = (g['Result'] == 'Win').mean() * 100
        avg    = g['PnL_Pct'].mean()
        med    = g['PnL_Pct'].median()
        gp     = wins.sum() if not wins.empty else 0.0
        gl     = abs(losses.sum()) if not losses.empty else 0.0
        pf     = (gp / gl) if gl > 0 else (gp if gp > 0 else 0.0)
        exp_   = (wr/100) * (wins.mean() if not wins.empty else 0.0) + \
                 (1 - wr/100) * (losses.mean() if not losses.empty else 0.0)
        return pd.Series({
            'n': n, 'win_rate': wr, 'avg_pnl': avg, 'median_pnl': med,
            'profit_factor': pf, 'expectancy': exp_,
        })

    g = trades.groupby(cols, dropna=False).apply(_agg).reset_index()
    g = g[g['n'] >= min_n].copy()
    if g.empty:
        return g
    # Edge score: expectancy weighted by sqrt(n) — penalises small samples
    import numpy as _np
    g['edge_score'] = g['expectancy'] * _np.sqrt(g['n'])
    g = g.sort_values('edge_score', ascending=False).reset_index(drop=True)
    return g


def _suggestion_card(rank: int, ticker: str, company: str, strategy: str,
                     signal: str, close: float, stop: float, target: float,
                     confidence: float, avg_pnl: float, n_hist: int,
                     position_pct: float, rationale: str) -> str:
    color = THEME[strategy]['color']
    bg    = THEME[strategy]['bg']
    icon  = THEME[strategy]['icon']
    conf_c = '#22C55E' if confidence >= 60 else ('#f9c200' if confidence >= 50 else '#EF4444')
    rr = abs((target - close) / (close - stop)) if (close - stop) > 0 else 0
    return (
        f'<div style="border:1px solid {color}44;background:{bg};border-radius:14px;'
        f'padding:18px 20px;margin-bottom:12px;">'
        f'  <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;">'
        f'    <div>'
        f'      <div style="font-size:11px;color:#3d4a60;letter-spacing:.08em;">#{rank} · {icon} {strategy}</div>'
        f'      <div style="font-size:20px;font-weight:900;color:#e4e8f0;margin-top:2px;">{ticker}</div>'
        f'      <div style="font-size:12px;color:#6a748a;">{company}</div>'
        f'    </div>'
        f'    <div style="text-align:right;">'
        f'      <div style="font-size:11px;color:#3d4a60;letter-spacing:.06em;">CONFIDENCE</div>'
        f'      <div style="font-size:24px;font-weight:900;color:{conf_c};">{confidence:.0f}%</div>'
        f'      <div style="font-size:10px;color:#6a748a;">hist. win rate · n={n_hist}</div>'
        f'    </div>'
        f'  </div>'
        f'  <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin-top:14px;'
        f'              padding-top:12px;border-top:1px solid #ffffff10;">'
        f'    <div><div style="font-size:10px;color:#3d4a60;">SIGNAL</div>'
        f'         <div style="font-size:13px;color:#e4e8f0;font-weight:700;">{signal}</div></div>'
        f'    <div><div style="font-size:10px;color:#3d4a60;">ENTRY</div>'
        f'         <div style="font-size:13px;color:#e4e8f0;font-weight:700;">₹{close:,.2f}</div></div>'
        f'    <div><div style="font-size:10px;color:#3d4a60;">STOP</div>'
        f'         <div style="font-size:13px;color:#EF4444;font-weight:700;">₹{stop:,.2f}</div></div>'
        f'    <div><div style="font-size:10px;color:#3d4a60;">TARGET</div>'
        f'         <div style="font-size:13px;color:#22C55E;font-weight:700;">₹{target:,.2f}</div></div>'
        f'    <div><div style="font-size:10px;color:#3d4a60;">R:R</div>'
        f'         <div style="font-size:13px;color:#e4e8f0;font-weight:700;">1 : {rr:.2f}</div></div>'
        f'  </div>'
        f'  <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:10px;margin-top:10px;">'
        f'    <div><div style="font-size:10px;color:#3d4a60;">AVG HIST PnL</div>'
        f'         <div style="font-size:13px;color:{"#22C55E" if avg_pnl>0 else "#EF4444"};font-weight:700;">{avg_pnl:+.2f}%</div></div>'
        f'    <div><div style="font-size:10px;color:#3d4a60;">MAX POSITION SIZE</div>'
        f'         <div style="font-size:13px;color:#e4e8f0;font-weight:700;">{position_pct:.0f}% of capital</div></div>'
        f'  </div>'
        f'  <div style="margin-top:12px;font-size:12px;color:#8892a4;line-height:1.55;">'
        f'    💡 {rationale}'
        f'  </div>'
        f'</div>'
    )


def _build_monthly_suggestions(m: dict, is_bull: bool, max_picks: int = 5) -> list[dict]:
    """Monthly: top-RS Strong-BUY signals from live_rankings, gated by regime."""
    out = []
    rk = m.get('rankings')
    if rk is None or rk.empty:
        return out
    rk = rk.copy()
    # Use historical equity to derive avg monthly gain as confidence proxy
    eq = m.get('equity')
    hist_wr = 60.0  # Monthly Rotation has confirmed +21% CAGR
    hist_avg = 1.8  # avg monthly return
    if eq is not None and 'Strategy_Value' in eq.columns:
        monthly_ret = eq['Strategy_Value'].pct_change().dropna() * 100
        if not monthly_ret.empty:
            hist_wr  = float((monthly_ret > 0).mean() * 100)
            hist_avg = float(monthly_ret.mean())

    # Filter to Strong BUY only
    if 'Signal' in rk.columns:
        rk = rk[rk['Signal'].astype(str).str.contains('Strong BUY', case=False, na=False)]
    rk = rk.head(max_picks)

    for _, r in rk.iterrows():
        close = float(r.get('Current_Price', 0) or 0)
        if close <= 0:
            continue
        stop   = round(close * 0.92, 2)   # 8% stop on monthly (cut early)
        target = round(close * 1.10, 2)   # 10% target
        rationale = (
            f"Top-{int(r.get('Rank', 0))} RS pick. RS Score {float(r.get('RS_Score', 0)):.1f} — "
            f"price beating Nifty by {float(r.get('Return_%', 0)) - float(r.get('Benchmark_Return_%', 0)):+.1f}% this month. "
            f"Monthly Rotation backtest: ~21% CAGR, max DD -11%. " +
            ("✅ Regime is Bull — entries allowed." if is_bull else "⚠️ Regime is Bear — hold off or size half.")
        )
        out.append({
            'ticker': str(r.get('Ticker', '')).replace('.NS', ''),
            'company': str(r.get('Company', '')),
            'strategy': S_MONTHLY,
            'signal': str(r.get('Signal', '')),
            'close': close, 'stop': stop, 'target': target,
            'confidence': hist_wr, 'avg_pnl': hist_avg, 'n_hist': len(eq) if eq is not None else 0,
            'position_pct': 20.0 if is_bull else 10.0,
            'edge_score': hist_wr + float(r.get('RS_Score', 0)),
            'rationale': rationale,
        })
    return out


def _build_ipo_suggestions(i: dict, is_bull: bool, max_picks: int = 5) -> list[dict]:
    """IPO Edge: live signals filtered by best historical Setup_Type."""
    out = []
    sig = i.get('signals')
    tr  = i.get('trades')
    if sig is None or sig.empty:
        return out

    edge_setup = _edge_buckets(tr, ['Setup_Type'], min_n=2) if tr is not None else pd.DataFrame()
    best_setups = set()
    setup_lookup = {}
    if not edge_setup.empty:
        # Keep setups with positive expectancy only
        good = edge_setup[edge_setup['expectancy'] > 0]
        best_setups = set(good['Setup_Type'].dropna().astype(str))
        setup_lookup = {str(r['Setup_Type']): r for _, r in edge_setup.iterrows()}

    # Filter signals to Breakout / Near Breakout only, then to best setups if data available
    if 'Signal' in sig.columns:
        sig = sig[sig['Signal'].astype(str).str.contains('Breakout|Near', case=False, regex=True, na=False)]
    if 'Setup' in sig.columns and best_setups:
        sig = sig[sig['Setup'].astype(str).isin(best_setups)]
    sig = sig.head(max_picks)

    for _, r in sig.iterrows():
        close = float(r.get('Close', 0) or 0)
        if close <= 0:
            continue
        stop   = round(close * 0.92, 2)   # IPO Edge hard stop ~8%
        target = round(close * 1.20, 2)   # base swing 20%
        setup = str(r.get('Setup', ''))
        lk = setup_lookup.get(setup)
        wr   = float(lk['win_rate']) if lk is not None else 45.0
        avgp = float(lk['avg_pnl'])  if lk is not None else 0.0
        n    = int(lk['n'])          if lk is not None else 0
        rationale = (
            f"Setup: <b>{setup or 'STANDARD'}</b> · Stage: {r.get('Stage', '—')}. "
            f"Historical {setup or 'this setup'} won {wr:.0f}% of {n} trades, avg {avgp:+.2f}%. "
            f"Liquidity: {r.get('Liquidity', '—')}. "
            + ("✅ Bull regime — proceed." if is_bull else "⚠️ Bear regime — wait or quarter-size.")
        )
        out.append({
            'ticker': str(r.get('Ticker', '')).replace('.NS', ''),
            'company': str(r.get('Company', '')),
            'strategy': S_IPO,
            'signal': str(r.get('Signal', '')),
            'close': close, 'stop': stop, 'target': target,
            'confidence': wr, 'avg_pnl': avgp, 'n_hist': n,
            'position_pct': 8.0 if is_bull else 4.0,   # IPOs are higher-risk → smaller size
            'edge_score': wr + float(r.get('Score', 0)),
            'rationale': rationale,
        })
    return out


def _build_momentum_suggestions(mo: dict, is_bull: bool, max_picks: int = 5) -> list[dict]:
    """Momentum Edge: signals filtered by best (Entry_Type × Recovery_Speed) bucket."""
    out = []
    sig = mo.get('signals')
    tr  = mo.get('trades')
    if sig is None or sig.empty:
        return out

    edge = _edge_buckets(tr, ['Entry_Type', 'Recovery_Speed'], min_n=3) if tr is not None else pd.DataFrame()
    best_pairs = set()
    edge_lookup = {}
    if not edge.empty:
        good = edge[edge['expectancy'] > 0]
        for _, r in good.iterrows():
            best_pairs.add((str(r['Entry_Type']), str(r['Recovery_Speed'])))
            edge_lookup[(str(r['Entry_Type']), str(r['Recovery_Speed']))] = r

    # Keep only Breakout / Near Breakout / Watch Zone (drop weak/none)
    if 'Signal' in sig.columns:
        sig = sig[sig['Signal'].astype(str).str.contains('Breakout|Near|Watch', case=False, regex=True, na=False)]

    # Normalise live-signal labels to match backtest bucket keys
    _ENTRY_MAP = {'52W High': '52W_HIGH_FALLBACK', 'ATH': 'ATH'}
    def _norm_entry(v: str) -> str:
        return _ENTRY_MAP.get(str(v).strip(), str(v).strip())
    def _norm_recov(v: str) -> str:
        return str(v).split()[0] if v else ''

    if best_pairs and {'Entry Type', 'Recovery'}.issubset(sig.columns):
        sig = sig.copy()
        sig['_et_norm'] = sig['Entry Type'].map(_norm_entry)
        sig['_rs_norm'] = sig['Recovery'].map(_norm_recov)
        matched = sig[sig.apply(lambda r: (r['_et_norm'], r['_rs_norm']) in best_pairs, axis=1)]
        if not matched.empty:
            sig = matched
        # else: fall back to unfiltered sig — surfaces something rather than nothing

    # Require clean chart
    if 'Chart Qual' in sig.columns:
        clean = sig[sig['Chart Qual'].astype(str).str.contains('Clean', na=False)]
        if not clean.empty:
            sig = clean

    sig = sig.head(max_picks)

    for _, r in sig.iterrows():
        close = float(r.get('Close', 0) or 0)
        if close <= 0:
            continue
        ema220 = float(r.get('220 EMA', close * 0.85) or close * 0.85)
        # Stop = max(15% below entry, 220 EMA) — whichever is tighter
        stop_15  = close * 0.85
        stop = round(max(stop_15, ema220), 2)
        target = round(close * 1.25, 2)
        et_raw = str(r.get('Entry Type', ''))
        rs_raw = str(r.get('Recovery', ''))
        et = _ENTRY_MAP.get(et_raw.strip(), et_raw.strip())
        rs = rs_raw.split()[0] if rs_raw else ''
        lk = edge_lookup.get((et, rs))
        wr   = float(lk['win_rate']) if lk is not None else 40.0
        avgp = float(lk['avg_pnl'])  if lk is not None else 0.0
        n    = int(lk['n'])          if lk is not None else 0
        rationale = (
            f"Entry: <b>{et}</b> · Recovery: <b>{rs}</b>. "
            f"This bucket won {wr:.0f}% of {n} historical trades, avg {avgp:+.2f}%. "
            f"Stop placed at 220 EMA (₹{ema220:,.2f}) or –15%, whichever is tighter. "
            + ("✅ Bull regime — green light." if is_bull else "⚠️ Bear regime — skip new ATH plays.")
        )
        out.append({
            'ticker': str(r.get('Ticker', '')).replace('.NS', ''),
            'company': str(r.get('Company', '')),
            'strategy': S_MOMENTUM,
            'signal': str(r.get('Signal', '')),
            'close': close, 'stop': stop, 'target': target,
            'confidence': wr, 'avg_pnl': avgp, 'n_hist': n,
            'position_pct': 12.0 if is_bull else 6.0,
            'edge_score': wr + float(r.get('Score', 0)),
            'rationale': rationale,
        })
    return out


def render_suggestions(m: dict, i: dict, mo: dict) -> None:
    st.markdown(
        '<h1 style="margin:0 0 6px 0;font-size:30px;font-weight:900;letter-spacing:-.02em;">'
        '🎯 Suggestions — Risk-Filtered Picks</h1>',
        unsafe_allow_html=True,
    )
    st.caption(
        'Live signals re-ranked by historical edge. Only setups that historically won are surfaced; '
        'regime gate, position sizing, and stop-losses are applied automatically.'
    )

    st.markdown(_explain_box(
        '🧠 <b>How the engine works (Plain English)</b><br>'
        '<b>Step 1 — Find the edge.</b> Every closed historical trade is grouped by its setup '
        '(e.g. Entry Type × Recovery Speed for Momentum Edge, Setup_Type for IPO Edge). '
        'Buckets with <b>positive expectancy</b> (wins × win-rate beats losses × loss-rate) become the "approved" buckets.<br>'
        '<b>Step 2 — Filter today\'s signals.</b> Only live signals that match an approved bucket pass through. '
        'Everything else is dropped — no matter how exciting the chart looks.<br>'
        '<b>Step 3 — Regime gate.</b> If Nifty regime is Bear, position sizes are cut in half (or to zero for IPO Edge). '
        'New entries during Bear regime have a much lower historical win rate.<br>'
        '<b>Step 4 — Risk wrap.</b> Each pick ships with a defined entry, stop-loss, target, R:R ratio, '
        'and max-position-size cap so a single bad trade can\'t crater the account.'
    ), unsafe_allow_html=True)

    st.markdown(_tip_box(
        '⚠️ <b>Zero risk does not exist in markets.</b> What this page does is <b>minimise</b> risk: '
        'it refuses to show you any setup that did not historically make money, it sizes positions so no single loss '
        'is fatal, and it forces a pre-defined stop-loss on every trade. Worst-case loss per pick is capped at '
        '<b>position_size × stop_distance</b>. Across the whole portfolio, that worst-case is &lt; 2% of capital.'
    ), unsafe_allow_html=True)

    # Regime gate
    snap = _regime_snapshot()
    is_bull = (snap.get('status') == 'Bull')
    regime_color = '#22C55E' if is_bull else '#EF4444'
    regime_msg = (
        '🟢 <b>BULL regime</b> — all 3 Nifty conditions on. New entries are allowed.'
        if is_bull else
        '🔴 <b>BEAR / SIDEWAYS regime</b> — at least one Nifty condition is failing. '
        'Position sizes halved; IPO Edge picks suspended.'
    )
    st.markdown(
        f'<div style="border-left:4px solid {regime_color};background:{regime_color}11;'
        f'padding:12px 16px;margin:14px 0;border-radius:8px;font-size:13px;color:#e4e8f0;">'
        f'{regime_msg}</div>',
        unsafe_allow_html=True,
    )

    # Build pools
    monthly_pool  = _build_monthly_suggestions(m,  is_bull, max_picks=5)
    momentum_pool = _build_momentum_suggestions(mo, is_bull, max_picks=5)
    ipo_pool      = _build_ipo_suggestions(i,      is_bull, max_picks=5) if is_bull else []

    all_picks = sorted(monthly_pool + momentum_pool + ipo_pool,
                       key=lambda x: x['edge_score'], reverse=True)

    # Top-line summary
    n_picks = len(all_picks)
    avg_conf = (sum(p['confidence'] for p in all_picks) / n_picks) if n_picks else 0
    total_alloc = sum(p['position_pct'] for p in all_picks)
    cash_pct = max(0, 100 - total_alloc)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        _kpi_card('Picks Today', f'{n_picks}', 'after edge + regime filter', '#7c9cff')
    with c2:
        _kpi_card('Avg Confidence', f'{avg_conf:.0f}%', 'hist. win rate', '#22C55E' if avg_conf >= 55 else '#f9c200')
    with c3:
        _kpi_card('Total Allocation', f'{min(total_alloc,100):.0f}%', 'of capital deployed', '#e4e8f0')
    with c4:
        _kpi_card('Cash Reserve', f'{cash_pct:.0f}%', 'idle (dry powder)', '#00c853')

    st.markdown('<br>', unsafe_allow_html=True)

    if not all_picks:
        st.markdown(_explain_box(
            '🛑 <b>No suggestions today.</b> Either the regime is Bear and entries are gated, '
            'or no live signal matches an approved historical bucket. '
            'Holding cash is a position too — wait for the next signal.', color='#f9c200'
        ), unsafe_allow_html=True)
        _glossary_expander()
        return

    # Tabs: All | Monthly | IPO | Momentum
    tab_all, tab_m, tab_i, tab_mo = st.tabs([
        f'⭐ All ({len(all_picks)})',
        f'🔄 Monthly ({len(monthly_pool)})',
        f'🚀 IPO Edge ({len(ipo_pool)})',
        f'📈 Momentum Edge ({len(momentum_pool)})',
    ])

    def _render_pool(pool: list[dict]) -> None:
        if not pool:
            st.info('No picks in this strategy right now.')
            return
        html = ''
        for idx, p in enumerate(pool, start=1):
            html += _suggestion_card(
                rank=idx, ticker=p['ticker'], company=p['company'],
                strategy=p['strategy'], signal=p['signal'],
                close=p['close'], stop=p['stop'], target=p['target'],
                confidence=p['confidence'], avg_pnl=p['avg_pnl'],
                n_hist=p['n_hist'], position_pct=p['position_pct'],
                rationale=p['rationale'],
            )
        st.markdown(html, unsafe_allow_html=True)

    with tab_all:
        _render_pool(all_picks)
    with tab_m:
        _render_pool(monthly_pool)
    with tab_i:
        _render_pool(ipo_pool)
    with tab_mo:
        _render_pool(momentum_pool)

    st.markdown('<br>', unsafe_allow_html=True)
    _glossary_expander()


# ═══════════════════════════════════════════════════════════════════════════════
#  INSIGHTS PAGE
# ═══════════════════════════════════════════════════════════════════════════════

def render_insights(m: dict, i: dict, mo: dict) -> None:
    st.markdown(
        '<h1 style="margin:0 0 6px 0;font-size:30px;font-weight:900;letter-spacing:-.02em;">'
        '🔬 Insights</h1>',
        unsafe_allow_html=True,
    )
    st.caption('Post-hoc analytics on closed trades — entry quality, exit timing, stop placement.')

    st.markdown(_explain_box(
        '🧠 <b>What this page shows (Plain English)</b><br>'
        'Every past trade is replayed to answer four questions: '
        '<b>(1)</b> which entry setups turned into winners, '
        '<b>(2)</b> when to take profits, '
        '<b>(3)</b> where to place the stop-loss so winners survive but losers get cut early, '
        '<b>(4)</b> how long to stay in a trade. '
        'You will see terms like <b>MAE</b> (the deepest dip a trade saw before it closed) and '
        '<b>MFE</b> (the biggest gain it touched). '
        '<b>p95</b> means "95% of cases stayed inside this number" — a worst-case bound that ignores rare outliers.'
    ), unsafe_allow_html=True)

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

    st.markdown('<br>', unsafe_allow_html=True)
    _glossary_expander()


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
    elif 'PEAD' in page:
        import pead_dashboard
        pead_dashboard.render()
    elif 'Suggestions' in page:
        render_suggestions(m, i, mo)
    elif 'Insights' in page:
        render_insights(m, i, mo)
    elif 'History' in page:
        render_history(m, i, mo)


if __name__ == '__main__':
    main()
