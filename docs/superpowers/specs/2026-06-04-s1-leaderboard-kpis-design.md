# S1 — Trustworthy Ranked Leaderboard (Standardized KPIs + Rank Score): Design Spec

**Author:** rahulsenadhi
**Date:** 2026-06-04
**Status:** Draft
**Depends on:** existing S1 groundwork (`generic_backtest.py`, Add Strategy wizard, leaderboard/library UI, `strategies_index.json`), S0a data layer (`^NSEI` benchmark in `data/nse_bse/`).

---

## 1. Goal

The S1 skeleton (strategy factory wizard + leaderboard + generic backtest engine) already exists and is wired into `master_dashboard.py`. This increment makes the leaderboard **trustworthy and comparable**:

1. **Standardize KPIs** — one canonical KPI contract computed identically for all 4 hardcoded strategies (Monthly Rotation, IPO Edge, Momentum Edge, PEAD) and any custom/generic strategy, from their equity/trades CSVs.
2. **Composite rank score** — a single weighted z-score blend ranks strategies on the leaderboard (replaces single-column sort).
3. **Test the engine** — add the missing unit tests for `generic_backtest.py` plus the two new modules.

## 2. Non-Goals

- No change to the 4 hardcoded backtest scripts' logic — they keep emitting their own equity/trades CSVs; KPIs are recomputed centrally from those.
- No new strategies, no new engine features (next-earnings exit, PEAD factors stay deferred).
- No weight-tuning UI (weights are constants, editable in code; sliders are future/YAGNI).
- No cloud/serving changes.

## 3. Current State (verified)

- `generic_backtest.py` (384 lines): DSL engine (features rsi_14/atr_14/sma_50/sma_200/volume_z, AND/OR/NOT → &/|/~, `pandas.eval`), universe loaders, exits (time/hard-stop/trailing; next-earnings stub), `_compute_kpis` (cagr/sharpe/max_dd/win_rate/num_trades/final_equity), `_update_strategies_index`. **No unit tests.**
- 7-step Add Strategy wizard in `master_dashboard.py` (~8230–8678): saves spec JSON → subprocess `generic_backtest.py` → updates index → library.
- Leaderboard/library in `master_dashboard.py` (~8216): card grid, filter by type/status/search, **sort by single column** (CAGR/Sharpe/Name/Last run). No composite rank.
- `strategies_index.json`: 4 entries with `kpis_inline`, but values are **inconsistent** (decimals vs %, win_rate scale varies, alpha/total_return only on some).
- `core/analytics.py`: post-hoc trade analytics — NOT the leaderboard KPI source, not called by the engine.

**Equity/trades CSV schemas differ** (drives the column-resolution requirement):

| Strategy | Equity CSV | Equity col | Benchmark | Trades / win-source |
|---|---|---|---|---|
| Monthly | `backtest_results.csv` | `Portfolio_Value` | `Benchmark_Value` (embedded) | `rebalance_log.csv` — no per-trade PnL → win_rate N/A |
| IPO | `ipo_edge_equity.csv` | `Portfolio_Value` | `Benchmark_Value` | `ipo_edge_trades.csv`: `PnL_Pct`, `Result` |
| Momentum | `momentum_edge_equity.csv` | `Equity` | none → `^NSEI` | `momentum_edge_trades.csv`: `PnL_Pct`, `Result` |
| PEAD | `pead_equity.csv` | (also `pead_kpis.csv`) | none → `^NSEI` | `pead_trades.csv` |
| Generic | `strategies/{sid}_equity.csv` | `equity` | none → `^NSEI` | `strategies/{sid}_trades.csv`: `return_pct` |

## 4. Architecture

Two new pure modules + thin integration; reuse existing engine/UI.

```
core/kpis.py        NEW — canonical KPI contract, single source of truth
  compute_kpis(equity_csv, trades_csv=None, *, benchmark="^NSEI",
               equity_col=None, benchmark_col=None, pnl_col=None,
               benchmark_loader=None) -> dict

core/ranking.py     NEW — composite leaderboard score
  rank_strategies(kpi_dicts, weights=DEFAULT_WEIGHTS, min_cohort=3) -> list

core/leaderboard.py NEW (small) — refresh_all(): recompute canonical KPIs + rank
  for every strategy in strategies_index.json, persist kpis_inline + rank_score + rank.

generic_backtest.py MODIFY — _compute_kpis delegates to core.kpis (one source of truth);
  engine still writes its trades/equity CSVs unchanged.
master_dashboard.py MODIFY — leaderboard: Rank + Score column, default sort by rank,
  "Recompute leaderboard" button calling core.leaderboard.refresh_all().
tests/test_kpis.py, tests/test_ranking.py, tests/test_generic_backtest.py  NEW
```

