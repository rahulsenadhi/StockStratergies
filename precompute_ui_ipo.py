# precompute_ui_ipo.py
"""Save the IPO page's data for the Next.js Research Desk (web/).

Calls the same master_dashboard.py functions Streamlit's render_ipo uses, so both apps
show the same numbers. No formulas live here. Rules copied from render_ipo, each with a
comment naming its source line: the win-rate fallback, the stage and signal counts, and
the rule that drops extra trade columns holding a single value. Trades are saved newest
exit first with open trades (no exit date) last; Streamlit shows them in file order.
The protected-file checksum on master_dashboard.py is the guard against these drifting.

Run:  python precompute_ui_ipo.py
Output (project root):  ui_ipo.json   (schema version 1)
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

import master_dashboard as md
from precompute_ui_home import _clean, _traces, write_snapshot

BASE_DIR = Path(__file__).resolve().parent
OUT = BASE_DIR / 'ui_ipo.json'
IPO_VERSION = 1
EXTRA_COLUMNS = ('Entry_Stage', 'Setup_Type', 'Partial_Booked', 'Liquidity_Status', 'Promoter_Backed')

SIGNAL_COLUMNS = {
    'company': 'Company', 'signal': 'Signal', 'stage': 'Stage', 'setup': 'Setup',
    'close': 'Close', 'bk_level': 'Bk Level', 'vs_bk': 'vs Bk%', 'vol_ratio': 'Vol Ratio',
    'ipo_day_val': 'IPO Day Val', 'liquidity': 'Liquidity', 'promoter': 'Promoter',
    'listing_pe': 'Listing PE', 'age_days': 'Age (d)', 'score': 'Score',
    'hist_win': 'Hist Win%', 'hist_avg': 'Hist Avg%',
}


def _symbol(ticker) -> str:
    return str(ticker).replace('.NS', '')


def _get(row, key):
    return row[key] if key in row.index else None


def _date(value):
    ts = pd.to_datetime(value, errors='coerce')
    return None if pd.isna(ts) else ts.strftime('%Y-%m-%d')


# ── signals ───────────────────────────────────────────────────────────────────

def _enriched(sigs: pd.DataFrame) -> pd.DataFrame:
    """Signals with the history overlay, as render_ipo ~6697-6704 (skipped on any error)."""
    try:
        report = md._build_report(md.S_IPO)
        return md.core_scorer.enrich_signals(sigs, report, feature_map={})
    except Exception as exc:
        print(f'warning: history overlay skipped ({exc})', file=sys.stderr)
        return sigs


def _signal_row(r: pd.Series) -> dict:
    return {'symbol': _symbol(r['Ticker']), **{k: _get(r, c) for k, c in SIGNAL_COLUMNS.items()}}


def _stage_counts(sigs: pd.DataFrame) -> dict:
    """Signal and stage counts, copied from render_ipo (master_dashboard.py ~6633-6636, 6648-6655)."""
    keys = ('live_breakout', 'watch_zone', 'stage3', 'stage2', 'stage1', 'in_trade')
    if sigs.empty:
        return dict.fromkeys(keys, 0)
    out = {
        'live_breakout': int((sigs['Signal'] == 'Live Breakout').sum()),
        'watch_zone': int((sigs['Signal'] == 'Watch Zone').sum()),
    }
    stage = sigs['Stage'] if 'Stage' in sigs.columns else pd.Series(dtype=object)
    for key, label in (('stage3', 'Stage 3'), ('stage2', 'Stage 2'),
                       ('stage1', 'Stage 1'), ('in_trade', 'In Trade')):
        out[key] = int((stage == label).sum())
    return out


# ── trades ────────────────────────────────────────────────────────────────────

def _win_rate(trades) -> float | None:
    """Win rate behind render_ipo's wr_str (master_dashboard.py ~6637-6646); None where it shows a dash."""
    if trades is None or not len(trades):
        return None
    if 'Result' in trades.columns:
        return float((trades['Result'] == 'Win').mean() * 100)
    if 'PnL_Pct' in trades.columns:
        closed = trades[trades['Status'] == 'Closed'] if 'Status' in trades.columns else trades
        return float((closed['PnL_Pct'] > 0).mean() * 100) if len(closed) else None
    return None


