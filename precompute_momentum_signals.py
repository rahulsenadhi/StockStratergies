"""Precompute Momentum Edge live signals to disk so the dashboard reads instead of computes.

The master dashboard's `load_momentum()` runs two full-universe scans
(`_compute_momentum_signals` ~16s + `_scan_recent_breakouts` ~36s) on every page
load, which leaves the page stuck on a Streamlit skeleton. This script runs that
same compute ONCE (as part of the data pipeline, after `momentum_edge_backtest.py`)
and persists the results. `load_momentum()` then reads these files in ~0.1s.

We import the dashboard's real compute functions verbatim (with a minimal Streamlit
stub) so the persisted output is byte-identical to what the live path would produce.

Run:  python precompute_momentum_signals.py
Outputs (in project root):
  momentum_edge_signals.csv           — signals DataFrame
  momentum_edge_funnel.json           — funnel dict
  momentum_edge_recent_breakouts.csv  — recent breakouts DataFrame
"""
from __future__ import annotations

import json
import sys
import time
import types
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
SIGNALS_OUT   = BASE_DIR / 'momentum_edge_signals.csv'
FUNNEL_OUT    = BASE_DIR / 'momentum_edge_funnel.json'
BREAKOUTS_OUT = BASE_DIR / 'momentum_edge_recent_breakouts.csv'


def _install_streamlit_stub() -> None:
    """Let master_dashboard import without a Streamlit runtime.

    Cache decorators become passthroughs; UI calls become no-ops. We only ever
    call the pure compute functions, so no real Streamlit behavior is needed.
    """
    if 'streamlit' in sys.modules:
        return

    def _noop(*_a, **_k):
        class _Ctx:
            def __enter__(self): return self
            def __exit__(self, *_): return False
        return _Ctx()

    def _passthru(*a, **k):
        # Supports both @st.cache_data and @st.cache_data(ttl=...)
        if len(a) == 1 and callable(a[0]) and not k:
            return a[0]
        def deco(fn):
            return fn
        return deco

    fake = types.ModuleType('streamlit')
    fake.cache_data = _passthru
    fake.cache_resource = _passthru
    fake.__version__ = '0'
    fake.__getattr__ = lambda _name: _noop  # any other st.* -> no-op
    sys.modules['streamlit'] = fake

    for sub in ('streamlit.components', 'streamlit.components.v1'):
        m = types.ModuleType(sub)
        m.__getattr__ = lambda _name: _noop
        sys.modules[sub] = m


def main() -> int:
    _install_streamlit_stub()

    print('Importing dashboard compute functions…', flush=True)
    t0 = time.time()
    import importlib.util
    spec = importlib.util.spec_from_file_location('master_dashboard', str(BASE_DIR / 'master_dashboard.py'))
    md = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(md)
    print(f'  imported in {time.time() - t0:.1f}s', flush=True)

    print('Computing momentum signals (full universe)…', flush=True)
    t = time.time()
    signals_df, funnel = md._compute_momentum_signals()
    print(f'  signals: {len(signals_df)} rows in {time.time() - t:.1f}s', flush=True)

    print('Scanning recent breakouts…', flush=True)
    t = time.time()
    breakouts_df = md._scan_recent_breakouts()
    print(f'  recent breakouts: {len(breakouts_df)} rows in {time.time() - t:.1f}s', flush=True)

    signals_df.to_csv(SIGNALS_OUT, index=False)
    breakouts_df.to_csv(BREAKOUTS_OUT, index=False)
    with open(FUNNEL_OUT, 'w', encoding='utf-8') as fh:
        json.dump(funnel, fh, default=str)

    print(f'Wrote:\n  {SIGNALS_OUT.name} ({len(signals_df)} rows)'
          f'\n  {BREAKOUTS_OUT.name} ({len(breakouts_df)} rows)'
          f'\n  {FUNNEL_OUT.name}', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
