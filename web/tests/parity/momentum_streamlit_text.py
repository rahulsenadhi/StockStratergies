"""Print the strings Streamlit's Momentum page builds from the current saved files, as JSON.

Run with cwd = project root (after precompute_ui_momentum.py). The Next.js parity test compares
these with its own mappers. The formatting lambdas below are copied from render_momentum's
_render_subset (master_dashboard.py ~7140-7175) and the past-trades table (~7470-7500); they are
test-only code. One deliberate difference: Streamlit prints a missing number as "nan%", the desk
shows "—", so a missing value maps to "—" here too. Ticker shows without ".NS" as in the desk.
"""
import json
import logging
import os
import sys

import pandas as pd

sys.path.insert(0, os.getcwd())  # run with cwd = project root
logging.disable(logging.WARNING)

import master_dashboard as md  # noqa: E402
from precompute_ui_momentum import _signals_frame  # noqa: E402

DASH = '—'
DISPLAY_COLS = [  # display_cols in render_momentum, minus Ticker/Company/Signal/Action
    'Close', 'Stop (₹)', 'Stop %', 'ATH (₹)', 'Dist ATH%', 'Entry Type', 'Chart Qual', 'Choppiness',
    'Recovery', '220 EMA', '52W High', 'vs High%', 'Vol Ratio', 'Score', 'Hist Win%', 'Hist Avg%',
]


def guard(fn):
    return lambda x: fn(x) if pd.notna(x) else DASH


def plain(x):
    return DASH if x is None or (isinstance(x, float) and pd.isna(x)) else str(x)


def setups(sigs: pd.DataFrame) -> list:
    d = sigs.copy()
    for c in ('Close', 'ATH (₹)', '220 EMA', '52W High', 'Stop (₹)'):
        d[c] = d[c].apply(guard(lambda x: f'₹{x:,.2f}'))
    d['Stop %'] = d['Stop %'].apply(guard(lambda x: f'{x:+.1f}%'))
    for c in ('Dist ATH%', 'vs High%'):
        d[c] = d[c].apply(guard(lambda x: f'{x:+.1f}%'))
    d['Vol Ratio'] = d['Vol Ratio'].apply(guard(lambda x: f'{x:.2f}×'))
    d['Hist Win%'] = d['Hist Win%'].apply(guard(lambda x: f'{x:.0f}%'))
    d['Hist Avg%'] = d['Hist Avg%'].apply(guard(lambda x: f'{x:+.1f}%'))
    badge = md._exit_badge(md._pick_rec('momentum_edge'))
    rows = []
    for (_, r), (_, raw) in zip(d.iterrows(), sigs.iterrows()):
        rows.append([str(raw['Ticker']).replace('.NS', ''), raw['Signal'], raw['Action'],
                     *[plain(r[c]) for c in DISPLAY_COLS], badge])
    return rows


def trades_table(trades: pd.DataFrame, limit: int = 15) -> list:
    ts = md._verify_past_trades(trades).copy()
    ts['Exit_Date'] = pd.to_datetime(ts['Exit_Date'], errors='coerce')
    view = ts.sort_values('Exit_Date', ascending=False).head(limit)
    rows = []
    for _, r in view.iterrows():
        prior, margin = r.get('Prior_52W_High'), r.get('Breakout_Margin_Pct')
        etype = {'52W_HIGH_FALLBACK': '52W high', 'ATH': 'All-time high'}.get(r['Entry_Type'], r['Entry_Type'])
        days = r.get('Recovery_Days')
        recovery = (f"{r['Recovery_Speed']} · {int(days)}d" if pd.notna(days) and days > 0
                    else str(r['Recovery_Speed']))
        rows.append([
            str(r['Ticker']).replace('.NS', ''),
            pd.to_datetime(r['Entry_Date']).strftime('%Y-%m-%d'),
            f"₹{r['Entry_Price']:,.2f}",
            f'₹{prior:,.2f}' if pd.notna(prior) else DASH,
            (f'+{margin:.2f}%' if margin >= 0 else f'{margin:.2f}%') if pd.notna(margin) else DASH,
            pd.to_datetime(r['Exit_Date']).strftime('%Y-%m-%d'),
            f"₹{r['Exit_Price']:,.2f}",
            f"{r['PnL_Pct']:+.2f}%",
            plain(r['Holding_Days']),
            r['Exit_Reason'],
            md._summarize_filter_detail(r['Filter_Detail']),
            etype,
            recovery,
        ])
    return rows


def health(mo: dict) -> dict:
    h = md._strategy_health(mo['trades'], mo['signals'])
    mx = md._equity_metrics(mo['equity'], 'Equity', 'Equity') if mo.get('equity') is not None else {}
    return {
        'values': [
            f"{mx['total_ret']:+.1f}%" if mx else DASH,
            f"{mx['max_dd']:.1f}%" if mx else DASH,
            f"{h['win_rate']:.0f}% of {h['n_trades']}",
            f"{h['avg_pnl']:+.2f}%",
            f"{h['median_hold']} days",
            f"{h['safe_20d_pct']:.0f}%",
        ],
        'medianSub': f"median {h['median_pnl']:+.2f}%",
    }


def counts(sigs: pd.DataFrame) -> dict:
    # n_bk ... n_fast as in render_momentum (master_dashboard.py ~6979-6995)
    return {
        'breakout': int((sigs['Signal'] == 'Breakout Today').sum()),
        'near': int((sigs['Signal'] == 'Near Breakout').sum()),
        'watch': int((sigs['Signal'] == 'Watch Zone').sum()),
        'ath': int((sigs['Entry Type'] == 'ATH').sum()),
        'clean': int((sigs['Chart Qual'] == 'Clean ✅').sum()),
        'fast': int(sigs['Recovery'].str.startswith('Fast').sum()),
    }


if __name__ == '__main__':
    mo = md.load_momentum()
    raw = mo['signals']
    print(json.dumps({
        'setups': setups(_signals_frame(raw)),
        'trades': trades_table(mo['trades']),
        'health': health(mo),
        'counts': counts(raw),
    }, ensure_ascii=False))
