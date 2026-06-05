# tests/test_leaderboard.py
import json
import numpy as np
import pandas as pd
import pytest
from core import leaderboard as LB


def _mk(tmp_path, sid, eq_vals, trades=None):
    eq = tmp_path / f"{sid}_eq.csv"
    pd.DataFrame({"Date": pd.bdate_range("2023-01-02", periods=len(eq_vals)).astype(str),
                  "equity": eq_vals}).to_csv(eq, index=False)
    entry = {"id": sid, "name": sid, "equity_csv": str(eq)}
    if trades is not None:
        tp = tmp_path / f"{sid}_tr.csv"
        pd.DataFrame({"return_pct": trades}).to_csv(tp, index=False)
        entry["trades_csv"] = str(tp)
    return entry


def _make_equity(n, drift, vol, seed=42):
    """Generate a realistic random-walk equity curve starting at 100."""
    rng = np.random.default_rng(seed)
    returns = rng.normal(drift, vol, n)
    return 100.0 * np.cumprod(1 + returns)


def test_refresh_all_writes_kpis_and_rank(tmp_path):
    # Use realistic random-walk curves so rank ordering is deterministic.
    # 'a' has clearly superior CAGR + Sharpe; 'b' is mid; 'c' is weakest.
    idx = {"strategies": [
        _mk(tmp_path, "a", _make_equity(253, 0.003, 0.015, seed=42), [0.1, 0.2, -0.05]),
        _mk(tmp_path, "b", _make_equity(253, 0.001, 0.020, seed=43), [0.05, -0.1]),
        _mk(tmp_path, "c", _make_equity(253, 0.0003, 0.025, seed=44), [-0.02, 0.01, 0.03]),
    ]}
    idx_path = tmp_path / "strategies_index.json"
    idx_path.write_text(json.dumps(idx))

    out = LB.refresh_all(str(idx_path), benchmark_loader=lambda: None)

    saved = json.loads(idx_path.read_text())["strategies"]
    for s in saved:
        assert "cagr" in s["kpis_inline"] and "rank" in s and "rank_score" in s
    ranks = {s["id"]: s["rank"] for s in saved}
    assert ranks["a"] == 1                       # strongest curve


def test_refresh_all_isolates_bad_strategy(tmp_path):
    good = _mk(tmp_path, "good", _make_equity(253, 0.002, 0.015, seed=10), [0.1, -0.05])
    bad = {"id": "bad", "name": "bad", "equity_csv": str(tmp_path / "missing.csv")}
    idx_path = tmp_path / "idx.json"
    idx_path.write_text(json.dumps({"strategies": [good, bad]}))

    LB.refresh_all(str(idx_path), benchmark_loader=lambda: None)
    saved = {s["id"]: s for s in json.loads(idx_path.read_text())["strategies"]}
    assert "kpis_inline" in saved["good"]
    assert "kpis_error" in saved["bad"]          # bad one flagged, batch survived
