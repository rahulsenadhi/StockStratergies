# precompute_ui_home.py
"""Save the Home page's data for the Next.js Research Desk (web/).

Calls the same master_dashboard.py functions Streamlit's Home uses, so both apps
show the same numbers. No formulas live here — this only collects and saves.

Run:  python precompute_ui_home.py
Output (project root):  ui_snapshot.json   (schema version 1)
"""
from __future__ import annotations

import json
import math
import os
from datetime import datetime
from pathlib import Path

import pandas as pd

import master_dashboard as md

BASE_DIR = Path(__file__).resolve().parent
OUT = BASE_DIR / 'ui_snapshot.json'
SNAPSHOT_VERSION = 1
GROWTH_WINDOWS = ('1Y', '3Y', '5Y', 'Max')


def _clean(value):
    """JSON-safe copy: NaN/inf -> None, numpy/pandas scalars -> Python."""
    if isinstance(value, dict):
        return {str(k): _clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    if hasattr(value, 'item') and not isinstance(value, (str, bytes)):
        value = value.item()
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def _traces(fig) -> list[dict]:
    """Read a Plotly line figure's traces as plain data: name, colour, dotted flag, [date, y] points."""
    return [{
        'name': t.name, 'colour': t.line.color, 'dash': t.line.dash == 'dot',
        'points': [[pd.Timestamp(x).strftime('%Y-%m-%d'), float(y)] for x, y in zip(t.x, t.y)],
    } for t in fig.data]


def _candidates(m: dict, i: dict, mo: dict) -> list[dict]:
    cands = md._home_candidates(m, i, mo)
    return [{
        'strategy': r['Strategy'], 'short': md._SHORT.get(r['Strategy'], r['Strategy']),
        'ticker': r['Ticker'], 'company': r['Company'] or '', 'status': r['Status'],
        'status_tone': md._STATUS_TONE.get(r['Status'], 'info'),
        'key_measure': r['Key measure'],
        'change': None if r['Change'] is None or pd.isna(r['Change']) else float(r['Change']),
        'data': r['Data'],
    } for _, r in cands.iterrows()]


def _strategies() -> list[dict]:
    rows = []
    for s in md._load_strategies_index():
        k = s.get('kpis_inline', {}) or {}
        title, _, unit, _ = md.HOME_STRATEGIES.get(s['id'], (s.get('name', s['id']), None, 'trades', ''))
        n = int(k.get('num_trades') or 0)
        rows.append({'id': s['id'], 'title': title, 'status': s.get('status', '—'), 'num_trades': n,
                     'unit': unit, 'small_sample': n < md.ui.LOW_SAMPLE_TRADES,
                     'max_dd_pct': (k.get('max_dd') or 0) * 100, 'cagr_pct': (k.get('cagr') or 0) * 100})
    return rows


def _growth(m: dict, i: dict, mo: dict) -> dict:
    by_title = {v[0]: (sid, v[3]) for sid, v in md.HOME_STRATEGIES.items()}
    out = {}
    for window in GROWTH_WINDOWS:
        fig, legend = md._home_growth_figure(m, i, mo, window)
        starts = {title: (last, start) for title, _, last, start in legend}
        series = []
        for trace in fig.data:
            if trace.name not in by_title:
                continue
            sid, colour = by_title[trace.name]
            last, start = starts.get(trace.name, (None, ''))
            points = [[pd.Timestamp(x).strftime('%Y-%m-%d'), float(y)] for x, y in zip(trace.x, trace.y)]
            series.append({'id': sid, 'title': trace.name, 'colour': colour, 'start': start,
                           'last_pct': last, 'points': points})
        out[window] = series
    return out


def build_ui_snapshot(m: dict, i: dict, mo: dict) -> dict:
    pead_file = Path(md.BASE_DIR) / 'pead_data' / 'live_signals.csv'
    return _clean({
        'version': SNAPSHOT_VERSION,
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'frame': {'regime': md._regime_snapshot(), 'freshness': md._data_freshness()},
        'home': {
            'candidates': _candidates(m, i, mo),
            'pead_has_signals': pead_file.exists() and pead_file.stat().st_size >= 10,
            'strategies': _strategies(),
            'growth': _growth(m, i, mo),
        },
    })


def write_snapshot(snapshot: dict, path: Path, indent: int | None = 1) -> None:
    """Write atomically so a reader never sees a half-written file (indent=None: compact, for big files)."""
    tmp = path.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(_clean(snapshot), ensure_ascii=False, indent=indent), encoding='utf-8')
    os.replace(tmp, path)


def main() -> None:
    snapshot = build_ui_snapshot(md.load_monthly(), md.load_ipo(), md.load_momentum())
    write_snapshot(snapshot, OUT)
    print(f'wrote {OUT.name}: {len(snapshot["home"]["candidates"])} candidates')


if __name__ == '__main__':
    main()
