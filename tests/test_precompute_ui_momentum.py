"""precompute_ui_momentum builds ui_momentum.json from the same functions Streamlit's Momentum page uses."""
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
    sys.modules.pop('precompute_ui_momentum', None)
    return importlib.import_module('precompute_ui_momentum')


def _ohlcv(n=400):
    idx = pd.date_range('2025-01-01', periods=n, freq='D')
    rng = np.random.default_rng(7)
    close = 100 + np.cumsum(rng.normal(0.2, 1.0, n))
    return pd.DataFrame({'Open': close, 'High': close + 1, 'Low': close - 1,
                         'Close': close, 'Volume': rng.integers(1000, 5000, n).astype(float)},
                        index=idx)


def _write_csv(base, symbol, n=400):
    folder = base / 'data' / 'nse_bse'
    folder.mkdir(parents=True, exist_ok=True)
    _ohlcv(n).to_csv(folder / f'{symbol}.NS.csv')


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setattr(_md, 'BASE_DIR', tmp_path)
    monkeypatch.setattr(_md, '_build_report', lambda *a, **k: {})
    monkeypatch.setattr(_md, '_regime_snapshot', lambda: {'status': 'Bull'})
    monkeypatch.setattr(_md, '_loss_free_holding', lambda *a, **k: pd.DataFrame())
    monkeypatch.setattr(_md, '_pick_rec', lambda *a, **k: None)
    monkeypatch.setattr(_md, '_verify_past_trades', _fake_verify)
    return tmp_path


def _fake_verify(trades):
    out = trades.copy()
    out['Prior_52W_High'] = out['Entry_Price'] * 0.98
    out['Breakout_Margin_Pct'] = [0.5, 2.0, 1.0, 3.0, 0.25, 1.5][:len(out)]
    out['All_Filters_OK'] = [True, True, False, True, True, True][:len(out)]
    out['Filter_Detail'] = ['F1✓ F2✓ BK✓', 'F1✓ F2✗ BK✓', 'F1✓ F2✓ BK✓',
                            'F1✓ F2✓ BK✓', 'F1✓ F2✓ BK✓', 'F1✓ F2✓ BK✓'][:len(out)]
    return out


def _trades():
    return pd.DataFrame({
        'Ticker': ['AAA.NS', 'BBB.NS', 'CCC.NS', 'AAA.NS', 'DDD.NS', 'BBB.NS'],
        'Entry_Date': ['2022-02-01', '2023-05-01', '2024-01-05', '2024-08-01', '2025-04-01', '2025-10-01'],
        'Entry_Price': [100.0, 50.0, 200.0, 110.0, 80.0, 60.0],
        'Exit_Date': ['2022-03-01', '2023-06-01', '2024-02-01', '2024-09-01', '2025-05-01', '2025-11-01'],
        'Exit_Price': [115.0, 42.5, 230.0, 100.0, 90.0, 66.0],
        'Exit_Reason': ['220 EMA break', '15% Hard Stop', '220 EMA break', '220 EMA break',
                        '220 EMA break', '220 EMA break'],
        'PnL_Pct': [15.0, -15.0, 15.0, -9.1, 12.5, 10.0],
        'Holding_Days': [28, 30, 27, 31, 30, 31],
        'Result': ['Win', 'Loss', 'Win', 'Loss', 'Win', 'Win'],
        'Entry_Type': ['ATH', '52W_HIGH_FALLBACK', 'ATH', '52W_HIGH_FALLBACK', 'ATH', '52W_HIGH_FALLBACK'],
        'Recovery_Speed': ['Fast', 'Slow', 'Fast', 'No Reclaim', 'Fast', 'Slow'],
        'Recovery_Days': [9, 40, 12, -1, 8, 35],
    })


def _signals():
    return pd.DataFrame({
        'Ticker': ['AAA', 'BBB', 'CCC'],
        'Company': ['Aaa Ltd', 'Bbb Ltd', 'Ccc Ltd'],
        'Signal': ['Watch Zone', 'Near Breakout', 'Breakout Today'],
        'Close': [100.0, 50.0, 200.0],
        'ATH (₹)': [110.0, 51.0, 200.0],
        'Dist ATH%': [-9.1, -2.0, 0.0],
        'Entry Type': ['ATH', '52W High', 'ATH'],
        'Chart Qual': ['Clean ✅', 'Choppy', 'Clean ✅'],
        'Choppiness': [30.0, 60.0, 40.0],
        'Recovery': ['Fast 🟢', 'Slow 🔴', 'Fast 🟢'],
        '220 EMA': [90.0, 45.0, 180.0],
        '52W High': [110.0, 51.0, 200.0],
        'vs High%': [-9.1, -2.0, 0.0],
        'Vol Ratio': [1.2, 0.9, 2.5],
        'Score': [80.0, 70.0, 60.0],
    })