def _extra_columns(trades: pd.DataFrame) -> list[str]:
    """Columns holding more than one value, in Streamlit's order (render_ipo ~6735-6736)."""
    return [c for c in EXTRA_COLUMNS if c in trades.columns and trades[c].nunique(dropna=False) > 1]


def _extra_value(column: str, value) -> str:
    if column == 'Partial_Booked':   # render_ipo ~6746-6749: bools or 'True'/'False' strings
        return {'true': 'Yes', 'false': 'No'}.get(str(value).strip().lower(), '—')
    if column == 'Entry_Stage':      # render_ipo ~6751: 'Stage 3 — Breakout' -> 'Breakout'
        return str(value).split('—')[-1].strip()
    return str(value)


def _sorted(trades: pd.DataFrame) -> pd.DataFrame:
    """Newest exit first, open trades (no exit date) last."""
    out = trades.copy()
    out['_exit'] = pd.to_datetime(out['Exit_Date'], errors='coerce')
    return out.sort_values('_exit', ascending=False, na_position='last', kind='stable').reset_index(drop=True)


def _trade_rows(trades, extras: list[str]) -> list[dict]:
    if trades is None or trades.empty:
        return []
    hold = 'Holding_Days' if 'Holding_Days' in trades.columns else 'Hold_Days'
    rows = []
    for i, r in _sorted(trades).iterrows():
        rows.append({
            'id': int(i), 'symbol': _symbol(r['Ticker']), 'entry_date': _date(r['Entry_Date']),
            'entry_price': r['Entry_Price'], 'exit_date': _date(r['Exit_Date']),
            'exit_price': r['Exit_Price'], 'pnl': r['PnL_Pct'], 'hold_days': _get(r, hold),
            'exit_reason': _get(r, 'Exit_Reason'), 'result': _get(r, 'Result'),
            'extras': {c.replace('_', ' '): _extra_value(c, r[c]) for c in extras},
        })
    return rows


# ── page ──────────────────────────────────────────────────────────────────────

def build_ui_ipo(i: dict) -> dict:
    colour = md.THEME[md.S_IPO]['color']
    eq, trades = i.get('equity'), i.get('trades')
    raw_sigs = i.get('signals')
    sigs = raw_sigs if raw_sigs is not None else pd.DataFrame()
    mx = md._equity_metrics(eq, 'Portfolio_Value', 'Portfolio_Value') if eq is not None else {}
    chart = None
    if mx:
        # Column choice as render_ipo ~6676-6677.
        eq_col = 'Portfolio_Value' if 'Portfolio_Value' in eq.columns else 'Equity'
        bench = 'Benchmark_Value' if 'Benchmark_Value' in eq.columns else None
        chart = _traces(md.chart_equity(eq, eq_col, md.S_IPO, colour, bench))
    counts = _stage_counts(sigs)
    sigs = _enriched(sigs) if not sigs.empty else sigs
    has_trades = trades is not None and not trades.empty
    extras = _extra_columns(trades) if has_trades else []
    return _clean({
        'version': IPO_VERSION,
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'colour': colour,
        'summary': {k: mx[k] for k in ('cagr', 'total_ret', 'max_dd', 'start', 'end')} if mx else None,
        'chart': chart,
        'counts': {**counts, 'trades': len(trades) if trades is not None else 0,
                   'win_rate': _win_rate(trades)},
        'signals': [_signal_row(r) for _, r in sigs.iterrows()],
        'trades': _trade_rows(trades, extras),
        'extra_columns': [c.replace('_', ' ') for c in extras],
        'exit_rec': md._pick_rec('ipo_edge'),
    })


def main() -> None:
    snapshot = build_ui_ipo(md.load_ipo())
    write_snapshot(snapshot, OUT)
    print(f'wrote {OUT.name}: {len(snapshot["signals"])} signals, {len(snapshot["trades"])} trades')


if __name__ == '__main__':
    main()
