# precompute_ui_monthly.py
"""Save the Monthly stock rotation page's data for the Next.js Research Desk (web/).

Calls the same master_dashboard.py functions Streamlit's render_monthly uses, so both
apps show the same numbers. No formulas live here — this only collects and saves.

Run:  python precompute_ui_monthly.py
Output (project root):  ui_monthly.json   (schema version 1)
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

import master_dashboard as md
from precompute_ui_home import _clean, write_snapshot

BASE_DIR = Path(__file__).resolve().parent
OUT = BASE_DIR / 'ui_monthly.json'
MONTHLY_VERSION = 1
CHART_WINDOWS = ('1Y', '3Y', 'All')
CLOSE_SESSIONS = 126      # render_monthly shows the last 126 closes
REBALANCE_ROWS = 12       # ...and the latest 12 rebalances


def _benchmark(eq: pd.DataFrame) -> tuple[float, float]:
    """render_monthly's inline Nifty total return and CAGR (0.0 when the column is absent)."""
    if 'Benchmark_Value' not in eq.columns:
        return 0.0, 0.0
    bv = eq['Benchmark_Value'].dropna()
    b_ret = (bv.iloc[-1] / bv.iloc[0] - 1) * 100
    b_yrs = (bv.index[-1] - bv.index[0]).days / 365.25
    b_cagr = ((bv.iloc[-1] / bv.iloc[0]) ** (1 / max(b_yrs, 0.01)) - 1) * 100
    return b_ret, b_cagr


def _summary(eq: pd.DataFrame, reb) -> dict | None:
    mx = md._equity_metrics(eq, 'Portfolio_Value', 'Portfolio_Value')
    if not mx:
        return None
    b_ret, b_cagr = _benchmark(eq)
    return {'cagr': mx['cagr'], 'total_ret': mx['total_ret'], 'max_dd': mx['max_dd'],
            'start': mx['start'], 'end': mx['end'], 'bench_ret': b_ret, 'bench_cagr': b_cagr,
            'alpha': mx['cagr'] - b_cagr,
            'n_months': len(reb) if reb is not None and not reb.empty else None}


def _chart(eq: pd.DataFrame, colour: str) -> dict:
    out = {}
    for window in CHART_WINDOWS:
        shown = md._monthly_period_slice(eq, window)
        fig = md.chart_equity(shown, 'Portfolio_Value', md.S_MONTHLY, colour, 'Benchmark_Value')
        out[window] = [{
            'name': t.name, 'colour': t.line.color, 'dash': t.line.dash == 'dot',
            'points': [[pd.Timestamp(x).strftime('%Y-%m-%d'), float(y)] for x, y in zip(t.x, t.y)],
        } for t in fig.data]
    return out


def _ranking(ranks: pd.DataFrame) -> list[dict]:
    rows = []
    for _, r in ranks.sort_values('Rank', kind='stable').iterrows():
        bench = pd.to_numeric(r.get('Benchmark_Return_%'), errors='coerce')
        rows.append({
            'rank': int(r['Rank']), 'ticker': str(r['Ticker']),
            'symbol': str(r['Ticker']).replace('.NS', ''), 'company': r['Company'],
            'price': float(r['Current_Price']), 'month_ret': float(r['Return_%']),
            'bench_ret': None if pd.isna(bench) else float(bench),
            'rs': float(r['RS_Score']), 'label': md._monthly_label(r['Signal']),
        })
    return rows


def _filters(ranks: pd.DataFrame) -> dict:
    ordered = ranks.sort_values('Rank', kind='stable')
    return {f: [str(t).replace('.NS', '') for t in md._monthly_filter(ordered, f)['Ticker']]
            for f in md._MONTHLY_FILTERS}


def _closes(ranks: pd.DataFrame) -> dict:
    out = {}
    for ticker in ranks['Ticker'].astype(str):
        close = md._monthly_close_history(ticker)
        if close is None or close.empty:
            continue
        close = close.iloc[-CLOSE_SESSIONS:]
        out[ticker.replace('.NS', '')] = {
            'saved_to': f'{close.index[-1]:%d %b %Y}',
            'points': [[pd.Timestamp(x).strftime('%Y-%m-%d'), float(y)] for x, y in close.items()],
        }
    return out


def _rebalances(reb) -> dict:
    if reb is None or reb.empty:
        return {'total': 0, 'rows': []}
    rows = [{'date': str(r['Date'])[:10], 'top5': md._monthly_tickers(r['Top5_Stocks']),
             'bought': md._monthly_tickers(r['Stocks_Bought']),
             'sold': md._monthly_tickers(r['Stocks_Sold']), 'value': float(r['Portfolio_Value'])}
            for _, r in reb.tail(REBALANCE_ROWS).iloc[::-1].iterrows()]
    return {'total': len(reb), 'rows': rows}


def _checks() -> list[dict]:
    out = []
    for title, status, note in md.MONTHLY_CHECKS:
        label, tone = md.ui.CHECK_STATUS[status]
        out.append({'title': title, 'label': label, 'tone': tone, 'note': note})
    return out


def build_ui_monthly(m: dict) -> dict:
    colour = md.THEME[md.S_MONTHLY]['color']
    eq = m.get('equity')
    ranks = m.get('rankings', pd.DataFrame())
    reb = m.get('rebalance', pd.DataFrame())
    has_ranks = not ranks.empty
    summary = _summary(eq, reb) if eq is not None else None
    return _clean({
        'version': MONTHLY_VERSION,
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'colour': colour,
        'summary': summary,
        'chart': _chart(eq, colour) if summary else None,
        'ranking': _ranking(ranks) if has_ranks else [],
        'filters': _filters(ranks) if has_ranks else {f: [] for f in md._MONTHLY_FILTERS},
        'default_symbol': str(ranks.iloc[0]['Ticker']).replace('.NS', '') if has_ranks else None,
        'top5': [str(t).replace('.NS', '') for t in ranks.sort_values('Rank').head(5)['Ticker']]
                if has_ranks else [],
        'closes': _closes(ranks) if has_ranks else {},
        'rebalances': _rebalances(reb),
        'checks': _checks(),
        'exit_rec': md._pick_rec('monthly_rotation'),
    })


def main() -> None:
    snapshot = build_ui_monthly(md.load_monthly())
    write_snapshot(snapshot, OUT)
    print(f'wrote {OUT.name}: {len(snapshot["ranking"])} ranked')


if __name__ == '__main__':
    main()
