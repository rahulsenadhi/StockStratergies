"""precompute_ui_ipo builds ui_ipo.json from the same functions Streamlit's IPO page uses."""
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
    sys.modules.pop('precompute_ui_ipo', None)
    return importlib.import_module('precompute_ui_ipo')


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    monkeypatch.setattr(_md, '_build_report', lambda *a, **k: {})
    monkeypatch.setattr(_md, '_pick_rec', lambda *a, **k: None)


def _signals():
    return pd.DataFrame({
        'Ticker': ['AAA.NS', 'BBB.NS'], 'Company': ['Aaa Ltd', 'Bbb Ltd'],
        'Signal': ['Live Breakout', 'Watch Zone'], 'Stage': ['Stage 3', 'Stage 2'],
        'Setup': ['STANDARD', 'STANDARD'], 'Close': [110.0, 95.0], 'Bk Level': [105.0, 100.0],
        'vs Bk%': [4.8, -5.0], 'Vol Ratio': [2.1, 0.9], 'IPO Day Val': [300.0, 120.0],
        'Liquidity': ['Liquid', 'Liquid'], 'Promoter': ['Yes', 'No'],
        'Listing PE': [25.0, np.nan], 'Age (d)': [80, 120], 'Score': [8.0, 5.0],
    })


def _trades():
    return pd.DataFrame({
        'Ticker': ['AAA.NS', 'BBB.NS', 'CCC.NS', 'DDD.NS', 'EEE.NS'],
        'Entry_Date': ['2025-01-01', '2025-02-01', '2025-03-01', '2025-04-01', '2025-05-01'],
        'Entry_Price': [100.0, 50.0, 200.0, 80.0, 60.0],
        'Exit_Date': ['2025-02-01', '2025-03-15', '2025-04-20', '2025-06-01', None],
        'Exit_Price': [110.0, 45.0, 230.0, 90.0, np.nan],
        'PnL_Pct': [10.0, -10.0, 15.0, 12.5, np.nan],
        'Holding_Days': [31, 42, 50, 61, np.nan],
        'Exit_Reason': ['SMA10 Trail', 'Hard Stop', 'SMA10 Trail', 'SMA10 Trail', 'Open'],
        'Status': ['Closed', 'Closed', 'Closed', 'Closed', 'Open'],
        'Result': ['Win', 'Loss', 'Win', 'Win', 'Open'],
        'Partial_Booked': ['True', 'False', 'False', 'True', 'False'],
        'Liquidity_Status': ['Liquid'] * 5,
        'Entry_Stage': ['Stage 3 — Breakout', 'Stage 1 — Building Base', 'Stage 3 — Breakout',
                        'Stage 2 — Recovering', 'Stage 3 — Breakout'],
    })


@pytest.fixture
def i():
    idx = pd.date_range('2023-01-01', periods=300, freq='D')
    eq = pd.DataFrame({'Portfolio_Value': 100000 * 1.001 ** np.arange(300),
                       'Benchmark_Value': 100000 * 1.0005 ** np.arange(300)}, index=idx)
    return {'equity': eq, 'trades': _trades(), 'signals': _signals()}


def test_summary_and_chart_use_dashboard_functions(pre, i):
    out = pre.build_ui_ipo(i)
    exp = _md._equity_metrics(i['equity'], 'Portfolio_Value', 'Portfolio_Value')
    for k in ('cagr', 'total_ret', 'max_dd', 'start', 'end'):
        assert out['summary'][k] == exp[k]
    fig = _md.chart_equity(i['equity'], 'Portfolio_Value', _md.S_IPO, out['colour'], 'Benchmark_Value')
    assert len(out['chart']) == 2
    for trace, ref in zip(out['chart'], fig.data):
        assert trace['name'] == ref.name
        assert [p[1] for p in trace['points']] == [float(y) for y in ref.y]
    assert out['version'] == 1
    i['equity'] = i['equity'][['Portfolio_Value']]
    assert len(pre.build_ui_ipo(i)['chart']) == 1


def test_counts_match_render_ipo(pre, i):
    c = pre.build_ui_ipo(i)['counts']
    assert c == {'live_breakout': 1, 'watch_zone': 1, 'stage3': 1, 'stage2': 1, 'stage1': 0,
                 'in_trade': 0, 'trades': 5, 'win_rate': 3 / 5 * 100}


def test_win_rate_falls_back_to_pnl(pre, i):
    t = i['trades'].drop(columns='Result')
    i['trades'] = t
    assert pre.build_ui_ipo(i)['counts']['win_rate'] == 3 / 4 * 100
    del i['trades']
    out = pre.build_ui_ipo(i)
    assert out['counts']['win_rate'] is None and out['counts']['trades'] == 0


def test_trades_display_rules(pre, i):
    out = pre.build_ui_ipo(i)
    trades = out['trades']
    assert [t['symbol'] for t in trades] == ['DDD', 'CCC', 'BBB', 'AAA', 'EEE']
    open_t = trades[-1]
    assert open_t['result'] == 'Open'
    assert open_t['exit_date'] is None and open_t['exit_price'] is None
    assert open_t['pnl'] is None and open_t['hold_days'] is None
    by = {t['symbol']: t for t in trades}
    assert by['AAA']['extras']['Partial Booked'] == 'Yes'
    assert by['BBB']['extras']['Partial Booked'] == 'No'
    assert by['AAA']['extras']['Entry Stage'] == 'Breakout'
    assert out['extra_columns'] == ['Entry Stage', 'Partial Booked']
    assert 'Liquidity Status' not in out['extra_columns']
    assert by['AAA']['entry_date'] == '2025-01-01'


def test_signal_rows_nan_becomes_none(pre, i):
    sigs = pre.build_ui_ipo(i)['signals']
    assert [s['symbol'] for s in sigs] == ['AAA', 'BBB']
    assert sigs[0]['bk_level'] == 105.0 and sigs[0]['vs_bk'] == 4.8
    assert sigs[0]['listing_pe'] == 25.0 and sigs[1]['listing_pe'] is None


def test_empty_signals_still_saves_trades(pre, i):
    i['signals'] = _signals().iloc[0:0]
    out = pre.build_ui_ipo(i)
    assert out['signals'] == []
    assert all(out['counts'][k] == 0 for k in
               ('live_breakout', 'watch_zone', 'stage3', 'stage2', 'stage1', 'in_trade'))
    assert len(out['trades']) == 5 and out['summary'] is not None


def test_no_equity(pre, i):
    del i['equity']
    out = pre.build_ui_ipo(i)
    assert out['summary'] is None and out['chart'] is None


def test_main_writes_atomic_json(pre, i, monkeypatch, tmp_path):
    target = tmp_path / 'ui_ipo.json'
    monkeypatch.setattr(pre, 'OUT', target)
    monkeypatch.setattr(_md, 'load_ipo', lambda: i)
    pre.main()
    assert json.loads(target.read_text(encoding='utf-8'))['version'] == 1
    assert not list(tmp_path.glob('*.json.tmp'))
