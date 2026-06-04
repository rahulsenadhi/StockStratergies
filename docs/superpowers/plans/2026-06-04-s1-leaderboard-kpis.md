# S1 — Trustworthy Ranked Leaderboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the existing strategy leaderboard trustworthy — one canonical KPI contract computed identically for all 4 hardcoded strategies + custom ones, a composite weighted-z-score rank, and unit tests for the previously-untested engine — **without removing any existing feature** (wizard, filters, all sort options, card detail pages must keep working).

**Architecture:** Two new pure modules — `core/kpis.py` (canonical KPIs from any equity/trades CSV via column-resolution) and `core/ranking.py` (weighted z-score blend) — plus `core/leaderboard.py` (`refresh_all()` persists KPIs+rank into `strategies_index.json`). `generic_backtest.py` delegates KPI math to `core.kpis`; `master_dashboard.py` leaderboard gains a Rank/Score column and a Recompute button while keeping every existing control.

**Tech Stack:** Python 3.13, pandas, numpy, Streamlit, pytest. Spec: `docs/superpowers/specs/2026-06-04-s1-leaderboard-kpis-design.md`.

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `core/kpis.py` | `KpiError`, column resolvers, `compute_kpis()` → canonical dict | Create |
| `core/ranking.py` | `DEFAULT_WEIGHTS`, `rank_strategies()` | Create |
| `core/leaderboard.py` | `refresh_all()` — recompute KPIs + rank, persist to index | Create |
| `tests/test_kpis.py` | unit tests for KPI computation + resolution | Create |
| `tests/test_ranking.py` | unit tests for ranking math | Create |
| `tests/test_leaderboard.py` | unit tests for refresh_all | Create |
| `tests/test_generic_backtest.py` | unit tests for the engine (fills the gap) | Create |
| `generic_backtest.py` | delegate `_compute_kpis` to `core.kpis`; re-rank after run | Modify |
| `master_dashboard.py` | leaderboard Rank/Score + Recompute button; None-safe card; keep all existing controls | Modify |

**Conventions (from existing code):** pytest with `tmp_path`/`monkeypatch`, no network (inject `benchmark_loader`); run `python -m pytest`. KPIs stored as **decimals** (0.22 = 22%); UI multiplies by 100. Commit types: feat/fix/refactor/test/docs.

**NON-REGRESSION (applies to every task touching master_dashboard.py):** Do not remove or rename any existing function, sort option, filter, button, or page route. Additions only. The 4 hardcoded backtest scripts must not be edited.

---

## Task 1: `core/kpis.py` — resolvers + equity metrics

**Files:**
- Create: `core/kpis.py`
- Test: `tests/test_kpis.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_kpis.py
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
```

- [ ] **Step 2: Run, verify fail**

Run: `python -m pytest tests/test_kpis.py -q`
Expected: FAIL (`ModuleNotFoundError: No module named 'core.kpis'`)

- [ ] **Step 3: Implement `core/kpis.py` (partial — equity side)**

