import importlib.util
import sys
import types
from unittest.mock import patch

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
    replacements = {'streamlit': fake}
    for s in ('streamlit.components', 'streamlit.components.v1'):
        m = types.ModuleType(s)
        m.__getattr__ = lambda n: (lambda *a, **k: None)
        replacements[s] = m
    spec = importlib.util.spec_from_file_location('md', 'master_dashboard.py')
    md = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, replacements):
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


def test_long_table_has_no_inner_scroll_and_hides_extra_rows():
    n = md.TABLE_PREVIEW_ROWS + 5
    df = pd.DataFrame({'Ticker': [f'T{i}' for i in range(n)]})
    html = md._modern_table(df, max_height=560)
    assert 'max-height' not in html          # no nested scroll box
    assert html.count('class="mtbl-extra"') == 5
    assert f'Show all {n:,} rows' in html
    assert '<details class="mtbl-more">' in html


def test_short_table_with_max_height_has_no_toggle():
    df = pd.DataFrame({'Ticker': ['A', 'B']})
    html = md._modern_table(df, max_height=560)
    assert 'mtbl-extra' not in html and 'mtbl-more' not in html


def test_filter_detail_summary():
    assert md._summarize_filter_detail('F1✓ F2✓ F3✓ BK✓') == 'All 4 pass'
    assert md._summarize_filter_detail('F1✓ F2✗ BK✓ V✗') == '2/4 · failed F2, V'
    assert md._summarize_filter_detail(None) == '—'


def test_headers_readable_and_dates_nowrap():
    df = pd.DataFrame({'Entry_Date': ['2025-06-05'], 'Ticker': ['A']})
    html = md._modern_table(df)
    assert '>Entry Date</th>' in html
    assert '<td class="mtbl-nw">2025-06-05</td>' in html


def test_sortable_long_table_marks_preview_and_has_no_inline_script():
    n = md.TABLE_PREVIEW_ROWS + 3
    df = pd.DataFrame({'Ticker': [f'T{i}' for i in range(n)]})
    html = md._modern_table(df, sortable=True, max_height=560)
    assert '<script' not in html                 # handler is installed page-wide
    assert 'data-sort=1' in html
    assert f'data-preview="{md.TABLE_PREVIEW_ROWS}"' in html
