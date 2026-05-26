from datetime import date

import numpy as np
import pandas as pd
import pytest

from pead_diagnostics import compute_kpis, compute_decile_spread


def test_compute_kpis_basic():
    eq = pd.DataFrame({
        "date": pd.bdate_range("2025-01-01", periods=252),
        "equity": [1_000_000 * (1.0008 ** i) for i in range(252)],
    })
    trades = pd.DataFrame([
        {"return_pct": 5.0, "exit_reason": "60D"},
        {"return_pct": -3.0, "exit_reason": "60D"},
        {"return_pct": 8.0, "exit_reason": "NEXT_EARNINGS"},
    ])
    kpi = compute_kpis(eq, trades)
    assert kpi["cagr"] == pytest.approx(0.221, abs=0.02)
    assert kpi["win_rate"] == pytest.approx(2/3, abs=1e-3)
    assert kpi["num_trades"] == 3
    assert kpi["max_dd"] <= 0


def test_compute_decile_spread():
    events = pd.DataFrame([
        {"sue_decile": d, "ticker": f"T{i}.NS",
         "fwd_60d_return": d * 0.5}     # decile 10 -> 5%, decile 1 -> 0.5%
        for d in range(1, 11) for i in range(5)
    ])
    spread = compute_decile_spread(events)
    assert spread.loc[10] > spread.loc[1]
    assert pytest.approx(spread.loc[10], abs=0.01) == 5.0