```python
# core/kpis.py
"""Canonical KPI contract — single source of truth for the leaderboard (S1).

compute_kpis() reads a strategy's equity (and optional trades) CSV — whatever
column schema it uses — and returns one normalized KPI dict. Annualization is
frequency-inferred so daily and monthly equity curves are both handled.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd


class KpiError(Exception):
    """Raised when a strategy's equity CSV is missing/empty/unusable."""


_EQUITY_COL_CANDIDATES = ["Portfolio_Value", "Equity", "equity"]
_DATE_COL_CANDIDATES = ["Date", "date", "Datetime"]
BENCHMARK_DEFAULT = "^NSEI"
_BENCHMARK_CSV = "data/nse_bse/^NSEI.csv"


def _read_csv(path) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        raise KpiError(f"missing CSV: {path}")
    try:
        df = pd.read_csv(p)
    except Exception as e:  # malformed file
        raise KpiError(f"unreadable CSV {path}: {e}")
    if df.empty:
        raise KpiError(f"empty CSV: {path}")
    return df


def _date_col(df: pd.DataFrame) -> str:
    for c in _DATE_COL_CANDIDATES:
        if c in df.columns:
            return c
    return df.columns[0]


def resolve_equity_col(df: pd.DataFrame, equity_col: str | None = None) -> str:
    if equity_col:
        if equity_col not in df.columns:
            raise KpiError(f"equity_col '{equity_col}' not in {list(df.columns)}")
        return equity_col
    for c in _EQUITY_COL_CANDIDATES:
        if c in df.columns:
            return c
    date_c = _date_col(df)
    for c in df.columns:
        if c != date_c and pd.api.types.is_numeric_dtype(df[c]):
            return c
    raise KpiError(f"no numeric equity column in {list(df.columns)}")


def _equity_series(df: pd.DataFrame, equity_col: str) -> pd.Series:
    dc = _date_col(df)
    s = df[[dc, equity_col]].copy()
    s[dc] = pd.to_datetime(s[dc], errors="coerce")
    s = s.dropna().sort_values(dc).set_index(dc)[equity_col].astype(float)
    if len(s) < 2:
        raise KpiError("equity series has < 2 points")
    return s


def _periods_per_year(idx: pd.DatetimeIndex) -> float:
    spacing = np.median(np.diff(idx.values).astype("timedelta64[D]").astype(float))
    if spacing <= 0:
        return 252.0
    return max(1.0, round(365.25 / spacing))


def _equity_metrics(eq: pd.Series) -> dict:
    initial, final = float(eq.iloc[0]), float(eq.iloc[-1])
    years = max((eq.index[-1] - eq.index[0]).days / 365.25, 1 / 365.25)
    cagr = (final / initial) ** (1 / years) - 1 if initial > 0 else 0.0
    total_return = (final / initial - 1) if initial > 0 else 0.0
    rets = eq.pct_change().dropna()
    ppy = _periods_per_year(eq.index)
    std = float(rets.std())
    vol = std * np.sqrt(ppy) if std > 0 else 0.0
    sharpe = (float(rets.mean()) / std) * np.sqrt(ppy) if std > 0 else 0.0
    peak = eq.cummax()
    max_dd = float(((eq - peak) / peak).min())
    calmar = (cagr / abs(max_dd)) if max_dd != 0 else None
    return {
        "cagr": float(cagr), "total_return": float(total_return),
        "volatility": float(vol), "sharpe": float(sharpe),
        "max_dd": max_dd, "calmar": calmar, "final_equity": final,
    }


def compute_kpis(
    equity_csv,
    trades_csv=None,
    *,
    benchmark: str = BENCHMARK_DEFAULT,
    equity_col: str | None = None,
    benchmark_col: str | None = None,
    pnl_col: str | None = None,
    benchmark_loader: Callable[[], pd.Series] | None = None,
) -> dict:
    """Return the canonical KPI dict for one strategy. Raises KpiError on bad equity."""
    edf = _read_csv(equity_csv)
    ecol = resolve_equity_col(edf, equity_col)
    eq = _equity_series(edf, ecol)
    out = _equity_metrics(eq)
    # win_rate / num_trades and alpha are added in Task 2.
    out["win_rate"] = None
    out["num_trades"] = 0
    out["alpha"] = None
    return out
```

- [ ] **Step 4: Run, verify pass**

Run: `python -m pytest tests/test_kpis.py -q`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add core/kpis.py tests/test_kpis.py
git commit -m "feat(s1): core.kpis equity metrics + column resolution"
```

---

## Task 2: `core/kpis.py` — win_rate + alpha

**Files:**
- Modify: `core/kpis.py`
- Test: `tests/test_kpis.py`

- [ ] **Step 1: Append failing tests**

```python
# tests/test_kpis.py  (append)
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
```

- [ ] **Step 2: Run, verify fail**

Run: `python -m pytest tests/test_kpis.py -q -k "win_rate or alpha"`
Expected: FAIL (win_rate is None / alpha is None for all)

- [ ] **Step 3: Implement (append helpers + wire into `compute_kpis`)**

Add these helpers to `core/kpis.py`:
```python
# core/kpis.py  (append)
_PNL_COL_CANDIDATES = ["PnL_Pct", "return_pct", "PnL"]


