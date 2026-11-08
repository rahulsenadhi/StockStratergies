# precompute_ui_momentum_charts.py
"""Save Streamlit's Momentum indicator chart, per stock, for the Next.js Research Desk (web/).

Runs master_dashboard._render_me_detail (the chart under Streamlit's Momentum signals) with
a recorder standing in for streamlit and a capturer standing in for md._plot, then turns
the captured Plotly figure into plain data. No indicator maths lives here. The period is
forced to 3Y (the longest Streamlit offers except "All") and all four toggles are on; the
web app slices 1M..1Y from that. The protected-file checksum on master_dashboard.py is the
guard against the page drifting from Streamlit.

Run:  python precompute_ui_momentum_charts.py
Output (project root):  ui_momentum_charts/{SYMBOL}.json + index.json   (schema version 1)
"""
from __future__ import annotations

import html
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

import master_dashboard as md
from precompute_ui_home import _clean
from precompute_ui_momentum import OUT as MOMENTUM_JSON, _Recorder

BASE_DIR = Path(__file__).resolve().parent
OUT_DIR = BASE_DIR / 'ui_momentum_charts'
CHARTS_VERSION = 1
ROWS = ['price', 'rsi', 'macd', 'volume']
PERIOD = '3Y'   # md._PERIOD_BARS['3Y'] = 756 sessions
_BADGE = re.compile(
    r'text-transform:uppercase;font-weight:500;">(.*?)</div>'
    r'<div style="[^"]*?color:([^;]+);[^"]*">(.*?)</div>'
    r'<div style="[^"]*">(.*?)</div></div>', re.S)
_TAGS = re.compile(r'<[^>]+>')
_AXIS_ROW = re.compile(r'^[xy](\d*)')


class _ChartRecorder(_Recorder):
    """The criteria recorder plus the widgets _render_me_detail uses; picks 3Y and all toggles on."""

    def __init__(self):
        super().__init__()
        self.captions: list[str] = []
        self.metrics: list[tuple] = []

    def radio(self, label, options, index=0, **_kw):
        return PERIOD if PERIOD in options else list(options)[index]

    def checkbox(self, label, value=False, **_kw):
        return True

    def caption(self, body, **_kw):
        self.captions.append(str(body))

    def metric(self, label, value, **_kw):
        self.metrics.append((label, value))


def _dates(values) -> list[str]:
    return [pd.Timestamp(x).strftime('%Y-%m-%d') for x in values]


def _row(axis_ref) -> int:
    match = _AXIS_ROW.match(str(axis_ref or 'y'))
    return int(match.group(1) or 1) if match else 1


def _num(value, digits=2):
    return None if value is None or pd.isna(value) else round(float(value), digits)


def _short(value):
    """Indicator values: whole numbers from 100,000 up (volume, OBV), else 5 significant digits."""
    if value is None or pd.isna(value):
        return None
    return round(float(value)) if abs(value) >= 100_000 else float(f'{float(value):.5g}')


def _kind(trace) -> str:
    if trace.type == 'candlestick':
        return 'candlestick'
    if trace.type == 'bar':
        return 'bar'
    return 'markers' if trace.mode == 'markers' else 'line'


def _trace(trace) -> dict:
    kind, xs = _kind(trace), _dates(trace.x)
    row = _row(trace.yaxis)
    if kind == 'candlestick':
        rows = zip(xs, trace.open, trace.high, trace.low, trace.close)
        points = [[d, _num(o), _num(h), _num(lo), _num(c)] for d, o, h, lo, c in rows]
        return {'name': trace.name, 'type': kind, 'row': row, 'colour': trace.increasing.line.color,
                'colour_down': trace.decreasing.line.color, 'dash': 'solid', 'points': points}
    ys = list(trace.y)
    if kind == 'bar':
        colours = trace.marker.color
        per_bar = colours is not None and not isinstance(colours, str)
        points = [[d, _short(y), c] if per_bar else [d, _short(y)]
                  for d, y, c in zip(xs, ys, colours if per_bar else ys)]
        colour = None if per_bar else colours
    elif kind == 'markers':
        points, colour = [[d, _short(y)] for d, y in zip(xs, ys)], trace.marker.color
    else:
        points = [[d, _short(y)] for d, y in zip(xs, ys) if y is not None and not pd.isna(y)]
        colour = trace.line.color
    return {'name': trace.name, 'type': kind, 'row': row, 'colour': colour,
            'dash': (trace.line.dash if kind == 'line' else None) or 'solid',
            'symbol': trace.marker.symbol if kind == 'markers' else None,
            'fill': trace.fill if kind == 'line' else None, 'opacity': trace.opacity if kind == 'bar' else None, 'points': points}


