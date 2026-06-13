"""Tests for precompute_suggestions pure functions."""
import pandas as pd
import pytest

import precompute_suggestions as ps


# ── edge_buckets ─────────────────────────────────────────────────────────────
def _trades():
    return pd.DataFrame(
        {
            "Entry_Type": ["ATH", "ATH", "ATH", "ATH", "52W", "52W", "52W"],
            "Recovery_Speed": ["Fast", "Fast", "Fast", "Fast", "Slow", "Slow", "Slow"],
            "Result": ["Win", "Win", "Win", "Loss", "Loss", "Loss", "Win"],
            "PnL_Pct": [10.0, 12.0, 8.0, -5.0, -6.0, -4.0, 3.0],
        }
    )


def test_edge_buckets_basic():
    g = ps.edge_buckets(_trades(), ["Entry_Type", "Recovery_Speed"], min_n=3)
    assert not g.empty
    # ATH/Fast: 4 trades, 3 wins -> 75% wr, positive expectancy ranks first
    top = g.iloc[0]
    assert top["Entry_Type"] == "ATH"
    assert top["Recovery_Speed"] == "Fast"
    assert top["n"] == 4
    assert top["win_rate"] == pytest.approx(75.0)
    assert top["expectancy"] > 0
    # sorted desc by edge_score
    assert g["edge_score"].is_monotonic_decreasing


def test_edge_buckets_min_n_filters():
    g = ps.edge_buckets(_trades(), ["Entry_Type", "Recovery_Speed"], min_n=5)
    assert g.empty  # no bucket has >=5 trades


def test_edge_buckets_empty_and_missing_cols():
    assert ps.edge_buckets(None, ["X"]).empty
    assert ps.edge_buckets(pd.DataFrame(), ["X"]).empty
    # missing Result/PnL_Pct
    assert ps.edge_buckets(pd.DataFrame({"Entry_Type": ["A"]}), ["Entry_Type"]).empty


def test_edge_score_is_expectancy_times_sqrt_n():
    g = ps.edge_buckets(_trades(), ["Entry_Type", "Recovery_Speed"], min_n=3)
    row = g.iloc[0]
    assert row["edge_score"] == pytest.approx(row["expectancy"] * (row["n"] ** 0.5))


# ── build_monthly_suggestions ────────────────────────────────────────────────
def _rankings():
    return pd.DataFrame(
        {
            "Rank": [1, 2, 3],
            "Ticker": ["AAA.NS", "BBB.NS", "CCC.NS"],
            "Company": ["Aaa", "Bbb", "Ccc"],
            "Current_Price": [100.0, 200.0, 0.0],
            "Return_%": [12.0, 8.0, 5.0],
            "Benchmark_Return_%": [4.0, 4.0, 4.0],
            "RS_Score": [90.0, 80.0, 70.0],
            "Signal": ["Strong BUY", "Strong BUY", "Strong BUY"],
        }
    )


def test_monthly_picks_stop_target_position():
    out = ps.build_monthly_suggestions(_rankings(), None, is_bull=True)
    assert len(out) == 2  # CCC dropped (close<=0)
    p = out[0]
    assert p["ticker"] == "AAA"
    assert p["close"] == 100.0
    assert p["stop"] == 92.0  # x0.92
    assert p["target"] == 110.0  # x1.10
    assert p["positionPct"] == 20.0  # bull
    assert p["confidence"] == 60.0  # default (no Strategy_Value col)
    assert p["strategyId"] == "monthly_rotation"


def test_monthly_bear_halves_position():
    out = ps.build_monthly_suggestions(_rankings(), None, is_bull=False)
    assert out[0]["positionPct"] == 10.0
    assert "Bear" in out[0]["rationale"]


def test_monthly_filters_strong_buy_only():
    rk = _rankings()
    rk.loc[0, "Signal"] = "BUY"  # not Strong
    out = ps.build_monthly_suggestions(rk, None, is_bull=True)
    assert all(p["ticker"] != "AAA" for p in out)


def test_monthly_empty():
    assert ps.build_monthly_suggestions(None, None, True) == []
    assert ps.build_monthly_suggestions(pd.DataFrame(), None, True) == []


# ── build_momentum_suggestions ───────────────────────────────────────────────
def _mom_signals():
    return pd.DataFrame(
        {
            "Ticker": ["XYZ.NS"],
            "Company": ["Xyz"],
            "Signal": ["Breakout Today"],
            "Close": [100.0],
            "Entry Type": ["ATH"],
            "Recovery": ["Fast"],
            "Chart Qual": ["Clean"],
            "220 EMA": [80.0],
            "Score": [50.0],
        }
    )


def test_momentum_stop_is_looser_of_ema_or_15pct():
    out = ps.build_momentum_suggestions(_mom_signals(), _trades(), is_bull=True)
    assert len(out) == 1
    p = out[0]
    # max(85, 80) = 85
    assert p["stop"] == 85.0
    assert p["target"] == 125.0
    assert p["positionPct"] == 12.0
    # ATH/Fast bucket matched -> confidence = its 75% win rate
    assert p["confidence"] == pytest.approx(75.0)
    assert p["nHist"] == 4


def test_momentum_stop_uses_ema_when_above_15pct():
    sig = _mom_signals()
    sig.loc[0, "220 EMA"] = 95.0  # above 85 floor
    out = ps.build_momentum_suggestions(sig, _trades(), is_bull=True)
    assert out[0]["stop"] == 95.0


def test_momentum_no_trades_uses_default_confidence():
    out = ps.build_momentum_suggestions(_mom_signals(), None, is_bull=True)
    assert out[0]["confidence"] == 40.0
    assert out[0]["nHist"] == 0


def test_momentum_empty():
    assert ps.build_momentum_suggestions(None, None, True) == []


# ── compute_regime ───────────────────────────────────────────────────────────
def test_compute_regime_short_series_unknown():
    s = pd.Series([1.0, 2.0, 3.0])
    assert ps.compute_regime(s)["status"] == "Unknown"
    assert ps.compute_regime(None)["status"] == "Unknown"


def test_compute_regime_bull():
    idx = pd.date_range("2020-01-01", periods=300, freq="D")
    s = pd.Series(range(1, 301), index=idx, dtype=float)  # steadily rising -> bull
    snap = ps.compute_regime(s)
    assert snap["status"] == "Bull"
    assert snap["close"] == 300.0
    assert "sma50" in snap and "high52" in snap
    assert snap["date"] == "2020-10-26"


# ── assemble ─────────────────────────────────────────────────────────────────
def test_assemble_sorts_reranks_and_summarises():
    pools = [
        [{"edgeScore": 50.0, "confidence": 60.0, "positionPct": 20.0}],
        [{"edgeScore": 90.0, "confidence": 75.0, "positionPct": 12.0}],
    ]
    res = ps.assemble({"status": "Bull"}, pools)
    assert [p["rank"] for p in res["picks"]] == [1, 2]
    assert res["picks"][0]["edgeScore"] == 90.0  # highest first
    assert res["summary"]["picks"] == 2
    assert res["summary"]["totalAllocation"] == 32.0
    assert res["summary"]["cashReserve"] == 68.0
    assert res["summary"]["avgConfidence"] == pytest.approx(67.5)


def test_assemble_empty():
    res = ps.assemble({"status": "Bear"}, [[], []])
    assert res["summary"] == {
        "picks": 0,
        "avgConfidence": 0.0,
        "totalAllocation": 0.0,
        "cashReserve": 100.0,
    }
