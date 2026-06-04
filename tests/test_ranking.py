# tests/test_ranking.py
import pytest
from core import ranking as R


def _k(id, cagr, sharpe, max_dd, alpha, win_rate):
    return {"id": id, "cagr": cagr, "sharpe": sharpe, "max_dd": max_dd,
            "alpha": alpha, "win_rate": win_rate}


def test_empty_input():
    assert R.rank_strategies([]) == []


def test_single_strategy_rank1():
    out = R.rank_strategies([_k("a", 0.2, 1.0, -0.1, 0.05, 0.6)])
    assert out[0]["id"] == "a" and out[0]["rank"] == 1


def test_orders_by_blend_three_cohort():
    # 'best' dominates every metric -> rank 1
    best = _k("best", 0.30, 2.0, -0.05, 0.15, 0.70)
    mid = _k("mid", 0.20, 1.0, -0.10, 0.08, 0.55)
    worst = _k("worst", 0.05, 0.2, -0.30, -0.02, 0.40)
    out = {r["id"]: r["rank"] for r in R.rank_strategies([mid, worst, best])}
    assert out["best"] == 1 and out["worst"] == 3


def test_max_dd_sign_flip_rewards_smaller_drawdown():
    a = _k("a", 0.10, 1.0, -0.05, 0.0, 0.5)   # smaller DD
    b = _k("b", 0.10, 1.0, -0.40, 0.0, 0.5)   # bigger DD
    c = _k("c", 0.10, 1.0, -0.20, 0.0, 0.5)
    out = {r["id"]: r["rank"] for r in R.rank_strategies([a, b, c])}
    assert out["a"] < out["b"]                 # a ranks better


def test_missing_metric_imputed_not_punished():
    # 'm' has win_rate=None; should be imputed (z=0), weight renormalized
    m = _k("m", 0.25, 1.5, -0.08, 0.10, None)
    n = _k("n", 0.25, 1.5, -0.08, 0.10, 0.30)
    o = _k("o", 0.25, 1.5, -0.08, 0.10, 0.90)
    res = {r["id"]: r for r in R.rank_strategies([m, n, o])}
    assert res["m"]["components"]["win_rate"]["imputed"] is True


def test_small_cohort_fallback_sharpe_then_cagr():
    a = _k("a", 0.10, 2.0, -0.1, 0.0, 0.5)
    b = _k("b", 0.40, 1.0, -0.1, 0.0, 0.5)
    out = {r["id"]: r["rank"] for r in R.rank_strategies([a, b])}   # N=2 < min_cohort
    assert out["a"] == 1                                            # higher sharpe wins