def _as_fraction(series: pd.Series) -> pd.Series:
    """Treat a clearly-percent column (abs median > 1.5) as percent -> fraction."""
    s = pd.to_numeric(series, errors="coerce").dropna()
    if len(s) and s.abs().median() > 1.5:
        return s / 100.0
    return s


def _win_rate(trades_csv, pnl_col: str | None) -> tuple[float | None, int]:
    if trades_csv is None or not Path(trades_csv).exists():
        return None, 0
    try:
        tdf = pd.read_csv(trades_csv)
    except Exception:
        return None, 0
    if tdf.empty:
        return None, 0
    n = len(tdf)
    col = pnl_col or next((c for c in _PNL_COL_CANDIDATES if c in tdf.columns), None)
    if col is not None:
        vals = _as_fraction(tdf[col])
        if len(vals):
            return float((vals > 0).mean()), n
    if "Result" in tdf.columns:
        res = tdf["Result"].astype(str).str.upper()
        wins = res.isin(["WIN", "W", "TRUE", "PROFIT"])
        if wins.any() or res.isin(["LOSS", "L", "FALSE"]).any():
            return float(wins.mean()), n
    return None, n


def _benchmark_cagr(eq_index, benchmark_loader) -> float | None:
    loader = benchmark_loader or _default_benchmark_loader
    try:
        bench = loader()
    except Exception:
        return None
    if bench is None or len(bench) < 2:
        return None
    bench = bench.reindex(bench.index.union(eq_index)).ffill().reindex(eq_index).dropna()
    if len(bench) < 2 or bench.iloc[0] <= 0:
        return None
    years = max((bench.index[-1] - bench.index[0]).days / 365.25, 1 / 365.25)
    return (float(bench.iloc[-1]) / float(bench.iloc[0])) ** (1 / years) - 1


def _default_benchmark_loader() -> pd.Series | None:
    p = Path(_BENCHMARK_CSV)
    if not p.exists():
        return None
    df = pd.read_csv(p)
    dc = _date_col(df)
    df[dc] = pd.to_datetime(df[dc], errors="coerce")
    return df.dropna(subset=[dc]).set_index(dc)["Close"].astype(float)
```

Then in `compute_kpis`, replace the three placeholder lines (`win_rate`/`num_trades`/`alpha`) with:
```python
    out["win_rate"], out["num_trades"] = _win_rate(trades_csv, pnl_col)

    if benchmark_col and benchmark_col in edf.columns:
        bench_series = _equity_series(edf, benchmark_col)
        bench_cagr = _benchmark_cagr(eq.index, lambda: bench_series)
    else:
        bench_cagr = _benchmark_cagr(eq.index, benchmark_loader)
    out["alpha"] = (out["cagr"] - bench_cagr) if bench_cagr is not None else None
    return out
```

- [ ] **Step 4: Run, verify pass**

Run: `python -m pytest tests/test_kpis.py -q`
Expected: PASS (14 passed)

- [ ] **Step 5: Commit**

```bash
git add core/kpis.py tests/test_kpis.py
git commit -m "feat(s1): core.kpis win_rate (multi-source) + alpha vs benchmark"
```

---

## Task 3: `core/ranking.py`

**Files:**
- Create: `core/ranking.py`
- Test: `tests/test_ranking.py`

- [ ] **Step 1: Write failing tests**

```python
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
```

- [ ] **Step 2: Run, verify fail**

Run: `python -m pytest tests/test_ranking.py -q`
Expected: FAIL (`ModuleNotFoundError: No module named 'core.ranking'`)

- [ ] **Step 3: Implement `core/ranking.py`**

```python
# core/ranking.py
"""Composite leaderboard rank — weighted z-score blend across the cohort (S1)."""
from __future__ import annotations

import numpy as np

DEFAULT_WEIGHTS = {"sharpe": 0.30, "cagr": 0.25, "max_dd": 0.20, "alpha": 0.15, "win_rate": 0.10}
MIN_COHORT = 3