def _recent():
    return pd.DataFrame({
        'Ticker': ['DDD', 'EEE'], 'Days Ago': [0, 3], 'Bk Date': ['2026-11-06', '2026-11-03'],
        'Bk Price (₹)': [50.0, 70.0], 'Close (₹)': [50.0, 68.6], '% Off Bk': [0.0, -2.0],
        '220 EMA (₹)': [40.0, 60.0], 'Vol Ratio': [1.5, 1.1], 'Stop (₹)': [42.5, 58.3],
    })


@pytest.fixture
def mo():
    idx = pd.date_range('2023-01-01', periods=300, freq='D')
    eq = pd.DataFrame({'Equity': 100000 * 1.001 ** np.arange(300)}, index=idx)
    funnel = {'total': 500, 'sufficient_data': 450, 'f1': 300, 'f2': 200, 'f3': 150,
              'f4': 120, 'f5': 60, 'f6': 40, 'vol_bk': 3}
    return {'equity': eq, 'trades': _trades(), 'signals': _signals(),
            'recent_breakouts': _recent(), 'funnel': funnel}


def test_summary_and_chart_use_dashboard_functions(pre, mo):
    out = pre.build_ui_momentum(mo)
    exp = _md._equity_metrics(mo['equity'], 'Equity', 'Equity')
    for k in ('cagr', 'total_ret', 'max_dd', 'start', 'end'):
        assert out['summary'][k] == exp[k]
    fig = _md.chart_equity(mo['equity'], 'Equity', _md.S_MOMENTUM, out['colour'])
    assert out['chart'][0]['name'] == fig.data[0].name
    assert [p[1] for p in out['chart'][0]['points']] == [float(y) for y in fig.data[0].y]
    assert out['version'] == 1


def test_views_all_and_ath(pre, mo):
    out = pre.build_ui_momentum(mo)
    exp = _md._strategy_health(mo['trades'], mo['signals'])
    health = out['views']['all']['health']
    for k, v in exp.items():
        if k in ('verdict_color', 'verdict_bg'):
            assert k not in health
        else:
            assert health[k] == v
    assert health['verdict_tone'] in ('gain', 'warn', 'loss', 'muted')
    assert out['views']['all']['signal_ids'] == ['AAA', 'BBB', 'CCC']
    ath = out['views']['ath']
    assert ath['signal_ids'] == ['AAA', 'CCC']
    by_id = {t['id']: t for t in out['trades']}
    assert ath['trade_ids'] and all(by_id[i]['entry_type'] == 'All-time high' for i in ath['trade_ids'])
    assert len(ath['trade_ids']) == 3
    assert ath['health']['n_trades'] == 3
    assert out['views']['all']['counts'] == {'breakout': 1, 'near': 1, 'watch': 1,
                                             'ath': 2, 'clean': 2, 'fast': 2}
    assert ath['counts']['ath'] == 2 and ath['counts']['near'] == 0


def test_tabs_use_action_from_signal(pre, mo):
    tabs = pre.build_ui_momentum(mo)['tabs']
    assert tabs['All'] == ['AAA', 'BBB', 'CCC']
    assert tabs['FORMING'] == ['AAA']
    assert tabs['WATCH'] == ['BBB']
    assert tabs['BUY NOW'] == ['CCC']


def test_signal_rows_carry_stop_and_action(pre, mo):
    sig = pre.build_ui_momentum(mo)['signals'][2]
    assert sig['symbol'] == 'CCC' and sig['action'] == 'BUY NOW' and sig['signal'] == 'Breakout Today'
    stop = _md._suggest_stop(200.0, atr=None, winner_mae_p95_pct=None)
    assert sig['stop_price'] == stop['stop_price']
    assert sig['stop_pct'] == -abs(stop['stop_pct'])
    assert sig['dist_ath'] == 0.0 and sig['ath'] == 200.0 and sig['high52'] == 200.0


def test_criteria_parsed_from_render_panel(pre, mo, isolated):
    _write_csv(isolated, 'AAA')
    details = pre.build_ui_momentum(mo)['details']
    conds = details['AAA']['conditions']
    assert len(conds) == 7
    assert [c['label'][:2] for c in conds[:6]] == ['F1', 'F2', 'F3', 'F4', 'F5', 'F6']
    assert 'Breakout Trigger' in conds[6]['label']
    assert all(isinstance(c['ok'], bool) for c in conds)
    assert all(c['sub'] and c['detail'] for c in conds)
    assert details['AAA']['note'] is None


def test_criteria_missing_file_gives_note(pre, mo):
    mo['recent_breakouts'] = pd.DataFrame({
        **{c: [v] for c, v in _recent().iloc[0].items()}, 'Ticker': ['ZZZ']})
    real_st = _md.st
    details = pre.build_ui_momentum(mo)['details']
    assert details['ZZZ']['conditions'] is None
    assert details['ZZZ']['note'] == 'No OHLCV file for ZZZ — cannot render criteria.'
    assert _md.st is real_st


