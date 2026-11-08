"""Print the strings Streamlit's IPO page builds from the current saved files, as JSON.

Run with cwd = project root (after precompute_ui_ipo.py). The Next.js parity test compares
these with its own mappers. The formatting lambdas below are copied from render_ipo's trade
history (master_dashboard.py ~6733-6762) and pills (~6650-6670); they are test-only code.
Two deliberate differences: Streamlit prints a missing number as "nan", the desk shows "—",
so a missing value maps to "—" here too; and rows use the desk's order (newest exit first,
open trades last, as precompute_ui_ipo.py sorts) where Streamlit shows file order.
Ticker shows without ".NS" as in the desk.
"""
import json
import logging
import os
import sys

import pandas as pd

sys.path.insert(0, os.getcwd())  # run with cwd = project root
logging.disable(logging.WARNING)

import master_dashboard as md  # noqa: E402
from precompute_ui_ipo import _extra_columns, _sorted  # noqa: E402

DASH = '—'


def guard(fn):
    return lambda x: fn(x) if pd.notna(x) else DASH


def plain(x):
    return DASH if x is None or (isinstance(x, float) and pd.isna(x)) else str(x)


def trade_rows(trades: pd.DataFrame, limit: int = 15) -> list:
    extra = _extra_columns(trades)
    hold = 'Holding_Days' if 'Holding_Days' in trades.columns else 'Hold_Days'
    t = _sorted(trades).head(limit)
    rows = []
    for _, r in t.iterrows():
        row = [
            str(r['Ticker']).replace('.NS', ''),
            plain(pd.to_datetime(r['Entry_Date'], errors='coerce').strftime('%Y-%m-%d')
                  if pd.notna(pd.to_datetime(r['Entry_Date'], errors='coerce')) else None),
            guard(lambda x: f'₹{x:,.2f}')(r['Entry_Price']),
            plain(pd.to_datetime(r['Exit_Date'], errors='coerce').strftime('%Y-%m-%d')
                  if pd.notna(pd.to_datetime(r['Exit_Date'], errors='coerce')) else None),
            guard(lambda x: f'₹{x:,.2f}')(r['Exit_Price']),
            guard(lambda x: f'{x:+.2f}%')(r['PnL_Pct']),
            plain(r[hold]),
            plain(r['Exit_Reason']),
            plain(r['Result']),
        ]
        for c in extra:
            v = r[c]
            if c == 'Partial_Booked':  # render_ipo ~6746-6749
                v = {'true': 'Yes', 'false': 'No'}.get(str(v).strip().lower(), DASH)
            elif c == 'Entry_Stage':   # render_ipo ~6751
                v = str(v).split('—')[-1].strip()
            row.append(plain(v))
        rows.append(row)
    return rows


def pills(i: dict) -> dict:
    # Pill values as render_ipo ~6650-6670, with the desk's plain-word labels and subs.
    eq, trades, sigs = i.get('equity'), i.get('trades'), i.get('signals')
    mx = md._equity_metrics(eq, 'Portfolio_Value', 'Portfolio_Value') if eq is not None else {}
    sigs = sigs if sigs is not None else pd.DataFrame()
    n_bk = int((sigs['Signal'] == 'Live Breakout').sum()) if not sigs.empty else 0
    stage = sigs['Stage'] if not sigs.empty and 'Stage' in sigs.columns else pd.Series(dtype=object)
    n_s3, n_s2, n_s1, n_it = (int((stage == s).sum()) for s in ('Stage 3', 'Stage 2', 'Stage 1', 'In Trade'))
    wr = f"{(trades['Result'] == 'Win').mean() * 100:.0f}%" if trades is not None and len(trades) else DASH
    return {
        'values': [
            f"{mx['total_ret']:+.1f}%" if mx else DASH,
            f"{mx['max_dd']:.1f}%" if mx else DASH,
            wr, str(n_s3), str(n_it),
        ],
        'subs': [None, None, f'{len(trades)} trades', f'Recovering: {n_s2} · Building: {n_s1}',
                 f'Live breakout signals: {n_bk}'],
    }


if __name__ == '__main__':
    ipo = md.load_ipo()
    print(json.dumps({'trades': trade_rows(ipo['trades']), 'pills': pills(ipo)}, ensure_ascii=False))