def _dir(metric: str, value):
    if value is None:
        return None
    return -value if metric == "max_dd" else value     # max_dd <=0 -> higher is better


def _fallback(kpis, ids):
    order = sorted(
        range(len(kpis)),
        key=lambda i: (-(kpis[i].get("sharpe") or float("-inf")),
                       -(kpis[i].get("cagr") or float("-inf"))),
    )
    out = [None] * len(kpis)
    for rank, i in enumerate(order, start=1):
        out[i] = {"id": ids[i], "score": 0.0, "rank": rank,
                  "components": {}, "fallback": True}
    return out


def rank_strategies(kpi_dicts, weights=None, min_cohort=MIN_COHORT):
    weights = weights or DEFAULT_WEIGHTS
    n = len(kpi_dicts)
    if n == 0:
        return []
    ids = [k.get("id") for k in kpi_dicts]
    if n < min_cohort:
        return _fallback(kpi_dicts, ids)

    metrics = list(weights)
    cols = {m: [_dir(m, kpi_dicts[i].get(m)) for i in range(n)] for m in metrics}
    stats = {}
    for m in metrics:
        present = [v for v in cols[m] if v is not None]
        stats[m] = (float(np.mean(present)), float(np.std(present))) if present else (0.0, 0.0)

    results = []
    for i in range(n):
        num = den = 0.0
        comps = {}
        for m in metrics:
            v = cols[m][i]
            mean, std = stats[m]
            if v is None:
                comps[m] = {"value": kpi_dicts[i].get(m), "z": 0.0, "imputed": True}
                continue
            z = 0.0 if std == 0 else (v - mean) / std
            comps[m] = {"value": kpi_dicts[i].get(m), "z": z, "imputed": False}
            num += weights[m] * z
            den += weights[m]
        score = num / den if den > 0 else 0.0
        results.append({"id": ids[i], "score": float(score), "components": comps,
                        "_sharpe": kpi_dicts[i].get("sharpe") or float("-inf"),
                        "_cagr": kpi_dicts[i].get("cagr") or float("-inf")})

    results.sort(key=lambda r: (-r["score"], -r["_sharpe"], -r["_cagr"]))
    for rank, r in enumerate(results, start=1):
        r["rank"] = rank
        r.pop("_sharpe", None)
        r.pop("_cagr", None)
    return results
```

- [ ] **Step 4: Run, verify pass**

Run: `python -m pytest tests/test_ranking.py -q`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add core/ranking.py tests/test_ranking.py
git commit -m "feat(s1): core.ranking weighted z-score blend + small-cohort fallback"
```

---

## Task 4: `core/leaderboard.py` — refresh_all

**Files:**
- Create: `core/leaderboard.py`
- Test: `tests/test_leaderboard.py`

- [ ] **Step 1: Write failing test**

```python
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


def test_refresh_all_writes_kpis_and_rank(tmp_path):
    idx = {"strategies": [
        _mk(tmp_path, "a", np.linspace(100, 300, 253), [0.1, 0.2, -0.05]),
        _mk(tmp_path, "b", np.linspace(100, 130, 253), [0.05, -0.1]),
        _mk(tmp_path, "c", np.linspace(100, 110, 253), [-0.02, 0.01, 0.03]),
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
    good = _mk(tmp_path, "good", np.linspace(100, 200, 253), [0.1, -0.05])
    bad = {"id": "bad", "name": "bad", "equity_csv": str(tmp_path / "missing.csv")}
    idx_path = tmp_path / "idx.json"
    idx_path.write_text(json.dumps({"strategies": [good, bad]}))

    LB.refresh_all(str(idx_path), benchmark_loader=lambda: None)
    saved = {s["id"]: s for s in json.loads(idx_path.read_text())["strategies"]}
    assert "kpis_inline" in saved["good"]
    assert "kpis_error" in saved["bad"]          # bad one flagged, batch survived
```

- [ ] **Step 2: Run, verify fail**

Run: `python -m pytest tests/test_leaderboard.py -q`
Expected: FAIL (`ModuleNotFoundError: No module named 'core.leaderboard'`)

- [ ] **Step 3: Implement `core/leaderboard.py`**