def test_criteria_restores_st_on_error(pre, mo, monkeypatch):
    real_st = _md.st
    monkeypatch.setattr(_md, '_render_criteria_panel', lambda t: 1 / 0)
    details = pre.build_ui_momentum(mo)['details']
    assert _md.st is real_st
    assert details['AAA']['conditions'] is None and 'ZeroDivisionError' in details['AAA']['note']


def test_chart_last_90_and_level(pre, mo, isolated):
    for s in ('AAA', 'DDD'):
        _write_csv(isolated, s)
    details = pre.build_ui_momentum(mo)['details']
    a, d = details['AAA']['chart'], details['DDD']['chart']
    assert len(a['close']) == 90 and len(a['ema220']) == 90
    assert a['level'] == {'label': '52-week high', 'value': 110.0}
    assert d['level'] == {'label': 'Breakout price', 'value': 50.0}
    assert a['saved_to'] == '04 Feb 2026'
    assert a['close'][-1][0] == '2026-02-04'
    assert details['BBB']['chart'] is None
    assert details['AAA']['past_trades'] == 2 and details['EEE']['past_trades'] == 0


def test_trade_filters(pre, mo):
    out = pre.build_ui_momentum(mo)
    trades, filt = out['trades'], out['trade_filters']
    assert [t['exit_date'] for t in trades] == sorted((t['exit_date'] for t in trades), reverse=True)
    assert [t['id'] for t in trades] == list(range(6))
    assert filt['periods']['All'] == list(range(6))
    latest = pd.Timestamp(trades[0]['exit_date'])
    exp_1y = [t['id'] for t in trades if pd.Timestamp(t['exit_date']) >= latest - pd.Timedelta(days=365)]
    assert filt['periods']['Last 1Y'] == exp_1y
    exp_3y = [t['id'] for t in trades if pd.Timestamp(t['exit_date']) >= latest - pd.Timedelta(days=365 * 3)]
    assert filt['periods']['Last 3Y'] == exp_3y
    assert filt['years'] == [2025, 2024, 2023, 2022]
    assert filt['periods']['2024'] == [t['id'] for t in trades if t['exit_date'].startswith('2024')]
    ver = _fake_verify(mo['trades'])
    ok = {(r.Ticker, r.Entry_Date) for r in ver.itertuples()
          if r.All_Filters_OK == True and r.Breakout_Margin_Pct >= 1.0}  # noqa: E712
    assert {(t['symbol'] + '.NS', t['entry_date']) for t in trades if t['id'] in filt['strict']} == ok


def test_trade_row_formatting(pre, mo):
    row = next(t for t in pre.build_ui_momentum(mo)['trades'] if t['exit_date'] == '2024-09-01')
    assert row['symbol'] == 'AAA' and row['entry_type'] == '52W high'
    assert row['recovery'] == 'No Reclaim'
    assert row['filters'] == _md._summarize_filter_detail('F1✓ F2✓ BK✓')
    assert row['pnl'] == -9.1 and row['hold_days'] == 31
    slow = next(t for t in pre.build_ui_momentum(mo)['trades'] if t['exit_date'] == '2023-06-01')
    assert slow['recovery'] == 'Slow · 40d' and slow['filters'] == '2/3 · failed F2'


def test_recent_and_funnel(pre, mo, monkeypatch):
    out = pre.build_ui_momentum(mo)
    assert out['recent'][0] == {'symbol': 'DDD', 'days_ago': 0, 'bk_date': '2026-11-06', 'bk_price': 50.0,
                                'close': 50.0, 'off_bk': 0.0, 'ema220': 40.0, 'vol_ratio': 1.5, 'stop': 42.5}
    assert out['funnel']['is_bull'] is True and out['funnel']['total'] == 500
    assert [s['key'] for s in out['funnel']['steps']] == [
        'total', 'sufficient_data', 'f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'vol_bk']
    monkeypatch.setattr(_md, '_regime_snapshot', lambda: {'status': 'Bear'})
    assert pre.build_ui_momentum(mo)['funnel']['is_bull'] is False
    mo['funnel'] = {'total': 0}
    assert pre.build_ui_momentum(mo)['funnel'] is None


def test_empty_signals(pre, mo):
    mo['signals'] = _signals().iloc[0:0]
    out = pre.build_ui_momentum(mo)
    assert out['signals'] == []
    assert all(v == [] for v in out['tabs'].values())
    assert set(out['details']) == {'DDD', 'EEE'}
    assert out['summary'] is not None


def test_no_equity_and_no_trades(pre, mo):
    del mo['equity'], mo['trades']
    out = pre.build_ui_momentum(mo)
    assert out['summary'] is None and out['chart'] is None
    assert out['trades'] == [] and out['trade_filters']['periods']['All'] == []


def test_main_writes_atomic_json(pre, mo, monkeypatch, tmp_path):
    target = tmp_path / 'ui_momentum.json'
    monkeypatch.setattr(pre, 'OUT', target)
    monkeypatch.setattr(_md, 'load_momentum', lambda: mo)
    pre.main()
    assert json.loads(target.read_text(encoding='utf-8'))['version'] == 1
    assert not list(tmp_path.glob('*.json.tmp'))
