import numpy as np
import pandas as pd
import pytest
from core import kpis as K


def _equity_csv(tmp_path, name, dates, values, col="equity", extra=None):
    d = {"Date": dates, col: values}
    if extra:
        d.update(extra)
    p = tmp_path / name
    pd.DataFrame(d).to_csv(p, index=False)
    return p


def test_resolve_equity_col_explicit_and_candidates(tmp_path):
    p = _equity_csv(tmp_path, "a.csv", ["2024-01-01"], [100.0], col="Portfolio_Value")
    df = pd.read_csv(p)
    assert K.resolve_equity_col(df) == "Portfolio_Value"
    assert K.resolve_equity_col(df, equity_col="Portfolio_Value") == "Portfolio_Value"


def test_resolve_equity_col_first_numeric_fallback(tmp_path):
    df = pd.DataFrame({"Date": ["2024-01-01"], "weird_name": [100.0]})
    assert K.resolve_equity_col(df) == "weird_name"


def test_resolve_equity_col_missing_raises():
    df = pd.DataFrame({"Date": ["2024-01-01"], "label": ["x"]})
    with pytest.raises(K.KpiError):
        K.resolve_equity_col(df)


def test_equity_metrics_known_curve(tmp_path):
    # 253 daily points doubling 100 -> 200 over ~1 trading year
    dates = pd.bdate_range("2023-01-02", periods=253)
    vals = np.linspace(100.0, 200.0, 253)
    p = _equity_csv(tmp_path, "eq.csv", dates.astype(str), vals)
    m = K.compute_kpis(str(p))
    assert m["total_return"] == pytest.approx(1.0, rel=1e-6)
    assert m["cagr"] == pytest.approx(1.0, rel=0.1)        # ~1 year, ~100% -> ~1.0
    assert m["max_dd"] == pytest.approx(0.0, abs=1e-9)     # monotonic up
    assert m["final_equity"] == pytest.approx(200.0)
    assert m["sharpe"] > 0


def test_max_dd_negative_on_drawdown(tmp_path):
    dates = pd.bdate_range("2023-01-02", periods=4).astype(str)
    p = _equity_csv(tmp_path, "dd.csv", dates, [100.0, 120.0, 60.0, 90.0])
    m = K.compute_kpis(str(p))
    assert m["max_dd"] == pytest.approx((60.0 - 120.0) / 120.0)   # -0.5


def test_missing_equity_raises(tmp_path):
    with pytest.raises(K.KpiError):
        K.compute_kpis(str(tmp_path / "nope.csv"))


# ---------------------------------------------------------------------------
# Task 2: win_rate + alpha
# ---------------------------------------------------------------------------

def _trades_csv(tmp_path, name, **cols):
    p = tmp_path / name
    pd.DataFrame(cols).to_csv(p, index=False)
    return p


def test_win_rate_from_pnl_pct(tmp_path):
    eq = _equity_csv(tmp_path, "e.csv", pd.bdate_range("2023-01-02", periods=10).astype(str),
                     np.linspace(100, 110, 10))
    tr = _trades_csv(tmp_path, "t.csv", PnL_Pct=[5.0, -2.0, 3.0, -1.0])  # 2/4 wins
    m = K.compute_kpis(str(eq), str(tr))
    assert m["num_trades"] == 4
    assert m["win_rate"] == pytest.approx(0.5)


def test_win_rate_from_return_pct_fraction(tmp_path):
    eq = _equity_csv(tmp_path, "e2.csv", pd.bdate_range("2023-01-02", periods=10).astype(str),
                     np.linspace(100, 110, 10))
    tr = _trades_csv(tmp_path, "t2.csv", return_pct=[0.05, 0.02, -0.10])  # 2/3 wins
    m = K.compute_kpis(str(eq), str(tr))
    assert m["win_rate"] == pytest.approx(2 / 3)


def test_win_rate_from_result_strings(tmp_path):
    eq = _equity_csv(tmp_path, "e3.csv", pd.bdate_range("2023-01-02", periods=10).astype(str),
                     np.linspace(100, 110, 10))
    tr = _trades_csv(tmp_path, "t3.csv", Result=["WIN", "LOSS", "WIN", "WIN"])
    m = K.compute_kpis(str(eq), str(tr))
    assert m["win_rate"] == pytest.approx(0.75)


def test_win_rate_none_without_pnl(tmp_path):
    # Monthly rotation: rebalance log has no per-trade pnl
    eq = _equity_csv(tmp_path, "e4.csv", pd.bdate_range("2023-01-02", periods=10).astype(str),
                     np.linspace(100, 110, 10))
    tr = _trades_csv(tmp_path, "t4.csv", Top5_Stocks=["A,B", "C,D"])
    m = K.compute_kpis(str(eq), str(tr))
    assert m["win_rate"] is None
    assert m["num_trades"] == 2


def test_win_rate_none_without_trades_file(tmp_path):
    eq = _equity_csv(tmp_path, "e5.csv", pd.bdate_range("2023-01-02", periods=10).astype(str),
                     np.linspace(100, 110, 10))
    m = K.compute_kpis(str(eq))
    assert m["win_rate"] is None and m["num_trades"] == 0


def test_alpha_from_injected_benchmark(tmp_path):
    dates = pd.bdate_range("2023-01-02", periods=253)
    eq = _equity_csv(tmp_path, "e6.csv", dates.astype(str), np.linspace(100, 200, 253))  # ~+100%
    bench = pd.Series(np.linspace(100, 150, 253), index=pd.to_datetime(dates))           # ~+50%
    m = K.compute_kpis(str(eq), benchmark_loader=lambda: bench)
    assert m["alpha"] is not None
    assert m["alpha"] == pytest.approx(m["cagr"] - 0.5, abs=0.12)   # strat cagr - bench cagr


def test_alpha_from_embedded_benchmark_col(tmp_path):
    dates = pd.bdate_range("2023-01-02", periods=253).astype(str)
    eq = _equity_csv(tmp_path, "e7.csv", dates, np.linspace(100, 200, 253),
                     extra={"Benchmark_Value": np.linspace(100, 150, 253)})
    m = K.compute_kpis(str(eq), benchmark_col="Benchmark_Value")
    assert m["alpha"] is not None


def test_periods_per_year_handles_degenerate_spacing():
    import pandas as pd
    idx = pd.to_datetime(["2024-01-01", "2024-01-01"])   # zero spacing
    assert K._periods_per_year(idx) == 252.0