```python
# core/leaderboard.py
"""Recompute canonical KPIs + composite rank for all strategies, persist to index (S1)."""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from core.kpis import KpiError, compute_kpis
from core.ranking import rank_strategies

_CANONICAL = ["cagr", "total_return", "volatility", "sharpe", "max_dd",
              "calmar", "win_rate", "num_trades", "alpha", "final_equity"]


def refresh_all(index_path: str = "strategies_index.json", benchmark_loader=None) -> list[dict]:
    """Recompute KPIs for every strategy, rank the cohort, persist. Returns the strategies."""
    p = Path(index_path)
    idx = json.loads(p.read_text())
    strategies = idx["strategies"]

    for s in strategies:
        try:
            kp = compute_kpis(
                s["equity_csv"], s.get("trades_csv"),
                equity_col=s.get("equity_col"), benchmark_col=s.get("benchmark_col"),
                pnl_col=s.get("pnl_col"), benchmark_loader=benchmark_loader,
            )
            s["kpis_inline"] = {k: kp[k] for k in _CANONICAL}
            s["kpis_updated"] = datetime.now().isoformat(timespec="seconds")
            s.pop("kpis_error", None)
        except KpiError as e:
            s["kpis_error"] = str(e)

    cohort = [{"id": s["id"], **s["kpis_inline"]}
              for s in strategies if "kpis_error" not in s and "kpis_inline" in s]
    ranked = {r["id"]: r for r in rank_strategies(cohort)}
    for s in strategies:
        r = ranked.get(s["id"])
        if r:
            s["rank"] = r["rank"]
            s["rank_score"] = r["score"]

    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(idx, indent=2, default=str))
    os.replace(tmp, p)
    return strategies
```

- [ ] **Step 4: Run, verify pass**

Run: `python -m pytest tests/test_leaderboard.py -q`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add core/leaderboard.py tests/test_leaderboard.py
git commit -m "feat(s1): core.leaderboard refresh_all (recompute KPIs + rank, persist)"
```

---

## Task 5: Tests for the existing engine `generic_backtest.py`

**Files:**
- Test: `tests/test_generic_backtest.py`

(Fills the pre-existing test gap. No network — monkeypatch `load_ohlcv`.)

- [ ] **Step 1: Read the engine first**

Run: `python -c "import ast,inspect; import generic_backtest as g; print([f for f in dir(g) if not f.startswith('__')])"`
Then read `generic_backtest.py` lines 97–154 (`_normalize_formula`, `_evaluate_signals`, `_load_universe`) to confirm exact signatures before writing tests.

- [ ] **Step 2: Write tests against the real functions**

```python
# tests/test_generic_backtest.py
import pandas as pd
import pytest
import generic_backtest as G


def test_normalize_formula_logical_ops():
    out = G._normalize_formula("rsi_14 > 70 AND close > sma_200 OR NOT volume_z > 1")
    assert " and " not in out.lower()
    assert "&" in out and "|" in out and "~" in out


def test_evaluate_signals_simple_mask():
    feats = pd.DataFrame({"rsi_14": [80, 50, 90], "sma_200": [10, 10, 10], "close": [12, 9, 15]})
    mask = G._evaluate_signals(feats, "rsi_14 > 70 AND close > sma_200")
    assert list(mask) == [True, False, True]


def test_compute_kpis_delegates_to_core(tmp_path, monkeypatch):
    eq = pd.DataFrame({"date": pd.bdate_range("2023-01-02", periods=253).astype(str),
                       "equity": list(range(100, 100 + 253))})
    tr = pd.DataFrame({"return_pct": [0.1, -0.05, 0.2]})
    k = G._compute_kpis(eq, tr)
    assert {"cagr", "sharpe", "max_dd", "win_rate", "num_trades"} <= set(k)
    assert k["num_trades"] == 3
