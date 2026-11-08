# precompute_ui_momentum.py
"""Save the Momentum page's data for the Next.js Research Desk (web/).

Calls the same master_dashboard.py functions Streamlit's render_momentum uses, so both
apps show the same numbers. No formulas live here, with three exceptions copied from
render_momentum (each has a comment naming its source line): the ATH-only filter, the
past-trade period cutoffs and the strict-mode mask. The protected-file checksum on
master_dashboard.py is the guard against these drifting.

Run:  python precompute_ui_momentum.py
Output (project root):  ui_momentum.json   (schema version 1)
"""
from __future__ import annotations

import contextlib
import html
import re
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

import master_dashboard as md
from precompute_ui_home import _clean, _traces, write_snapshot

BASE_DIR = Path(__file__).resolve().parent
OUT = BASE_DIR / 'ui_momentum.json'
MOMENTUM_VERSION = 1
CHART_SESSIONS = 90       # the detail chart keeps the last 90 sessions
TABS = ('BUY NOW', 'WATCH', 'FORMING')
FUNNEL_KEYS = ('total', 'sufficient_data', 'f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'vol_bk')
TONES = {'var(--success)': 'gain', 'var(--warning)': 'warn', 'var(--destructive)': 'loss'}
_CRIT_BLOCK = re.compile(
    r'<div class="(crit-ok|crit-fail)"[^>]*>.*?<div class="crit-label">(.*?)</div>'
    r'<div style="[^"]*">(.*?)</div><div class="crit-detail">(.*?)</div></div>', re.S)


def _symbol(ticker) -> str:
    return str(ticker).replace('.NS', '')


def _get(row, key):
    return row[key] if key in row.index else None


def _signals_frame(sigs: pd.DataFrame) -> pd.DataFrame:
    """Signals with the history overlay, stop columns and Action, as render_momentum ~7113-7134."""
    sigs = sigs.copy()
    stop_p95 = None
    try:
        report = md._build_report(md.S_MOMENTUM)
        sigs = md.core_scorer.enrich_signals(
            sigs, report, feature_map={'Entry Type': 'Entry_Type', 'Recovery': 'Recovery_Speed'})
        stop_p95 = (report.get('stop_recommendation') or {}).get('winner_mae_p95')
    except Exception as exc:
        print(f'warning: history overlay skipped ({exc})', file=sys.stderr)
    if 'Close' in sigs.columns:
        stops = sigs['Close'].apply(
            lambda px: md._suggest_stop(float(px), atr=None, winner_mae_p95_pct=stop_p95))
        sigs['Stop (₹)'] = stops.apply(lambda d: d.get('stop_price'))
        sigs['Stop %'] = stops.apply(lambda d: -abs(d.get('stop_pct') or 0))
    sigs['Action'] = sigs['Signal'].map(lambda s: md._action_from_signal(s, True))
    return sigs


def _signal_row(r: pd.Series) -> dict:
    cols = {
        'company': 'Company', 'signal': 'Signal', 'action': 'Action', 'close': 'Close',
        'ath': 'ATH (₹)', 'dist_ath': 'Dist ATH%', 'entry_type': 'Entry Type',
        'chart_qual': 'Chart Qual', 'choppiness': 'Choppiness', 'recovery': 'Recovery',
        'ema220': '220 EMA', 'high52': '52W High', 'vs_high': 'vs High%',
        'vol_ratio': 'Vol Ratio', 'score': 'Score', 'hist_win': 'Hist Win%',
        'hist_avg': 'Hist Avg%', 'hist_n': 'Hist N', 'stop_price': 'Stop (₹)',
        'stop_pct': 'Stop %',
    }
    return {'symbol': _symbol(r['Ticker']), **{k: _get(r, c) for k, c in cols.items()}}


def _recent_rows(recent: pd.DataFrame) -> list[dict]:
    cols = {'days_ago': 'Days Ago', 'bk_date': 'Bk Date', 'bk_price': 'Bk Price (₹)',
            'close': 'Close (₹)', 'off_bk': '% Off Bk', 'ema220': '220 EMA (₹)',
            'vol_ratio': 'Vol Ratio', 'stop': 'Stop (₹)'}
    return [{'symbol': _symbol(r['Ticker']), **{k: _get(r, c) for k, c in cols.items()}}
            for _, r in recent.iterrows()]


# ── views (all / ATH-only) ────────────────────────────────────────────────────

def _health(trades, sigs) -> dict:
    h = md._strategy_health(trades, sigs)
    tone = TONES.get(h.get('verdict_color'), 'muted')
    h = {k: v for k, v in h.items() if k not in ('verdict_color', 'verdict_bg')}
    return {**h, 'verdict_tone': tone}


def _counts(sigs: pd.DataFrame) -> dict:
    """render_momentum's n_bk ... n_fast (master_dashboard.py ~6979-6995)."""
    if sigs.empty:
        return dict.fromkeys(('breakout', 'near', 'watch', 'ath', 'clean', 'fast'), 0)
    has = sigs.columns
    return {
        'breakout': int((sigs['Signal'] == 'Breakout Today').sum()),
        'near': int((sigs['Signal'] == 'Near Breakout').sum()),
        'watch': int((sigs['Signal'] == 'Watch Zone').sum()),
        'ath': int((sigs['Entry Type'] == 'ATH').sum()) if 'Entry Type' in has else 0,
        'clean': int((sigs['Chart Qual'] == 'Clean ✅').sum()) if 'Chart Qual' in has else 0,
        'fast': int(sigs['Recovery'].str.startswith('Fast').sum()) if 'Recovery' in has else 0,
    }


def _ath_only(trades, sigs):
    """The ATH-only toggle, copied from render_momentum (master_dashboard.py ~6958-6962)."""
    if trades is not None and not trades.empty and 'Entry_Type' in trades.columns:
        trades = trades[trades['Entry_Type'] == 'ATH'].copy()
    if sigs is not None and not sigs.empty and 'Entry Type' in sigs.columns:
        sigs = sigs[sigs['Entry Type'] == 'ATH'].copy()
    return trades, sigs


def _views(trades, sigs: pd.DataFrame, sorted_trades: pd.DataFrame) -> dict:
    out = {}
    for key in ('all', 'ath'):
        t_view, s_view = _ath_only(trades, sigs) if key == 'ath' else (trades, sigs)
        ids = []
        if not sorted_trades.empty:
            keep = set(t_view.index) if t_view is not None else set()
            ids = [i for i, orig in enumerate(sorted_trades['_orig']) if orig in keep]
        out[key] = {
            'health': _health(t_view, s_view), 'counts': _counts(s_view),
            'signal_ids': [_symbol(t) for t in s_view['Ticker']] if not s_view.empty else [],
            'trade_ids': ids,
        }
    return out


# ── past trades ───────────────────────────────────────────────────────────────

def _sorted_trades(trades) -> pd.DataFrame:
    """Verified trades, newest exit first (render_momentum ~7416-7420); '_orig' is the raw row label."""
    if trades is None or trades.empty:
        return pd.DataFrame()
    verified = md._verify_past_trades(trades).copy()
    verified['_orig'] = trades.index
    verified['Exit_Date'] = pd.to_datetime(verified['Exit_Date'], errors='coerce')
    return verified.sort_values('Exit_Date', ascending=False).reset_index(drop=True)


def _recovery(r: pd.Series):
    speed, days = _get(r, 'Recovery_Speed'), _get(r, 'Recovery_Days')
    if speed is None:
        return None
    return f'{speed} · {int(days)}d' if pd.notna(days) and days > 0 else str(speed)


def _date(value):
    ts = pd.to_datetime(value, errors='coerce')
    return None if pd.isna(ts) else ts.strftime('%Y-%m-%d')


def _trade_rows(tr: pd.DataFrame) -> list[dict]:
    names = {'ATH': 'All-time high', '52W_HIGH_FALLBACK': '52W high'}
    rows = []
    for i, r in tr.iterrows():
        entry_type = _get(r, 'Entry_Type')
        rows.append({
            'id': int(i), 'symbol': _symbol(r['Ticker']), 'entry_date': _date(r['Entry_Date']),
            'entry_price': r['Entry_Price'], 'prior_high': _get(r, 'Prior_52W_High'),
            'bk_margin': _get(r, 'Breakout_Margin_Pct'), 'exit_date': _date(r['Exit_Date']),
            'exit_price': r['Exit_Price'], 'pnl': r['PnL_Pct'], 'hold_days': _get(r, 'Holding_Days'),
            'exit_reason': _get(r, 'Exit_Reason'), 'result': _get(r, 'Result'),
            'filters': md._summarize_filter_detail(_get(r, 'Filter_Detail')),
            'entry_type': names.get(entry_type, entry_type), 'recovery': _recovery(r),
        })
    return rows


def _trade_filters(tr: pd.DataFrame) -> dict:
    if tr.empty:
        return {'periods': {'Last 1Y': [], 'Last 3Y': [], 'All': []}, 'years': [], 'strict': []}
    exit_max = tr['Exit_Date'].max()
    # Period cutoffs copied from render_momentum (master_dashboard.py ~7446-7455).
    periods = {
        'Last 1Y': tr['Exit_Date'] >= exit_max - pd.Timedelta(days=365),
        'Last 3Y': tr['Exit_Date'] >= exit_max - pd.Timedelta(days=365 * 3),
        'All': pd.Series(True, index=tr.index),
    }
    years = sorted({d.year for d in tr['Exit_Date'].dropna()}, reverse=True)
    for y in years:
        periods[str(y)] = tr['Exit_Date'].dt.year == y
    strict = []
    if 'Breakout_Margin_Pct' in tr.columns:
        # Strict-mode mask copied from render_momentum (master_dashboard.py ~7460).
        mask = (tr['All_Filters_OK'] == True) & (tr['Breakout_Margin_Pct'] >= 1.0)  # noqa: E712
        strict = [int(i) for i in tr.index[mask]]
    return {'periods': {k: [int(i) for i in tr.index[m]] for k, m in periods.items()},
            'years': years, 'strict': strict}


# ── per-symbol details ────────────────────────────────────────────────────────

class _Recorder:
    """Stands in for streamlit while _render_criteria_panel runs, keeping what it would draw."""

    def __init__(self):
        self.blocks: list[str] = []
        self.notes: list[str] = []

    def markdown(self, body, **_kw):
        self.blocks.append(str(body))

    def info(self, text, **_kw):
        self.notes.append(str(text))

    def columns(self, n, **_kw):
        return [contextlib.nullcontext() for _ in range(n if isinstance(n, int) else len(n))]


def _criteria(symbol: str) -> tuple[list[dict] | None, str | None]:
    rec, real_st = _Recorder(), md.st
    md.st = rec
    try:
        md._render_criteria_panel(symbol)
    except Exception as exc:
        print(f'warning: {symbol} criteria not saved ({exc})', file=sys.stderr)
        return None, f'Could not render criteria: {type(exc).__name__}: {exc}'
    finally:
        md.st = real_st
    if rec.notes:
        return None, rec.notes[0]
    conds = [{'ok': kind == 'crit-ok', 'label': html.unescape(label).strip(),
              'sub': html.unescape(sub).strip(), 'detail': html.unescape(detail).strip()}
             for block in rec.blocks for kind, label, sub, detail in _CRIT_BLOCK.findall(block)]
    return conds or None, None


def _chart_path(symbol: str) -> Path | None:
    """The first existing file, in _render_me_detail's order (master_dashboard.py ~3685-3688)."""
    base = Path(md.BASE_DIR)
    cands = (base / 'data' / 'nse_bse' / f'{symbol}.NS.csv',
             base / 'momentum_edge_data' / f'{symbol}.NS.csv',
             base / 'data' / 'nse_bse' / f'{symbol}.csv')
    return next((p for p in cands if p.exists()), None)


def _points(series: pd.Series) -> list[list]:
    return [[pd.Timestamp(x).strftime('%Y-%m-%d'), v] for x, v in series.items()]


def _chart(symbol: str, level: dict | None) -> dict | None:
    path = _chart_path(symbol)
    df = md._compute_full_indicators(str(path)) if path else None
    if df is None or df.empty:
        return None
    tail = df.iloc[-CHART_SESSIONS:]
    return {'saved_to': f'{tail.index[-1]:%d %b %Y}', 'close': _points(tail['Close']),
            'ema220': _points(tail['ema220']), 'level': level}


def _details(sigs: pd.DataFrame, recent: pd.DataFrame, trades) -> dict:
    levels = {_symbol(r['Ticker']): {'label': 'Breakout price', 'value': r['Bk Price (₹)']}
              for _, r in recent.iterrows()}
    levels.update({_symbol(r['Ticker']): {'label': '52-week high', 'value': _get(r, '52W High')}
                   for _, r in sigs.iterrows()})
    counts = trades['Ticker'].map(_symbol).value_counts() if trades is not None and not trades.empty else {}
    out = {}
    for symbol, level in levels.items():
        conditions, note = _criteria(symbol)
        out[symbol] = {'conditions': conditions, 'note': note, 'chart': _chart(symbol, level),
                       'past_trades': int(counts.get(symbol, 0))}
    return out


# ── page ──────────────────────────────────────────────────────────────────────

def _funnel(funnel: dict) -> dict | None:
    if not funnel or funnel.get('total', 0) <= 0:
        return None
    is_bull = True   # render_momentum ~7309-7314
    try:
        is_bull = md._regime_snapshot().get('status') == 'Bull'
    except Exception:
        pass
    return {'is_bull': is_bull, 'total': int(funnel['total']),
            'steps': [{'key': k, 'count': int(funnel.get(k, 0))} for k in FUNNEL_KEYS]}


def build_ui_momentum(mo: dict) -> dict:
    colour = md.THEME[md.S_MOMENTUM]['color']
    eq, trades = mo.get('equity'), mo.get('trades')
    raw_sigs = mo.get('signals')
    raw_sigs = raw_sigs if raw_sigs is not None else pd.DataFrame()
    recent = mo.get('recent_breakouts')
    recent = recent if recent is not None else pd.DataFrame()
    mx = md._equity_metrics(eq, 'Equity', 'Equity') if eq is not None else {}
    sigs = _signals_frame(raw_sigs) if not raw_sigs.empty else raw_sigs
    tr = _sorted_trades(trades)
    tabs = {'All': [_symbol(t) for t in sigs['Ticker']] if not sigs.empty else []}
    for tab in TABS:
        tabs[tab] = [_symbol(r['Ticker']) for _, r in sigs.iterrows() if r['Action'] == tab]
    return _clean({
        'version': MOMENTUM_VERSION,
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'colour': colour,
        'summary': {k: mx[k] for k in ('cagr', 'total_ret', 'max_dd', 'start', 'end')} if mx else None,
        'chart': _traces(md.chart_equity(eq, 'Equity', md.S_MOMENTUM, colour)) if mx else None,
        'views': _views(trades, raw_sigs, tr),
        'signals': [_signal_row(r) for _, r in sigs.iterrows()],
        'tabs': tabs,
        'recent': _recent_rows(recent),
        'funnel': _funnel(mo.get('funnel') or {}),
        'details': _details(sigs, recent, trades),
        'trades': _trade_rows(tr),
        'trade_filters': _trade_filters(tr),
        'exit_rec': md._pick_rec('momentum_edge'),
    })


def main() -> None:
    snapshot = build_ui_momentum(md.load_momentum())
    write_snapshot(snapshot, OUT, indent=None)   # compact: per-symbol charts make it ~2 MB indented
    print(f'wrote {OUT.name}: {len(snapshot["signals"])} signals, '
          f'{len(snapshot["recent"])} recent, {len(snapshot["trades"])} trades')


if __name__ == '__main__':
    main()
