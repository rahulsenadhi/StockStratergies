import importlib.util
import sys
import types

import pandas as pd


def _load_md():
    def _pass(*a, **k):
        if len(a) == 1 and callable(a[0]) and not k:
            return a[0]
        return lambda f: f
    fake = types.ModuleType('streamlit')
    fake.cache_data = _pass
    fake.cache_resource = _pass
    fake.__getattr__ = lambda n: (lambda *a, **k: None)
    sys.modules['streamlit'] = fake
    for s in ('streamlit.components', 'streamlit.components.v1'):
        m = types.ModuleType(s)
        m.__getattr__ = lambda n: (lambda *a, **k: None)
        sys.modules[s] = m
    spec = importlib.util.spec_from_file_location('md', 'master_dashboard.py')
    md = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(md)
    return md


md = _load_md()


def test_modern_table_renders_rows_and_headers():
    df = pd.DataFrame({'Ticker': ['INFY', 'TCS'], 'Return': ['+5.0%', '-2.0%']})
    html = md._modern_table(df, numeric_cols=['Return'])
    assert '<table' in html and 'mtbl' in html
    assert html.count('<tr') == 3            # header + 2 rows
    assert 'INFY' in html and 'TCS' in html
    assert 'mtbl-num' in html                # numeric cell class applied


def test_modern_table_status_pill():
    df = pd.DataFrame({'Name': ['A'], 'Status': ['Live']})
    html = md._modern_table(df, status_col='Status')
    assert 'mtbl-pill' in html