**Boundaries:** `core/kpis.py` and `core/ranking.py` are pure and independently testable (CSV paths / dicts in; no Streamlit; benchmark read injectable via `benchmark_loader`). The 4 hardcoded backtests are untouched. Persisting into `strategies_index.json` keeps page loads fast; recompute is an explicit action + post-backtest hook.

## 5. Canonical KPI Contract (`core/kpis.py`)

`compute_kpis(...)` returns this dict for every strategy:

| Key | Definition | Notes |
|---|---|---|
| `cagr` | `(final/initial)**(252/n_days) − 1` | decimal; n_days from equity index length |
| `total_return` | `final/initial − 1` | decimal |
| `volatility` | `std(daily_ret) × √252` | annualized |
| `sharpe` | `mean(daily_ret)/std(daily_ret) × √252` | rf=0; 0.0 if std==0 |
| `max_dd` | `min(equity/cummax − 1)` | decimal ≤ 0 |
| `calmar` | `cagr / abs(max_dd)` | None if max_dd==0 |
| `win_rate` | `mean(pnl > 0)` over closed trades | decimal; **None** if no per-trade PnL |
| `num_trades` | count of closed trades | 0 if no trades file |
| `alpha` | `cagr − benchmark_cagr` over aligned window | decimal |
| `final_equity` | last equity value | absolute |

**Column resolution (the standardization core):**
- **Equity col:** `equity_col` arg → else first of `Portfolio_Value`, `Equity`, `equity` → else first numeric non-Date column.
- **Benchmark:** if `benchmark_col` present in the equity CSV (e.g. `Benchmark_Value`), use it; else load `^NSEI` Close (`benchmark_loader` injectable; default reads `data/nse_bse/^NSEI.csv`), reindex to the equity dates (ffill), compute benchmark CAGR over the **same** window.
- **PnL col (trades):** `pnl_col` → else `PnL_Pct`, `return_pct`, `PnL`; else derive sign from `Result` (`WIN`/`LOSS`); none present → `win_rate=None`.
- **Percent normalization:** a `*_Pct` / pnl column whose abs median > 1.5 is treated as percent and divided by 100 to a fraction.

**Per-strategy hints:** optional `equity_col`/`benchmark_col`/`pnl_col` keys may be added to each `strategies_index.json` entry; auto-detect when absent. Monthly/IPO use embedded `Benchmark_Value`; Momentum/PEAD/generic fall back to `^NSEI`.

**Errors:** missing/empty equity CSV → raise `KpiError` (caller records the strategy as un-scored, leaves prior KPIs). A non-fatal trades read failure → `win_rate=None`, `num_trades=0`, KPIs from equity still returned.

## 6. Ranking Math (`core/ranking.py`)

`rank_strategies(kpi_dicts, weights=DEFAULT_WEIGHTS, min_cohort=3)`:

```
DEFAULT_WEIGHTS = {"sharpe":0.30, "cagr":0.25, "max_dd":0.20, "alpha":0.15, "win_rate":0.10}
```

Steps:
1. **Direction normalize** — higher = better. All metrics used as-is except `max_dd` (≤0): use `dd_score = -max_dd`.
2. **Per-metric z-score across the cohort:** `z = (x − mean)/std` over the N strategies; `std==0` → all z=0 for that metric.
3. **Missing/None impute → z=0** (cohort-median equivalent); flagged `imputed=True` in components.
4. **Weighted sum with per-strategy weight renormalization:** imputed metrics' weights are dropped and remaining weights rescaled to sum 1:
   `score = Σ(w_i·z_i for present i) / Σ(w_i for present i)`.
5. **Rank** = descending `score`; ties broken by `sharpe`, then `cagr`.

**Output** per strategy: `{"id", "score": float, "rank": int (1=best), "components": {metric: {"value", "z", "imputed"}}}`.

