"""
Nifty 50 Momentum Rotation — Visual Dashboard
Run: streamlit run dashboard_visual.py
"""

import os
import sys
import subprocess
from datetime import datetime, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Nifty Momentum Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
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

.top-card {
    background: #121623; border-radius: 11px; padding: 13px 14px;
    border: 1px solid #242d47; height: 155px; position: relative;
}
.tc-rank  { font-size: 0.62rem; color: #6e7a90; text-transform: uppercase;
            letter-spacing: 0.08em; }
.tc-co    { font-size: 0.82rem; font-weight: 600; color: #dde4f0;
            margin: 3px 0 1px; line-height: 1.2; }
.tc-tk    { font-size: 0.66rem; color: #6e7a90; margin-bottom: 5px; }
.tc-rs    { font-size: 1.25rem; font-weight: 700; line-height: 1; }
.tc-sub   { font-size: 0.65rem; color: #6e7a90; margin-top: 1px; }
.tc-price { font-size: 0.73rem; color: #8a96aa; margin-top: 5px; }
.tc-sig   { font-size: 0.62rem; padding: 2px 7px; border-radius: 4px;
            margin-top: 6px; display: inline-block; font-weight: 500; }

.sec-hdr  { font-size: 0.7rem; font-weight: 700; color: #6e7a90;
            text-transform: uppercase; letter-spacing: 0.08em;
            padding-bottom: 6px; border-bottom: 1px solid #242d47;
            margin-bottom: 10px; }

.rebal-card { background: #121623; border-radius: 8px; padding: 11px 14px;
              margin-bottom: 7px; border: 1px solid #242d47; }
</style>""", unsafe_allow_html=True)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Helpers ───────────────────────────────────────────────────────────────────
def rs_color(rs):
    if pd.isna(rs):  return '#6e7a90'
    if rs > 3:       return '#00c853'
    if rs >= 1:      return '#f9c200'
    if rs >= 0:      return '#ff8c00'
    return '#ff3d3d'

def next_rebalance():
    today = datetime.now().date()
    m, y  = today.month, today.year
    first = today.replace(year=y + 1, month=1, day=1) if m == 12 \
            else today.replace(month=m + 1, day=1)
    last  = first - timedelta(days=1)
    while last.weekday() >= 5:
        last -= timedelta(days=1)
    return last

def clean_tickers(val):
    if pd.isna(val) or str(val).strip() in ('', 'nan', 'None'):
        return '—'
    return str(val).replace('.NS', '').strip()

def write_memory_log():
    """Append a timestamped snapshot to MEMORY.md after each refresh."""
    rankings_path = os.path.join(BASE_DIR, "live_rankings.csv")
    backtest_path = os.path.join(BASE_DIR, "backtest_results.csv")
    memory_path   = os.path.join(BASE_DIR, "MEMORY.md")

    if not os.path.exists(rankings_path):
        return

    df_r = pd.read_csv(rankings_path)
    beating = int((df_r['RS_Score'] > 0).sum())
    lagging = int((df_r['RS_Score'] < 0).sum())
    bench   = float(df_r['Benchmark_Return_%'].iloc[0])
    top5    = df_r[df_r['RS_Score'] > 0].head(5)

    now = datetime.now().strftime("%d %b %Y, %H:%M")

    lines = [f"\n## {now} — Data Refresh\n\n"]
    lines.append(f"**Market (NiftyBees) this month:** {bench:+.2f}%  \n")
    lines.append(f"**Stocks beating market:** {beating} of 50 &nbsp;|&nbsp; **Lagging:** {lagging}\n\n")

    lines.append("### Top 5 Picks\n")
    lines.append("| # | Company | Ticker | Price | Ahead of Market | Signal |\n")
    lines.append("|---|---------|--------|------:|----------------:|--------|\n")
    for _, row in top5.iterrows():
        ticker  = row['Ticker'].replace('.NS', '')
        signal  = str(row['Signal']).split(' ', 1)[-1]
        lines.append(
            f"| {int(row['Rank'])} | {row['Company']} | {ticker} | "
            f"₹{row['Current_Price']:,.2f} | {row['RS_Score']:+.2f}% | {signal} |\n"
        )

    if os.path.exists(backtest_path):
        bt = pd.read_csv(backtest_path, parse_dates=['Date']).sort_values('Date')
        pv0, pvf = bt['Portfolio_Value'].iloc[0], bt['Portfolio_Value'].iloc[-1]
        bv0, bvf = bt['Benchmark_Value'].iloc[0], bt['Benchmark_Value'].iloc[-1]
        strat_ret = (pvf / pv0 - 1) * 100
        bench_ret = (bvf / bv0 - 1) * 100
        factor    = (pvf / pv0) / (bvf / bv0)
        n_years   = max((bt['Date'].iloc[-1] - bt['Date'].iloc[0]).days / 365.25, 0.01)
        cagr_s    = ((pvf / pv0) ** (1 / n_years) - 1) * 100
        cagr_b    = ((bvf / bv0) ** (1 / n_years) - 1) * 100
        start_str = bt['Date'].iloc[0].strftime('%b %Y')
        end_str   = bt['Date'].iloc[-1].strftime('%b %Y')
        months    = len(bt) - 1
        lines.append(f"\n### Strategy Performance ({start_str} → {end_str} · {months} months)\n")
        lines.append(f"- Your money grew: **{strat_ret:+.1f}%** &nbsp;(₹{pv0:,.0f} → ₹{pvf:,.0f})  \n")
        lines.append(f"- Market (NiftyBees) grew: **{bench_ret:+.1f}%**  \n")
        lines.append(f"- Outgrew market by: **{factor:.2f}×**  \n")
        lines.append(f"- Extra return per year: **{cagr_s - cagr_b:+.1f}%** above NiftyBees\n")

    lines.append("\n---\n")

    # Prepend new entry after the header block
    if os.path.exists(memory_path):
        with open(memory_path, 'r', encoding='utf-8') as f:
            existing = f.read()
        # Insert after the first "---\n" separator (end of header)
        split_marker = "---\n"
        idx = existing.find(split_marker)
        if idx != -1:
            new_content = existing[:idx + len(split_marker)] + ''.join(lines) + existing[idx + len(split_marker):]
        else:
            new_content = existing + ''.join(lines)
    else:
        header = "# Nifty 50 Momentum Strategy — Activity Log\n\nNewest entries at the top.\n\n---\n"
        new_content = header + ''.join(lines)

    with open(memory_path, 'w', encoding='utf-8') as f:
        f.write(new_content)

# ── Data loaders ──────────────────────────────────────────────────────────────
@st.cache_data(ttl=60)
def load_rankings():
    p = os.path.join(BASE_DIR, "live_rankings.csv")
    return pd.read_csv(p) if os.path.exists(p) else pd.DataFrame()

@st.cache_data(ttl=300)
def load_backtest():
    p = os.path.join(BASE_DIR, "backtest_results.csv")
    return pd.read_csv(p, parse_dates=['Date']) if os.path.exists(p) else pd.DataFrame()

@st.cache_data(ttl=300)
def load_rebalance():
    p = os.path.join(BASE_DIR, "rebalance_log.csv")
    return pd.read_csv(p, parse_dates=['Date']) if os.path.exists(p) else pd.DataFrame()

# ── Header ────────────────────────────────────────────────────────────────────
hc1, hc2, hc3 = st.columns([5, 2.5, 0.8])
with hc1:
    st.markdown("### 📈 &nbsp;Nifty 50 — Momentum Rotation Dashboard")
with hc2:
    rankings_path = os.path.join(BASE_DIR, "live_rankings.csv")
    if os.path.exists(rankings_path):
        mtime  = datetime.fromtimestamp(os.path.getmtime(rankings_path))
        ts_str = mtime.strftime("Last updated: %d %b %Y, %H:%M")
    else:
        ts_str = "No data yet"
    st.markdown(
        f"<p style='padding-top:13px; color:#6e7a90; font-size:0.78rem;'>{ts_str}</p>",
        unsafe_allow_html=True,
    )
with hc3:
    do_refresh = st.button("🔄 Refresh", width='stretch')

if do_refresh:
    with st.spinner("Fetching live prices from Yahoo Finance…"):
        subprocess.run(
            [sys.executable, os.path.join(BASE_DIR, "step3_dashboard.py")],
            capture_output=True, text=True, cwd=BASE_DIR,
        )
    st.cache_data.clear()
    write_memory_log()
    st.rerun()

# ── Load data ─────────────────────────────────────────────────────────────────
df        = load_rankings()
backtest  = load_backtest()
rebalance = load_rebalance()

if df.empty:
    st.warning("⚠️  No `live_rankings.csv` found. Click **Refresh** to fetch live data.")
    st.stop()

beating    = int((df['RS_Score'] > 0).sum())
lagging    = int((df['RS_Score'] < 0).sum())
bench_ret  = float(df['Benchmark_Return_%'].iloc[0])
rebal_date = next_rebalance()
days_left  = (rebal_date - datetime.now().date()).days
top5       = df[df['RS_Score'] > 0].head(5)

# ── Today's Snapshot ─────────────────────────────────────────────────────────
st.markdown('<div class="sec-hdr">Today\'s Snapshot</div>', unsafe_allow_html=True)
mc = st.columns(5)
stats = [
    ("Market moved this month",  f"{bench_ret:+.2f}%",          "#00c853" if bench_ret >= 0 else "#ff3d3d",
     "NiftyBees ETF return"),
    ("Stocks beating the market", str(beating),                  "#00c853",
     "outperforming NiftyBees"),
    ("Stocks lagging the market", str(lagging),                  "#ff3d3d",
     "underperforming NiftyBees"),
    ("Next stock swap date",      rebal_date.strftime("%d %b %Y"), "#7c9cff",
     "when we review the top 5"),
    ("Days until next swap",      str(days_left),                "#7c9cff",
     "end-of-month review"),
]
for col, (label, val, color, sub) in zip(mc, stats):
    col.markdown(
        f'<div class="metric-card">'
        f'<div class="mv" style="color:{color};">{val}</div>'
        f'<div class="ml">{label}</div>'
        f'<div class="ml2">{sub}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

st.markdown("<div style='margin:16px 0'></div>", unsafe_allow_html=True)

# ── Top 5 picks ───────────────────────────────────────────────────────────────
st.markdown(
    '<div class="sec-hdr">Top 5 Stocks to Hold This Month &nbsp;—&nbsp; ₹10,000 in Each</div>',
    unsafe_allow_html=True,
)

pick_cols = st.columns(5)
for i, (_, row) in enumerate(top5.iterrows()):
    color     = rs_color(row['RS_Score'])
    price     = row['Current_Price']
    shares    = int(10_000 // price) if price > 0 else 0
    signal    = str(row['Signal'])
    sig_clean = signal.split(' ', 1)[-1] if len(signal) > 2 else signal
    rs        = row['RS_Score']

    pick_cols[i].markdown(
        f'<div class="top-card" style="border-top: 3px solid {color};">'
        f'<div class="tc-rank">Rank #{int(row["Rank"])}</div>'
        f'<div class="tc-co">{row["Company"]}</div>'
        f'<div class="tc-tk">{row["Ticker"].replace(".NS","")}</div>'
        f'<div class="tc-rs" style="color:{color};">{rs:+.2f}%</div>'
        f'<div class="tc-sub">ahead of market this month</div>'
        f'<div class="tc-price">₹{price:,.2f} &nbsp;·&nbsp; {shares} shares</div>'
        f'<div><span class="tc-sig" style="color:{color};'
        f' border:1px solid {color}; background:rgba(0,0,0,0.35);">{sig_clean}</span></div>'
        f'</div>',
        unsafe_allow_html=True,
    )

st.markdown("<div style='margin:16px 0'></div>", unsafe_allow_html=True)

# ── Bar chart  +  Rankings table ─────────────────────────────────────────────
bar_col, tbl_col = st.columns([1.05, 0.95], gap="medium")

with bar_col:
    st.markdown(
        '<div class="sec-hdr">How Each Stock Is Doing vs the Market This Month</div>',
        unsafe_allow_html=True,
    )
    bdf    = df.sort_values('RS_Score', ascending=True)
    colors = [rs_color(x) for x in bdf['RS_Score']]

    fig_bar = go.Figure(go.Bar(
        y=bdf['Ticker'].str.replace('.NS', '', regex=False),
        x=bdf['RS_Score'],
        orientation='h',
        marker=dict(color=colors, line=dict(width=0)),
        text=[f"{x:+.1f}%" for x in bdf['RS_Score']],
        textposition='outside',
        textfont=dict(size=9, color='#6e7a90'),
        cliponaxis=False,
        customdata=bdf['Company'],
        hovertemplate=(
            '<b>%{customdata}</b><br>'
            'Ahead of market by: %{x:+.2f}%<extra></extra>'
        ),
    ))
    fig_bar.add_vline(x=0, line_color='#3a4460', line_width=1.5, line_dash='dot')
    fig_bar.add_annotation(
        x=0, y=1.01, xref='x', yref='paper',
        text='← Lagging market  |  Beating market →',
        showarrow=False, font=dict(size=9, color='#6e7a90'),
        xanchor='center',
    )
    fig_bar.update_layout(
        height=850, margin=dict(l=0, r=52, t=20, b=4),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(
            gridcolor='#242d47', gridwidth=0.5, zeroline=False,
            tickfont=dict(color='#6e7a90', size=9), ticksuffix='%',
        ),
        yaxis=dict(
            gridcolor='rgba(0,0,0,0)',
            tickfont=dict(color='#bcc6d8', size=10),
        ),
        showlegend=False,
    )
    st.plotly_chart(fig_bar, width='stretch', config={'displayModeBar': False})

with tbl_col:
    st.markdown('<div class="sec-hdr">All 50 Stocks — Ranked Best to Worst</div>', unsafe_allow_html=True)

    tdf      = df.copy()
    t_colors = [rs_color(x) for x in tdf['RS_Score']]
    row_bg   = []
    for c in t_colors:
        if c == '#00c853':   row_bg.append('rgba(0,200,83,0.07)')
        elif c == '#f9c200': row_bg.append('rgba(249,194,0,0.07)')
        elif c == '#ff8c00': row_bg.append('rgba(255,140,0,0.07)')
        else:                row_bg.append('rgba(255,61,61,0.04)')

    fig_tbl = go.Figure(data=[go.Table(
        columnwidth=[28, 58, 128, 72, 65, 75, 85],
        header=dict(
            values=[
                '<b>#</b>', '<b>Ticker</b>', '<b>Company</b>',
                '<b>Price ₹</b>', '<b>Month Return</b>',
                '<b>vs Market</b>', '<b>Signal</b>',
            ],
            fill_color='#161b2b',
            align=['center', 'left', 'left', 'right', 'right', 'right', 'center'],
            font=dict(color='#6e7a90', size=11),
            height=28,
            line_color='#242d47',
        ),
        cells=dict(
            values=[
                tdf['Rank'].astype(int),
                tdf['Ticker'].str.replace('.NS', '', regex=False),
                tdf['Company'],
                tdf['Current_Price'].apply(lambda x: f"{x:,.2f}"),
                tdf['Return_%'].apply(lambda x: f"{x:+.2f}%"),
                tdf['RS_Score'].apply(lambda x: f"{x:+.2f}%"),
                tdf['Signal'],
            ],
            fill_color=[row_bg] * 7,
            align=['center', 'left', 'left', 'right', 'right', 'right', 'center'],
            font=dict(
                color=[
                    ['#bcc6d8'] * len(tdf),
                    ['#bcc6d8'] * len(tdf),
                    ['#8a96aa'] * len(tdf),
                    ['#bcc6d8'] * len(tdf),
                    ['#bcc6d8'] * len(tdf),
                    t_colors,
                    t_colors,
                ],
                size=10,
            ),
            height=21,
            line_color='#242d47',
        ),
    )])
    fig_tbl.update_layout(
        height=850, margin=dict(l=0, r=0, t=4, b=4),
        paper_bgcolor='rgba(0,0,0,0)',
    )
    st.plotly_chart(fig_tbl, width='stretch', config={'displayModeBar': False})

# ── Performance section ───────────────────────────────────────────────────────
if not backtest.empty:
    bt  = backtest.sort_values('Date').copy()
    pv0 = bt['Portfolio_Value'].iloc[0]
    bv0 = bt['Benchmark_Value'].iloc[0]
    bt['Strat'] = bt['Portfolio_Value'] / pv0 * 100
    bt['Bench'] = bt['Benchmark_Value'] / bv0 * 100

    # Key numbers
    n_months      = len(bt) - 1                         # months of active trading
    s_final       = bt['Strat'].iloc[-1]
    b_final       = bt['Bench'].iloc[-1]
    strat_total   = s_final - 100                        # e.g. +60.9 %
    bench_total   = b_final - 100                        # e.g. +29.8 %
    outgrowth     = (s_final / 100) / (b_final / 100)   # e.g. 1.24x
    n_years       = max((bt['Date'].iloc[-1] - bt['Date'].iloc[0]).days / 365.25, 0.01)
    yearly_strat  = ((s_final / 100) ** (1 / n_years) - 1) * 100
    yearly_bench  = ((b_final / 100) ** (1 / n_years) - 1) * 100
    yearly_edge   = yearly_strat - yearly_bench
    start_str     = bt['Date'].iloc[0].strftime('%b %Y')
    end_str       = bt['Date'].iloc[-1].strftime('%b %Y')

    st.markdown(
        f'<div class="sec-hdr" style="margin-top:6px;">'
        f'How the Strategy Has Grown &nbsp;—&nbsp; {start_str} to {end_str} ({n_months} months)</div>',
        unsafe_allow_html=True,
    )

    # Chart
    fig_perf = go.Figure()
    fig_perf.add_trace(go.Scatter(
        x=bt['Date'], y=bt['Strat'], name='This Strategy',
        line=dict(color='#00c853', width=2.5),
        hovertemplate='%{x|%b %Y} &nbsp; Strategy: %{y:.1f}<extra></extra>',
    ))
    fig_perf.add_trace(go.Scatter(
        x=bt['Date'], y=bt['Bench'], name='NiftyBees (Market)',
        line=dict(color='#7c9cff', width=2, dash='dot'),
        hovertemplate='%{x|%b %Y} &nbsp; Market: %{y:.1f}<extra></extra>',
    ))
    fig_perf.add_hline(y=100, line_color='#3a4460', line_width=1, line_dash='dash')
    fig_perf.update_layout(
        height=280, margin=dict(l=0, r=0, t=6, b=6),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(12,15,22,0.7)',
        xaxis=dict(gridcolor='#242d47', gridwidth=0.5, zeroline=False,
                   tickfont=dict(color='#6e7a90', size=10)),
        yaxis=dict(gridcolor='#242d47', gridwidth=0.5, zeroline=False,
                   tickfont=dict(color='#6e7a90', size=10),
                   title='Growth (started at 100)',
                   title_font=dict(color='#6e7a90', size=10)),
        legend=dict(bgcolor='rgba(0,0,0,0)', font=dict(color='#bcc6d8', size=12),
                    orientation='h', x=0, y=1.1),
        hovermode='x unified',
    )

    st.plotly_chart(fig_perf, width='stretch', config={'displayModeBar': False})

    # Five plain-English summary cards below the chart
    st.markdown("<div style='margin:10px 0 4px'></div>", unsafe_allow_html=True)
    c1, c2, c3, c4, c5 = st.columns(5)
    perf_cards = [
        ("Months running",           f"{n_months}",              "#7c9cff",
         f"{start_str} → {end_str}"),
        ("Your money grew by",        f"{strat_total:+.1f}%",    "#00c853",
         f"₹50k → ₹{pv0 * s_final/100:,.0f}"),
        ("Market (NiftyBees) grew by", f"{bench_total:+.1f}%",   "#7c9cff",
         "same period"),
        ("Outgrew NiftyBees by",      f"{outgrowth:.2f}×",       "#00c853" if outgrowth > 1 else "#ff3d3d",
         "strategy ÷ market growth"),
        ("Extra return per year",     f"{yearly_edge:+.1f}%",    "#00c853" if yearly_edge > 0 else "#ff3d3d",
         "above NiftyBees annually"),
    ]
    for col, (label, val, color, sub) in zip([c1, c2, c3, c4, c5], perf_cards):
        col.markdown(
            f'<div class="metric-card">'
            f'<div class="mv" style="color:{color};">{val}</div>'
            f'<div class="ml">{label}</div>'
            f'<div class="ml2">{sub}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

# ── What Changed Each Month ───────────────────────────────────────────────────
if not rebalance.empty:
    st.markdown(
        '<div class="sec-hdr" style="margin-top:14px;">What Changed Each Month</div>',
        unsafe_allow_html=True,
    )
    st.caption("Every month, on the last trading day, we swap out any stock that has fallen behind the market and replace it with the strongest new performer. Hold the top 5, drop the laggards.")
    recent = rebalance.sort_values('Date', ascending=False).head(6)
    rc1, rc2 = st.columns(2)
    for i, (_, row) in enumerate(recent.iterrows()):
        date_str = row['Date'].strftime('%d %b %Y') if pd.notna(row['Date']) else '—'
        val_str  = (f"₹{row['Portfolio_Value']:,.0f}"
                    if pd.notna(row.get('Portfolio_Value')) else '—')
        added   = clean_tickers(row.get('Stocks_Bought', ''))
        removed = clean_tickers(row.get('Stocks_Sold', ''))
        kept    = clean_tickers(row.get('Stocks_Held', ''))

        card = (
            f'<div class="rebal-card">'
            f'<div style="display:flex;justify-content:space-between;margin-bottom:7px;">'
            f'<span style="color:#dde4f0;font-weight:600;font-size:0.84rem;">{date_str}</span>'
            f'<span style="color:#00c853;font-size:0.8rem;">Portfolio: {val_str}</span>'
            f'</div>'
            f'<div style="font-size:0.73rem;display:flex;flex-direction:column;gap:3px;">'
            f'<span><span style="color:#00c853;">▲ Added &nbsp;&nbsp;</span>'
            f'<span style="color:#7e8fa8;">{added}</span></span>'
            f'<span><span style="color:#ff3d3d;">▼ Removed</span>&nbsp;'
            f'<span style="color:#7e8fa8;">{removed}</span></span>'
            f'<span><span style="color:#f9c200;">● Kept &nbsp;&nbsp;&nbsp;</span>'
            f'<span style="color:#7e8fa8;">{kept}</span></span>'
            f'</div></div>'
        )
        (rc1 if i % 2 == 0 else rc2).markdown(card, unsafe_allow_html=True)

# ── Glossary ──────────────────────────────────────────────────────────────────
st.markdown("<div style='margin-top:24px'></div>", unsafe_allow_html=True)
with st.expander("📖 What do these terms mean? — Plain-English Glossary"):
    st.markdown("""
**Relative Strength (RS) Score** — How much a stock has gained or lost *compared to the Nifty 50 average* this month.
A score of +5% means the stock beat the market by 5 percentage points. Negative = lagging behind.

**NiftyBees (Benchmark)** — An ETF that simply tracks the Nifty 50 index. We use it as the "market average"
to measure whether our strategy is beating a basic "just buy the index" approach.

**Rebalancing** — Swapping stocks once a month. We sell any stock that has fallen behind and buy the new top performer.
This keeps the portfolio always holding the 5 strongest Nifty 50 stocks.

**CAGR (Compound Annual Growth Rate)** — The average yearly growth rate if returns were compounded continuously.
Example: 15% CAGR means your money roughly doubles every 5 years.

**Outgrowth Multiple** — How many times more your money grew vs just holding NiftyBees.
A value of 1.5× means the strategy grew 50% more than the benchmark over the same period.

**Signal badges** — 🟢 Strong Buy = stock is well ahead of the market · 🟡 Moderate = slightly ahead ·
🟠 Neutral = roughly at market · 🔴 Lagging = below market average.

**Month Return %** — How much the stock's price changed this calendar month (not annualised).

**vs Market %** — The RS Score: same as Month Return minus the Nifty 50 average return this month.

**Top 5 picks** — The 5 Nifty 50 stocks with the highest RS Score right now. These are the stocks the strategy currently holds.
We invest ₹10,000 in each (₹50,000 total) and review every month-end.
    """)

