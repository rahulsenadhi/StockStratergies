"""precompute_ui_monthly builds ui_monthly.json from the same functions Streamlit's Monthly page uses."""
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
    sys.modules.pop('precompute_ui_monthly', None)
    return importlib.import_module('precompute_ui_monthly')


def _rebalance(n=3):
    dates = pd.date_range('2023-12-31', periods=n, freq='ME')
    return pd.DataFrame({'Date': dates.strftime('%Y-%m-%d'),
                         'Top5_Stocks': ['AAA.NS, BBB.NS'] * n,
                         'Stocks_Sold': [None] + ['AAA.NS'] * (n - 1),
                         'Stocks_Bought': ['BBB.NS, CCC.NS'] * n,
                         'Portfolio_Value': [50000.0 + 1000 * k for k in range(n)]})


@pytest.fixture
def m():
    idx = pd.date_range('2021-01-31', periods=40, freq='ME')
    eq = pd.DataFrame({'Portfolio_Value': 100 * 1.02 ** np.arange(40),
                       'Benchmark_Value': 100 * 1.01 ** np.arange(40)}, index=idx)
    ranks = pd.DataFrame({
        'Rank': [2, 1, 3], 'Ticker': ['BBB.NS', 'AAA.NS', 'CCC.NS'],
        'Company': ['Bbb Ltd', 'Aaa Ltd', 'Ccc Ltd'], 'Current_Price': [200.5, 100.25, 50.0],
        'Prev_Month_End_Price': [190.0, 90.0, 55.0], 'Return_%': [5.5, 11.4, -9.1],
        'Benchmark_Return_%': [3.0, np.nan, 3.0], 'RS_Score': [2.5, 8.4, -12.1],
        'Signal': ['🟡 Hold', '🟢 Strong BUY', '🔴 Avoid']})
    return {'rankings': ranks, 'equity': eq, 'rebalance': _rebalance()}


def test_summary_uses_equity_metrics(pre, m):
    out = pre.build_ui_monthly(m)
    exp = _md._equity_metrics(m['equity'], 'Portfolio_Value', 'Portfolio_Value')
    for k in ('cagr', 'total_ret', 'max_dd', 'start', 'end'):
        assert out['summary'][k] == exp[k]
    assert out['summary']['n_months'] == 3
    assert out['version'] == 1


def test_benchmark_matches_render_monthly_inline_formula(pre, m):
    out = pre.build_ui_monthly(m)
    eq = m['equity']
    # master_dashboard.py render_monthly, inline b_ret / b_cagr lines
    bv = eq['Benchmark_Value'].dropna()
    b_ret = (bv.iloc[-1] / bv.iloc[0] - 1) * 100
    b_yrs = (bv.index[-1] - bv.index[0]).days / 365.25
    b_cagr = ((bv.iloc[-1] / bv.iloc[0]) ** (1 / max(b_yrs, 0.01)) - 1) * 100
    s = out['summary']
    assert s['bench_ret'] == pytest.approx(b_ret)
    assert s['bench_cagr'] == pytest.approx(b_cagr)
    assert s['alpha'] == s['cagr'] - s['bench_cagr']


def test_no_benchmark_column_gives_streamlit_zero(pre, m):
    m['equity'] = m['equity'].drop(columns='Benchmark_Value')
    out = pre.build_ui_monthly(m)
    assert out['summary']['bench_ret'] == 0.0
    assert out['summary']['bench_cagr'] == 0.0
    assert all(len(out['chart'][w]) == 1 for w in ('1Y', '3Y', 'All'))


def test_no_equity(pre, m):
    del m['equity']
    out = pre.build_ui_monthly(m)
    assert out['summary'] is None and out['chart'] is None
    assert len(out['ranking']) == 3