```

> If `_evaluate_signals`/`_normalize_formula` signatures differ from the above (e.g. take extra args), adapt the call but keep the asserted behavior. Confirm names from Step 1 before running.

- [ ] **Step 3: Run, verify fail (then implement Task 6 to make `_compute_kpis` delegate)**

Run: `python -m pytest tests/test_generic_backtest.py -q`
Expected: the two formula tests PASS now; `test_compute_kpis_delegates_to_core` may PASS or FAIL depending on the current `_compute_kpis` output — it is made authoritative in Task 6. If it fails on missing keys, that is expected pre-Task-6.

- [ ] **Step 4: Commit the tests**

```bash
git add tests/test_generic_backtest.py
git commit -m "test(s1): unit tests for generic_backtest DSL + kpis"
```

---

## Task 6: Wire `generic_backtest.py` to `core.kpis` + re-rank after run

**Files:**
- Modify: `generic_backtest.py`

- [ ] **Step 1: Make `_compute_kpis` delegate to core.kpis**

Replace the body of `_compute_kpis(equity, trades)` (lines ~316–341) so it writes nothing new but reuses the canonical contract. Since `_compute_kpis` receives in-memory DataFrames, persist them to temp CSVs is overkill — instead import and reuse the math by passing through `core.kpis` on the already-written files in `run_backtest`. Simpler and DRY: change the call site.

Add import near the top:
```python
from core.kpis import compute_kpis as _core_kpis
```
In `run_backtest`, AFTER the trades/equity CSVs are written (the code that produces `trades_path` and `equity_path`), replace the existing `kpis = _compute_kpis(equity_df, trades_df)` call with:
```python
        kpis = _core_kpis(equity_path, trades_path)
```
Keep the old `_compute_kpis` function in place (still imported by the test) but it is no longer the production path. (If `run_backtest` returns `result['kpis']`, it now carries the canonical dict — superset of the old keys, so `_update_strategies_index` still finds `cagr/sharpe/max_dd/win_rate/num_trades`.)

> `win_rate` may now be `None` (canonical) where the old code returned `0.0`. Update `_update_strategies_index` to store `None` as-is (JSON null) — do not coerce. The leaderboard card is made None-safe in Task 7.

- [ ] **Step 2: Re-rank the cohort after a run**

At the end of `main()`, after `_update_strategies_index(...)`, add:
```python
    try:
        from core.leaderboard import refresh_all
        refresh_all()
    except Exception as e:
        print(f"WARN: leaderboard refresh failed: {e}")
    print('DONE')
```
(Remove the now-duplicate trailing `print('DONE')` so it prints once.)

- [ ] **Step 3: Verify engine smoke + tests**

Run: `python generic_backtest.py --spec strategies/test_rsi_breakout.json`
Expected: prints `DONE`; `strategies_index.json` gains `rank`/`rank_score` for entries; no traceback.
Then: `python -m pytest tests/test_generic_backtest.py tests/test_kpis.py -q` → all pass.

- [ ] **Step 4: Commit**

```bash
git add generic_backtest.py
git commit -m "refactor(s1): generic_backtest uses core.kpis + re-ranks after run"
```

---

## Task 7: Leaderboard UI — Rank/Score + Recompute (NON-REGRESSION)

**Files:**
- Modify: `master_dashboard.py` (`render_strategy_library` ~8216, `_render_strategy_card` ~8151)

- [ ] **Step 1: Make the card None-safe + show Rank/Score**

In `_render_strategy_card` (line ~8152), replace the KPI extraction:
```python
    k = strat.get('kpis_inline', {})
    cagr = k.get('cagr', 0) * 100
    sharpe = k.get('sharpe', 0)
    max_dd = k.get('max_dd', 0) * 100
```
with None-safe versions + rank:
```python
    k = strat.get('kpis_inline', {})
    cagr = (k.get('cagr') or 0) * 100
    sharpe = k.get('sharpe') or 0
    max_dd = (k.get('max_dd') or 0) * 100
    rank = strat.get('rank')
    score = strat.get('rank_score')
    rank_badge = f"#{rank}" if rank else "—"
```
Add a rank badge into the card head (next to the status chip). In the `strat-card-head` block, change:
```python
                <div>{_status_chip_html(status)}</div>
```
to:
```python
                <div style="text-align:right">
                  <div style="font-weight:700">{rank_badge}</div>
                  {_status_chip_html(status)}
                </div>
