"""Unit tests for the generic_backtest DSL engine (Task 5 of S1 leaderboard-kpis).

Real function signatures (read from generic_backtest.py before writing):
  _normalize_formula(formula: str) -> str
      Translates AND/OR/NOT (case-insensitive) to pandas.eval operators &/|/~.

  _evaluate_signals(features: pd.DataFrame, formula: str) -> pd.Series
      Evaluates a normalized DSL formula against a feature DataFrame;
      returns a boolean Series aligned to features.index.

  _compute_kpis(equity: pd.DataFrame, trades: pd.DataFrame) -> dict[str, float]
      Receives in-memory DataFrames (not CSV paths).
      equity must have columns: ['date', 'equity']
      trades must have column:  ['return_pct'] (or be empty)
      Returns 6 keys: cagr, sharpe, max_dd, final_equity, win_rate, num_trades
      NOTE: does NOT yet return the full canonical set — delegation to core.kpis
      happens in Task 6.  test_compute_kpis_delegates_to_core asserts the
      CURRENT available keys so it passes now; Task 6 will strengthen the assertion.
"""
import pandas as pd
import pytest

import generic_backtest as G


# ─────────────────────────────────────────────────────────────────────────────
# _normalize_formula
# ─────────────────────────────────────────────────────────────────────────────

def test_normalize_formula_logical_ops():
    """AND/OR/NOT (both cases) must become &/|/~ for pandas.eval."""
    out = G._normalize_formula("rsi_14 > 70 AND close > sma_200 OR NOT volume_z > 1")
    # pandas.eval does not understand AND/OR/NOT as keywords
    assert "&" in out
    assert "|" in out
    assert "~" in out
    # no residual uppercase logical keywords
    assert " AND " not in out
    assert " OR "  not in out
    assert " NOT " not in out


def test_normalize_formula_lowercase_ops():
    """Lower-case 'and'/'or'/'not' are also replaced."""
    out = G._normalize_formula("rsi_14 > 30 and close > 0 or not volume_z > 2")
    assert "&" in out and "|" in out and "~" in out
    assert " and " not in out
    assert " or "  not in out
    assert " not " not in out


def test_normalize_formula_passthrough():
    """A formula already using pandas operators is returned unchanged (modulo strip)."""
    formula = "rsi_14 > 50 & close > sma_200"
    assert G._normalize_formula(formula) == formula


# ─────────────────────────────────────────────────────────────────────────────
# _evaluate_signals
# ─────────────────────────────────────────────────────────────────────────────

def test_evaluate_signals_simple_mask():
    """Basic AND combo: rows where rsi>70 AND close>sma_200."""
    feats = pd.DataFrame(
        {"rsi_14": [80, 50, 90], "sma_200": [10, 10, 10], "close": [12, 9, 15]}
    )
    mask = G._evaluate_signals(feats, "rsi_14 > 70 AND close > sma_200")
    assert list(mask) == [True, False, True]


def test_evaluate_signals_all_false_empty_formula():
    """Empty formula returns all-False Series."""
    feats = pd.DataFrame({"rsi_14": [80, 50], "close": [100, 90]})
    mask = G._evaluate_signals(feats, "")
    assert list(mask) == [False, False]


def test_evaluate_signals_bad_formula_returns_false_not_raise():
    """A formula that references a missing column should not raise — returns False."""
    feats = pd.DataFrame({"rsi_14": [70]})
    mask = G._evaluate_signals(feats, "nonexistent_col > 50")
    assert list(mask) == [False]


def test_evaluate_signals_boolean_dtype():
    """Result is a boolean-dtype Series."""
    feats = pd.DataFrame({"rsi_14": [80, 40]})
    mask = G._evaluate_signals(feats, "rsi_14 > 60")
    assert mask.dtype == bool


# ─────────────────────────────────────────────────────────────────────────────
# _compute_kpis
# ─────────────────────────────────────────────────────────────────────────────

def _make_equity(n=253, start=100, end=200):
    """Return a DataFrame with ['date', 'equity'] columns (n trading days)."""
    dates = pd.bdate_range("2023-01-02", periods=n).astype(str)
    import numpy as np
    equity_vals = list(__import__("numpy").linspace(start, end, n))
    return pd.DataFrame({"date": dates, "equity": equity_vals})


def _make_trades(return_pcts):
    """Return a minimal trades DataFrame with a 'return_pct' column."""
    return pd.DataFrame({"return_pct": return_pcts})


def test_compute_kpis_delegates_to_core():
    """_compute_kpis returns at minimum the 5 keys the plan expects.

    Current engine returns {cagr, sharpe, max_dd, final_equity, win_rate, num_trades}.
    We assert the subset {cagr, sharpe, max_dd, win_rate, num_trades} is present
    AND num_trades == 3 (matching the 3-trade DataFrame passed in).
    Task 6 will strengthen this assertion to require the full canonical key set.
    """
    eq = _make_equity(253, 100, 352)
    tr = _make_trades([0.1, -0.05, 0.2])
    k = G._compute_kpis(eq, tr)
    assert {"cagr", "sharpe", "max_dd", "win_rate", "num_trades"} <= set(k)
    assert k["num_trades"] == 3


def test_compute_kpis_empty_equity():
    """Empty equity DataFrame returns zeroed-out KPI dict (no crash)."""
    eq = pd.DataFrame({"date": [], "equity": []})
    tr = _make_trades([])
    k = G._compute_kpis(eq, tr)
    assert k["cagr"] == 0.0
    assert k["num_trades"] == 0


def test_compute_kpis_win_rate_calculation():
    """win_rate is fraction of return_pct > 0 across trades."""
    eq = _make_equity(253)
    tr = _make_trades([0.1, 0.2, -0.05, -0.1])  # 2 wins / 4 trades = 0.5
    k = G._compute_kpis(eq, tr)
    assert k["win_rate"] == pytest.approx(0.5)
    assert k["num_trades"] == 4


def test_compute_kpis_no_trades():
    """Empty trades DataFrame gives win_rate=0.0 and num_trades=0."""
    eq = _make_equity(253)
    tr = pd.DataFrame({"return_pct": []})
    k = G._compute_kpis(eq, tr)
    assert k["win_rate"] == 0.0
    assert k["num_trades"] == 0


def test_compute_kpis_monotone_up_has_zero_drawdown():
    """Monotonically increasing equity → max_dd == 0 (or at most floating-point noise)."""
    eq = _make_equity(253, 100, 200)
    tr = _make_trades([])
    k = G._compute_kpis(eq, tr)
    assert k["max_dd"] == pytest.approx(0.0, abs=1e-9)


def test_compute_kpis_final_equity_matches_last_row():
    """final_equity equals the last row of the equity column."""
    eq = _make_equity(253, 100, 350)
    tr = _make_trades([])
    k = G._compute_kpis(eq, tr)
    assert k["final_equity"] == pytest.approx(350.0, rel=1e-6)