def test_ranking_rows_and_filters(pre, m):
    out = pre.build_ui_monthly(m)
    assert [r['symbol'] for r in out['ranking']] == ['AAA', 'BBB', 'CCC']
    first = out['ranking'][0]
    assert first['rank'] == 1 and first['ticker'] == 'AAA.NS' and first['label'] == 'Strong BUY'
    assert first['bench_ret'] is None
    assert out['ranking'][1]['bench_ret'] == 3.0
    sorted_ranks = m['rankings'].sort_values('Rank', kind='stable')
    for f in _md._MONTHLY_FILTERS:
        assert out['filters'][f] == [t.replace('.NS', '') for t in _md._monthly_filter(sorted_ranks, f)['Ticker']]
    assert out['default_symbol'] == 'BBB'          # ranks.iloc[0] in file order
    assert out['top5'] == ['AAA', 'BBB', 'CCC']


def test_chart_traces_match_chart_equity(pre, m):
    out = pre.build_ui_monthly(m)
    fig = _md.chart_equity(_md._monthly_period_slice(m['equity'], '3Y'), 'Portfolio_Value',
                           _md.S_MONTHLY, out['colour'], 'Benchmark_Value')
    traces = out['chart']['3Y']
    assert [t['name'] for t in traces] == [t.name for t in fig.data]
    assert [t['colour'] for t in traces] == [t.line.color for t in fig.data]
    for t, f in zip(traces, fig.data):
        assert [p[1] for p in t['points']] == [float(y) for y in f.y]
    assert traces[0]['dash'] is False and traces[1]['dash'] is True


def test_closes_last_126_and_missing_file(pre, m, monkeypatch):
    idx = pd.date_range('2026-01-01', periods=200, freq='D')
    series = pd.Series(np.arange(200.0), index=idx)
    monkeypatch.setattr(_md, '_monthly_close_history', lambda t: series if t == 'AAA.NS' else None)
    out = pre.build_ui_monthly(m)
    assert len(out['closes']['AAA']['points']) == 126
    assert out['closes']['AAA']['saved_to'] == series.index[-1].strftime('%d %b %Y')
    assert 'BBB' not in out['closes']


def test_closes_skip_ticker_with_unreadable_history(pre, m, monkeypatch, capsys):
    good = pd.Series(np.arange(10.0), index=pd.date_range('2026-01-01', periods=10, freq='D'))
    bad = pd.Series(np.arange(10.0), index=[f'bad-{k}' for k in range(10)])   # text, not dates
    histories = {'AAA.NS': good, 'BBB.NS': bad, 'CCC.NS': good}
    monkeypatch.setattr(_md, '_monthly_close_history', lambda t: histories[t])
    out = pre.build_ui_monthly(m)
    assert 'BBB' not in out['closes']
    assert set(out['closes']) == {'AAA', 'CCC'}
    err = capsys.readouterr().err
    assert 'BBB' in err and 'AAA' not in err and 'CCC' not in err


def test_rebalances_latest_12_newest_first(pre, m):
    m['rebalance'] = _rebalance(14)
    out = pre.build_ui_monthly(m)
    reb = out['rebalances']
    assert reb['total'] == 14 and len(reb['rows']) == 12
    assert reb['rows'][0]['date'] == m['rebalance']['Date'].iloc[-1]
    assert reb['rows'][0]['top5'] == _md._monthly_tickers('AAA.NS, BBB.NS')
    assert reb['rows'][-1]['sold'] == 'AAA'


def test_checks_and_exit_rec(pre, m, monkeypatch):
    out = pre.build_ui_monthly(m)
    assert [c['label'] for c in out['checks']] == [_md.ui.CHECK_STATUS[s][0] for _, s, _ in _md.MONTHLY_CHECKS]
    monkeypatch.setattr(_md, '_pick_rec', lambda *a, **k: None)
    assert pre.build_ui_monthly(m)['exit_rec'] is None


def test_main_writes_atomic_json(pre, m, monkeypatch, tmp_path):
    target = tmp_path / 'ui_monthly.json'
    monkeypatch.setattr(pre, 'OUT', target)
    monkeypatch.setattr(_md, 'load_monthly', lambda: m)
    pre.main()
    assert json.loads(target.read_text(encoding='utf-8'))['version'] == 1
    assert not list(tmp_path.glob('*.json.tmp'))