**Small-N handling (designed-for):** z-scores are sensitive at tiny N and scores are *relative to the current cohort* (adding a strategy reshuffles others). If `N < min_cohort` (default 3), skip z-scoring and rank directly by `sharpe` then `cagr`; log that the fallback was used (not silent). Score is documented as a relative within-cohort rank, recomputed by `refresh_all()` whenever the set changes.

Weights are a module constant (edit to tune; UI sliders deferred).

## 7. Integration

- `core/leaderboard.refresh_all()`: for each entry in `strategies_index.json`, call `core.kpis.compute_kpis` (using per-entry CSV paths + optional hints), then `core.ranking.rank_strategies` over the cohort; write back `kpis_inline` (canonical contract), `rank_score`, `rank`, and `kpis_updated` timestamp. Atomic JSON write (temp + replace).
- `generic_backtest._compute_kpis` → calls `core.kpis.compute_kpis` on the just-written equity/trades CSVs (keeps engine output identical, removes duplicate KPI math).
- After any backtest (wizard subprocess) completes, `refresh_all()` runs so ranks stay current.
- `master_dashboard.py` leaderboard: add a **Rank** badge + **Score** to each card; default sort = `rank` ascending; add a **"Recompute leaderboard"** button → `refresh_all()` → `st.rerun()`. A "why this rank" tooltip renders `components`.

## 8. Error Handling

- `compute_kpis`: equity unreadable/empty → `KpiError`; benchmark unavailable → `alpha=None` (rank imputes it), not fatal; trades unreadable → `win_rate=None`, `num_trades=0`.
- `refresh_all`: per-strategy try/except — one strategy's `KpiError` doesn't abort the batch; it keeps that strategy's previous `kpis_inline` and marks `kpis_error`. Logged.
- `rank_strategies`: empty input → `[]`; single strategy → rank 1, score 0.0; all-equal metric → z=0 (no NaN).
- Atomic write for `strategies_index.json` (temp + `os.replace`).

## 9. Testing

`core/kpis.py` and `core/ranking.py` are pure → fully unit-testable; benchmark injected via `benchmark_loader`.

**test_kpis.py**
- cagr/total_return/sharpe/max_dd on a known synthetic equity curve (hand-computed expected).
- equity-col resolution: `Portfolio_Value`, `Equity`, `equity`, fallback-first-numeric.
- benchmark from embedded `Benchmark_Value` vs injected `^NSEI` loader → alpha correct.
- win_rate from `PnL_Pct`, from `return_pct`, from `Result` strings; **None** when no trades file / no pnl col (Monthly case).
- percent-normalization (column in % vs fraction).
- empty/missing equity → `KpiError`.

**test_ranking.py**
- z-score blend orders a 3+ cohort correctly (hand-computed).
- `max_dd` sign flip (smaller drawdown ranks higher).
- missing metric imputed (z=0) + weight renormalization (score not diluted).
- N<min_cohort → Sharpe/CAGR fallback ordering.
- ties broken by sharpe then cagr; empty input → []; single strategy → rank 1.

**test_generic_backtest.py** (fills the existing gap; no network — synthetic OHLCV via monkeypatched `load_ohlcv`)
- `_normalize_formula` AND/OR/NOT → &/|/~.
- `_evaluate_signals` on a small feature panel → expected mask.
- universe loader routing (mock folders).
- exits: time-based, hard stop, trailing — each triggers on a crafted price path.
- `_compute_kpis` delegates to `core.kpis` and writes trades/equity/kpis CSVs.
- `_update_strategies_index` writes expected keys.

Target ≥80% coverage on `core/kpis.py`, `core/ranking.py`, and the engine's pure functions.

## 10. Open Questions

| Question | Resolution |
|---|---|
| risk-free rate for Sharpe? | rf=0 (matches all existing backtests). Revisit only if requested. |
| Benchmark for alpha when a strategy isn't NSE-50 (e.g. IPO/wide)? | `^NSEI` for all — single consistent benchmark for comparability. Per-strategy benchmark deferred. |
| Should Monthly's win_rate be derived from monthly rebalance up/down periods? | No — leave `None` (rotation has no discrete trades). Imputed in rank. Revisit if user wants period-win-rate. |
| Persist canonical KPIs as decimals or %? | Decimals (fractions) in JSON; UI multiplies for display (matches generic engine convention). One-time migration of the 4 existing inconsistent entries via first `refresh_all()`. |