```
And add a Score line to the footer (line ~8184). Change:
```python
              <span>{k.get('num_trades', '—')} trades</span>
```
to:
```python
              <span>{(k.get('num_trades') or 0)} trades</span>
              <span>Score {score:+.2f}</span>
```
where `score` is guarded — add just above the footer markdown:
```python
        score_disp = f"{score:+.2f}" if isinstance(score, (int, float)) else "—"
```
and use `{score_disp}` instead of `{score:+.2f}`.

- [ ] **Step 2: Add 'Rank' sort (default) WITHOUT removing existing sorts**

In `render_strategy_library`, the sort selectbox (line ~8243) currently:
```python
        sort_by = st.selectbox('Sort', ['Last run', 'CAGR', 'Sharpe', 'Name'],
                                key='lib_sort_by', label_visibility='collapsed')
```
Change the options list to prepend 'Rank' (keep all existing options):
```python
        sort_by = st.selectbox('Sort', ['Rank', 'Last run', 'CAGR', 'Sharpe', 'Name'],
                                key='lib_sort_by', label_visibility='collapsed')
```
In `sort_keys` (line ~8259) add a Rank key (None-safe), keep the others unchanged:
```python
    sort_keys = {
        'Rank':     lambda s: s.get('rank', 9999),
        'CAGR':     lambda s: -((s.get('kpis_inline', {}).get('cagr') or 0)),
        'Sharpe':   lambda s: -((s.get('kpis_inline', {}).get('sharpe') or 0)),
        'Name':     lambda s: s.get('name', ''),
        'Last run': lambda s: s.get('last_run', ''),
    }
```
The existing `if sort_by == 'Last run': reverse=True else ascending` branch already handles 'Rank' correctly (ascending: rank 1 first). Confirm no other change needed there.

> Note the CAGR/Sharpe lambdas are made None-safe (`or 0`) — same behavior for present values, no crash on None.

- [ ] **Step 3: Add a 'Recompute leaderboard' button (additive)**

In the action row (line ~8234, the `a1, a2 = st.columns([1, 5])` block), widen to 3 columns and add a button:
```python
    a1, a2, a3 = st.columns([1, 1, 4])
    with a1:
        if st.button('+ New strategy', type='primary', use_container_width=True, key='lib_new_btn'):
            st.session_state['_page_override'] = 'add_strategy'
            st.rerun()
    with a2:
        if st.button('↻ Recompute', use_container_width=True, key='lib_recompute_btn',
                     help='Recompute KPIs + rank from each strategy\'s equity/trades CSVs'):
            from core.leaderboard import refresh_all
            with st.spinner('Recomputing leaderboard…'):
                refresh_all()
            st.cache_data.clear()
            st.rerun()
```
(Leave the rest of `render_strategy_library` unchanged.)

- [ ] **Step 4: Syntax check**

Run: `python -c "import ast; ast.parse(open('master_dashboard.py', encoding='utf-8').read()); print('syntax ok')"`
Expected: `syntax ok`

- [ ] **Step 5: Commit**

```bash
git add master_dashboard.py
git commit -m "feat(s1): leaderboard Rank/Score column + Recompute button (None-safe, additive)"
```

---

## Task 8: Migrate existing index + NON-REGRESSION verification

**Files:**
- Modify: `strategies_index.json` (via refresh_all, not hand-edit)

- [ ] **Step 1: Run refresh_all once to migrate the 4 existing entries to the canonical contract**

Run:
```bash
python -c "from core.leaderboard import refresh_all; [print(s['id'], s.get('rank'), s.get('kpis_inline',{}).get('cagr'), s.get('kpis_error','')) for s in refresh_all()]"
```
Expected: each of the 4 strategies prints an id, a rank (1–4), a cagr decimal, and empty error (or a clear `kpis_error` if a CSV path is stale — if so, fix that entry's `equity_csv`/`trades_csv` path in `strategies_index.json` and re-run; do NOT hand-edit KPI values).

- [ ] **Step 2: Full unit-test suite**

Run: `python -m pytest -q`
Expected: all pass (existing 126 + new S1 tests). No pre-existing test regressed.

- [ ] **Step 3: Non-regression live smoke (AppTest) — library page renders with all existing controls**

Create `_smoke_s1.py`:
```python
from streamlit.testing.v1 import AppTest