def _shapes(fig) -> list[dict]:
    out = []
    for s in fig.layout.shapes:
        horizontal = s.y0 == s.y1 and s.x0 != s.x1
        label = next((a.text for a in fig.layout.annotations
                      if horizontal and a.yref == s.yref and a.y == s.y0), None)
        value = _short(s.y0) if horizontal else _dates([s.x0])[0]
        out.append({'kind': 'hline' if horizontal else 'vline', 'row': _row(s.yref),
                    'value': value, 'colour': s.line.color, 'dash': s.line.dash or 'solid',
                    'label': label})
    return out


def _badges(blocks: list[str]) -> list[dict]:
    return [{'label': html.unescape(label).strip(), 'value': html.unescape(value).strip(),
             'sub': html.unescape(sub).strip(), 'colour': colour.strip()}
            for block in blocks for label, colour, value, sub in _BADGE.findall(block)]


def _since_line(rec: _ChartRecorder) -> str | None:
    for block in rec.blocks:
        if 'Since all conditions met' in block:
            return html.unescape(_TAGS.sub('', block)).strip()
    return rec.captions[0] if rec.captions else None


def _empty(symbol: str, note: str) -> dict:
    return {'version': CHARTS_VERSION, 'symbol': symbol, 'rows': ROWS, 'traces': [], 'shapes': [],
            'badges': [], 'since_line': None, 'note': note}


def build_chart(symbol: str, trades) -> dict:
    """One stock's chart data. md.st and md._plot are swapped for the render and always restored."""
    rec, figs = _ChartRecorder(), []
    real_st, real_plot = md.st, md._plot
    md.st, md._plot = rec, lambda fig, **_kw: figs.append(fig)
    try:
        md._render_me_detail(symbol, trades)
    except Exception as exc:
        print(f'warning: {symbol} chart not saved ({exc})', file=sys.stderr)
        return _empty(symbol, f'Could not render chart: {type(exc).__name__}: {exc}')
    finally:
        md.st, md._plot = real_st, real_plot
    if not figs:
        return _empty(symbol, rec.notes[0] if rec.notes else 'No chart could be drawn.')
    fig = figs[0]
    return {'version': CHARTS_VERSION, 'symbol': symbol, 'rows': ROWS,
            'traces': [_trace(t) for t in fig.data], 'shapes': _shapes(fig),
            'badges': _badges(rec.blocks), 'since_line': _since_line(rec), 'note': None}


def _write_json(path: Path, payload: dict) -> int:
    """Atomic compact write; returns bytes written."""
    tmp = path.with_suffix('.json.tmp')
    text = json.dumps(_clean(payload), ensure_ascii=False, separators=(',', ':'))
    tmp.write_text(text, encoding='utf-8')
    os.replace(tmp, path)
    return len(text.encode('utf-8'))


def write_charts(symbols: list[str], trades, out_dir: Path) -> tuple[int, int]:
    """Write one file per symbol plus index.json; delete files of symbols no longer listed."""
    out_dir.mkdir(parents=True, exist_ok=True)
    generated, total = datetime.now().isoformat(timespec='seconds'), 0
    for symbol in symbols:
        total += _write_json(out_dir / f'{symbol}.json',
                             {**build_chart(symbol, trades), 'generated_at': generated})
    total += _write_json(out_dir / 'index.json', {'version': CHARTS_VERSION, 'symbols': symbols})
    keep = {f'{s}.json' for s in symbols} | {'index.json'}
    for stale in out_dir.glob('*.json'):
        if stale.name not in keep:
            stale.unlink()
    return len(symbols), total


def main() -> None:
    symbols = list(json.loads(MOMENTUM_JSON.read_text(encoding='utf-8'))['details'])
    count, size = write_charts(symbols, md.load_momentum().get('trades'), OUT_DIR)
    print(f'wrote {count} chart files ({size / 1_000_000:.1f} MB)')


if __name__ == '__main__':
    main()
