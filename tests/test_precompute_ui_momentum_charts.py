"""precompute_ui_momentum_charts saves Streamlit's Momentum indicator chart per stock."""
import importlib
import json
import sys

import numpy as np
import pandas as pd
import pytest

from tests.test_modern_table import md as _md  # master_dashboard loaded with a fake streamlit


@pytest.fixture(scope='module')
def pre():
    sys.modules['master_dashboard'] = _md
    sys.modules.pop('precompute_ui_momentum_charts', None)
    return importlib.import_module('precompute_ui_momentum_charts')


def _write_csv(base, symbol, n=800):
    idx = pd.date_range('2023-01-01', periods=n, freq='D')
    rng = np.random.default_rng(11)
    close = 100 + np.cumsum(rng.normal(0.2, 1.0, n))
    df = pd.DataFrame({'Open': close - 0.2, 'High': close + 1, 'Low': close - 1, 'Close': close,
                       'Volume': rng.integers(1000, 5000, n).astype(float)}, index=idx)
    folder = base / 'data' / 'nse_bse'
    folder.mkdir(parents=True, exist_ok=True)
    df.to_csv(folder / f'{symbol}.NS.csv')


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setattr(_md, 'BASE_DIR', tmp_path)


def _trades():
    return pd.DataFrame({'Ticker': ['AAA.NS'], 'Entry_Date': ['2024-06-01'], 'Entry_Price': [120.0],
                         'Exit_Date': ['2024-09-01'], 'Exit_Price': [130.0]})


def test_chart_has_four_rows_candles_rsi_lines_and_badges(pre, tmp_path):
    _write_csv(tmp_path, 'AAA')
    chart = pre.build_chart('AAA', _trades())
    assert chart['version'] == 1 and chart['symbol'] == 'AAA'
    assert chart['rows'] == ['price', 'rsi', 'macd', 'volume']
    candles = [t for t in chart['traces'] if t['type'] == 'candlestick']
    assert len(candles) == 1 and 0 < len(candles[0]['points']) <= 756
    assert len(candles[0]['points'][0]) == 5
    assert {t['name'] for t in chart['traces']} >= {'SMA 50', 'BB Upper', 'RSI(14)', 'MACD', 'Volume', 'BUY', 'EXIT'}
    rsi_lines = sorted(s['value'] for s in chart['shapes'] if s['kind'] == 'hline' and s['row'] == 2)
    assert rsi_lines == [30, 50, 70]
    assert [b['label'] for b in chart['badges']] == ['RSI(14)', 'MACD Hist', 'ADX(14)', 'ATR(14)', 'OBV 20d']
    assert all(b['value'] and b['sub'] for b in chart['badges'])
    assert chart['note'] is None


def test_missing_file_sets_note_and_no_traces(pre):
    chart = pre.build_chart('NOPE', None)
    assert chart['note'] and 'NOPE' in chart['note']
    assert chart['traces'] == [] and chart['shapes'] == [] and chart['badges'] == []


def test_streamlit_and_plot_restored_after_exception(pre, tmp_path, monkeypatch, capsys):
    _write_csv(tmp_path, 'AAA')
    real_st, real_plot = _md.st, _md._plot

    def boom(*a, **k):
        raise RuntimeError('boom')
    monkeypatch.setattr(_md, '_indicator_badge', boom)
    chart = pre.build_chart('AAA', None)
    assert _md.st is real_st and _md._plot is real_plot
    assert chart['traces'] == []
    assert chart['note'] == 'Chart could not be prepared for this stock in the last update.'
    assert 'boom' not in chart['note'] and 'RuntimeError' not in chart['note']
    assert 'boom' in capsys.readouterr().err


def test_index_lists_written_symbols_and_stale_file_is_removed(pre, tmp_path):
    _write_csv(tmp_path, 'AAA')
    out = tmp_path / 'ui_momentum_charts'
    out.mkdir()
    (out / 'OLD.json').write_text('{}')
    n, _size = pre.write_charts(['AAA'], _trades(), out)
    assert n == 1
    assert not (out / 'OLD.json').exists()
    assert json.loads((out / 'index.json').read_text()) == {'version': 1, 'symbols': ['AAA']}
    assert json.loads((out / 'AAA.json').read_text())['symbol'] == 'AAA'
    assert not list(out.glob('*.tmp'))