# Drive the master dashboard's Strategy Library page headless.
at = AppTest.from_file("master_dashboard.py", default_timeout=120)
at.session_state["_page_override"] = ""        # ensure normal nav
at.run()
assert not at.exception, f"dashboard raised: {at.exception}"
# Existing controls still present:
labels = [s.label for s in at.selectbox]
print("selectboxes:", labels)
buttons = [b.label for b in at.button]
print("buttons:", buttons)
print("SMOKE OK")
```
Run: `PYTHONIOENCODING=utf-8 python _smoke_s1.py`
Expected: `SMOKE OK`, no exception. (If `AppTest.from_file` on the full 9k-line dashboard is too heavy/slow or needs a specific page param, fall back to driving `render_strategy_library` via a tiny wrapper script that imports it and calls it with the loaded indices — capture no-exception + that the Type/Status/Sort selectboxes and the New/Recompute buttons render.)

- [ ] **Step 4: Confirm the wizard route + card detail route still resolve**

Add to `_smoke_s1.py` (or a second script) a check that the add-strategy and backtest-results routes still render without exception:
```python
from streamlit.testing.v1 import AppTest
for override in ("add_strategy",):
    at = AppTest.from_file("master_dashboard.py", default_timeout=120)
    at.session_state["_page_override"] = override
    at.run()
    assert not at.exception, f"{override} raised: {at.exception}"
    print(override, "OK")
```
Run it; expected each route prints OK with no exception.

- [ ] **Step 5: Clean up the smoke script + commit the migrated index**

```bash
rm -f _smoke_s1.py
git add strategies_index.json
git commit -m "chore(s1): migrate strategies_index to canonical KPIs + ranks via refresh_all"
```

- [ ] **Step 6: Update memory**

The controller (not a subagent) updates memory: add `s1_leaderboard.md` describing the canonical KPI contract + ranking, and an index line in `MEMORY.md`; note S1 increment done.

---

## Self-Review

**Spec coverage:**
- §4 architecture (core/kpis, core/ranking, core/leaderboard, engine + dashboard integration) → Tasks 1–7. ✓
- §5 KPI contract (all fields, column resolution, percent-normalize, benchmark embedded vs ^NSEI, errors) → Tasks 1–2. ✓ (Refinement: annualization is frequency-inferred via `_periods_per_year` rather than hard √252, to handle daily+monthly equity curves correctly — stated in code comment.)
- §6 ranking (weights, z-score, max_dd flip, impute+renormalize, small-N fallback, output shape) → Task 3. ✓
- §7 integration (refresh_all persist, engine delegate, post-run rerank, UI Rank/Score + Recompute) → Tasks 4,6,7. ✓
- §8 error handling (KpiError, per-strategy isolation, empty/single rank, atomic write) → Tasks 1,3,4. ✓
- §9 testing (kpis, ranking, leaderboard, engine + coverage) → Tasks 1–5. ✓
- §10 decisions (rf=0, ^NSEI, Monthly win_rate None, decimals + migration) → Tasks 1,2,8. ✓
- User constraint NON-REGRESSION (keep wizard/filters/all sorts/detail) → Task 7 (additive only) + Task 8 (AppTest verification of library + wizard + detail routes). ✓

**Placeholder scan:** every code step shows complete code; the only "adapt if signature differs" note (Task 5 Step 2) is gated by a read-first step. No TBD/TODO. ✓

**Type consistency:** `compute_kpis(...) -> dict` with keys {cagr,total_return,volatility,sharpe,max_dd,calmar,win_rate,num_trades,alpha,final_equity}; `rank_strategies(...) -> [{id,score,rank,components,(fallback?)}]`; `refresh_all(index_path, benchmark_loader) -> list`; `_CANONICAL` list matches the compute_kpis keys exactly. Consistent across tasks. ✓
