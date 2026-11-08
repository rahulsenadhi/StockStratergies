"""Streamlit no longer starts updates: the Next.js app (web/) does, so two apps never
write the same files at once. Streamlit shows a note pointing there instead."""
from contextlib import contextmanager

import pytest

from tests.test_modern_table import md  # master_dashboard loaded with a fake streamlit


class Recorder:
    """Stands in for streamlit: records button/caption calls, everything else is a no-op."""

    def __init__(self):
        self.buttons, self.captions = [], []
        self.session_state = {}

    def button(self, label, *a, **k):
        self.buttons.append(label)
        return False

    def caption(self, text, *a, **k):
        self.captions.append(text)

    @contextmanager
    def _ctx(self, *a, **k):
        yield self

    container = popover = expander = status = _ctx

    def columns(self, spec, *a, **k):
        n = spec if isinstance(spec, int) else len(spec)
        return [self] * n

    def __getattr__(self, name):
        return lambda *a, **k: None


@pytest.fixture
def rec(monkeypatch):
    r = Recorder()
    monkeypatch.setitem(md._render_sidebar_refresh.__globals__, 'st', r)
    monkeypatch.setitem(md.render_staleness_banner.__globals__, 'st', r)
    return r


def test_note_text():
    from core.workflow_ui import UPDATES_MOVED_NOTE
    assert UPDATES_MOVED_NOTE == ('Updates now run from the new app: http://localhost:3000 '
                                  '(Update all data in its sidebar).')


def test_sidebar_has_no_update_buttons(rec):
    from core.workflow_ui import UPDATES_MOVED_NOTE
    md._render_sidebar_refresh()
    assert rec.buttons == []
    assert UPDATES_MOVED_NOTE in rec.captions


def test_staleness_banner_has_no_update_button(rec, monkeypatch):
    monkeypatch.setitem(md.render_staleness_banner.__globals__, 'dataset_staleness',
                        lambda folder: {'days_behind': 3, 'latest_date': '2026-11-03'})
    from core.workflow_ui import UPDATES_MOVED_NOTE
    md.render_staleness_banner('nse_bse', 'data/nse_bse')
    assert rec.buttons == []
    assert UPDATES_MOVED_NOTE in rec.captions


def test_step_lists_still_defined_for_the_web_app():
    assert set(md._PIPELINES) == {'Monthly', 'IPO', 'Momentum', 'PEAD'}
    assert all('precompute_ui_home.py' in v for v in md._PRECOMPUTE_FOR.values())
    assert all('precompute_ui_monthly.py' in v
               and v.index('precompute_ui_monthly.py') > v.index('precompute_ui_home.py')
               for k, v in md._PRECOMPUTE_FOR.items() if k != 'PEAD')
    assert 'precompute_ui_monthly.py' not in md._PRECOMPUTE_FOR['PEAD']
    assert 'precompute_ui_momentum.py' in md._PRECOMPUTE_FOR['Momentum']
    assert 'precompute_ui_momentum.py' in md._PRECOMPUTE_FOR['IPO']
    assert md._PRECOMPUTE_FOR['Momentum'][-2] == 'precompute_ui_momentum_charts.py'
    assert md._PRECOMPUTE_FOR['Momentum'][-3] == 'precompute_ui_ipo.py'
    others = md._PRECOMPUTE_FOR['IPO'] + md._PRECOMPUTE_FOR['Monthly'] + md._PRECOMPUTE_FOR['PEAD']
    assert 'precompute_ui_momentum_charts.py' not in others
    assert md._PRECOMPUTE_FOR['IPO'][-2] == 'precompute_ui_ipo.py'
    assert 'precompute_ui_ipo.py' not in md._PRECOMPUTE_FOR['Monthly'] + md._PRECOMPUTE_FOR['PEAD']
    assert 'precompute_ui_momentum.py' not in md._PRECOMPUTE_FOR['Monthly'] + md._PRECOMPUTE_FOR['PEAD']


def test_portfolio_monitor_is_last_step_of_every_update_path():
    from pathlib import Path
    assert all(v[-1] == 'portfolio_monitor.py' for v in md._PRECOMPUTE_FOR.values())
    root = Path(md.__file__).resolve().parent
    run_all = (root / 'run_all.py').read_text(encoding='utf-8')
    assert run_all.index("'portfolio_monitor.py'") > run_all.index("'precompute_ui_home.py'")
    bat = (root / 'refresh_data.bat').read_text(encoding='utf-8')
    assert bat.rindex('portfolio_monitor.py') > bat.rindex('precompute_ui_home.py')
    assert '[12/12]' in bat and '/11]' not in bat
    steps = (root / 'web' / 'lib' / 'desk' / 'update-steps.ts').read_text(encoding='utf-8')
    assert steps.count('["portfolio_monitor.py"]') == 4
