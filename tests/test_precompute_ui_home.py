"""precompute_ui_home builds ui_snapshot.json from the same functions Streamlit's Home uses."""
import importlib
import json
import sys

import pandas as pd
import pytest

from tests.test_modern_table import md as _md  # master_dashboard loaded with a fake streamlit


@pytest.fixture(scope='module')
def pre():
    sys.modules['master_dashboard'] = _md
    sys.modules.pop('precompute_ui_home', None)
    return importlib.import_module('precompute_ui_home')


@pytest.fixture
def sample_inputs():
    idx = pd.date_range('2024-01-01', periods=30, freq='D')
    m = {'rankings': pd.DataFrame({'Rank': [1, 2], 'Ticker': ['AAA.NS', 'BBB.NS'],
                                   'Company': ['Aaa Ltd', 'Bbb Ltd'], 'RS_Score': [7.7, 5.1],
                                   'Return_%': [15.83, 9.2]}),
         'equity': pd.DataFrame({'Portfolio_Value': range(100, 130)}, index=idx)}
    i = {'signals': pd.DataFrame({'Ticker': ['CCC.NS'], 'Company': ['Ccc Ltd'], 'Signal': ['Watch Zone'],
                                  'Stage': ['Stage 3'], 'Vol Ratio': [1.4]}),
         'equity': pd.DataFrame({'Portfolio_Value': range(200, 230)}, index=idx)}
    mo = {'signals': pd.DataFrame({'Ticker': ['DDD.NS'], 'Company': ['Ddd Ltd'], 'Signal': ['Near Breakout'],
                                   'Dist ATH%': [-3.5], 'Score': [56]}),
          'equity': pd.DataFrame({'Equity': range(300, 330)}, index=idx)}
    return m, i, mo


def test_snapshot_candidates_match_home_candidates(pre, sample_inputs):
    snap = pre.build_ui_snapshot(*sample_inputs)
    expected = _md._home_candidates(*sample_inputs)
    cands = snap['home']['candidates']
    assert [c['ticker'] for c in cands] == list(expected['Ticker'])
    assert cands[0]['status'] == 'Top 5 · #1'
    assert cands[0]['status_tone'] == 'info'          # not in _STATUS_TONE -> default 'info'
    assert cands[0]['short'] == 'Monthly'
    assert [c['status_tone'] for c in cands[2:]] == ['warn', 'info']   # Watch Zone, Near Breakout
    assert snap['version'] == 1


def test_snapshot_growth_windows_present(pre, sample_inputs):
    snap = pre.build_ui_snapshot(*sample_inputs)
    assert set(snap['home']['growth']) == {'1Y', '3Y', '5Y', 'Max'}
    first = snap['home']['growth']['Max'][0]
    assert first['id'] == 'monthly_rotation'
    assert first['points'][0] == ['2024-01-01', 0.0]   # rebased to 0% at window start
    assert first['colour'] == '#3B6FD8'


def test_snapshot_has_frame_and_strategies(pre, sample_inputs):
    snap = pre.build_ui_snapshot(*sample_inputs)
    assert set(snap['frame']) == {'regime', 'freshness'}
    for s in snap['home']['strategies']:
        assert set(s) >= {'id', 'title', 'status', 'num_trades', 'unit', 'small_sample', 'max_dd_pct', 'cagr_pct'}


def test_write_snapshot_is_atomic(pre, tmp_path):
    out = tmp_path / 'ui_snapshot.json'
    pre.write_snapshot({'version': 1, 'x': float('nan')}, out)
    assert json.loads(out.read_text(encoding='utf-8')) == {'version': 1, 'x': None}
    assert not list(tmp_path.glob('*.tmp'))           # temp file replaced, not left behind
