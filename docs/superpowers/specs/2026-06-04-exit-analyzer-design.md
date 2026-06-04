# Hold-Period & Exit-Ladder Analyzer — Design

**Date:** 2026-06-04
**Status:** Approved for planning
**Author:** brainstorming session (rahulsenadhi)

## Problem

Each of the four strategies fires entry signals, but tells the user nothing about
*when to exit* or *how to scale out*. Given an entry, we want a data-driven
recommendation for:

1. **Best holding duration** — the number of trading days after entry that
   historically maximizes risk-adjusted profit.
2. **Exit ladder** — a 3-tier partial scale-out (profit targets + booking
   percentages) plus a stop level, so the user can lock gains while capping
   drawdown.

The recommendation is shown alongside each live entry signal.

## Decisions (from brainstorming)

| Question | Decision |
|---|---|
| Recommendation basis | **Per-strategy historical.** Pool all historical entries for a strategy; sub-bucket by setup-type / SUE-decile only when a bucket has enough samples, else fall back to strategy-level. Per-signal forward simulation rejected (too noisy; IPO Edge has only ~18 trades). |
| Optimization objective | **Risk-adjusted:** maximize `median_return[d] / max(avg_MAE[d], floor)` over horizon days `d`. |
| Exit ladder | **3-tier scale-out** derived from the historical max-favorable-excursion (MFE) distribution, plus a stop from the max-adverse-excursion (MAE) distribution. |
| Display | **Compact badge per signal row + an "Exit Playbook" detail card** above each strategy's signal table. |

## Data Sources

All strategies load prices through `core/data_io.load_ohlcv`.

| Strategy | Entries from | Price folder | MFE/MAE quality |
|---|---|---|---|
| Monthly Rotation | `rebalance_log.csv` (`Stocks_Bought` per rebalance) | `data/` (close-only) | close-approximation |
| IPO Edge | `ipo_edge_trades.csv` | `ipo_data/` (OHLCV) | true intraday |
| Momentum Edge | `momentum_edge_trades.csv` | `momentum_edge_data/` (OHLCV) | true intraday |
| PEAD | `pead_trades.csv` | `momentum_edge_data/` (OHLCV) | true intraday |

The `data/` folder is close-only, so Monthly Rotation MFE/MAE is computed from
close prices and flagged `data_quality: "close"`. The other three use High/Low
for true intraday excursions and are flagged `data_quality: "ohlcv"`.

## Architecture

Four units, each with one clear responsibility:

```
core/exit_analyzer.py          pure analysis functions (no Streamlit, no network)
precompute_exit_recommendations.py   pipeline step → exit_recommendations.json
master_dashboard.py            two new render helpers read the JSON
tests/test_exit_analyzer.py    pure-function unit tests
```

### 1. `core/exit_analyzer.py`

Pure, unit-testable functions. No Streamlit, no I/O beyond what is passed in.

**Input:** a list of historical entries `(ticker, entry_date, entry_price)`, a
price panel (dict of ticker → OHLCV/close DataFrame, as returned by
`load_ohlcv`), and a config object.

**Steps:**

1. **Post-entry matrix.** For each entry, pull forward up to `MAX_HORIZON_DAYS`
   (default 90 trading days) of prices. For each day offset `d`:
   - cumulative return vs entry price,
   - running MFE = max favorable excursion % so far,
   - running MAE = max adverse excursion % so far.
   Use intraday High/Low where present; fall back to Close when the panel is
   close-only.
2. **Return-by-day curve.** Across all entries, for each day `d`: median, mean,
   p25, p75 of cumulative return, and average MAE. Weight each day by the number
   of entries that have data for that offset (entries near the data end
   contribute fewer days).
3. **Best hold duration.** `argmax` over `d` of
   `median_return[d] / max(avg_MAE[d], MAE_FLOOR)`. Report the day, its median
   return, win-rate at that day, and sample size.
4. **3-tier exit ladder.** From the per-entry MFE distribution, place targets at
   the `TARGET_PERCENTILES` (default 40th / 65th / 85th) percentiles of MFE; book
   `BOOK_FRACTIONS` (default 40% / 35% / 25%) of the position at each. For each
   target, report the historical hit-rate (fraction of entries whose MFE reached
   that target).
5. **Stop level.** `STOP_PERCENTILE` (default 75th) percentile of the MAE
   distribution — the "normal pain" floor — rounded to a clean number.
6. **Output:** a `Recommendation` dataclass serialized to dict:

   ```
   {
     "strategy": "momentum_edge",
     "bucket": "ALL" | "FLAG" | "decile_10" | ...,
     "hold_days": 32,
     "hold_median_return": 8.4,
     "hold_win_rate": 0.61,
     "targets": [
        {"pct": 6.0, "book_pct": 40, "hit_rate": 0.78},
        {"pct": 12.0, "book_pct": 35, "hit_rate": 0.52},
        {"pct": 22.0, "book_pct": 25, "hit_rate": 0.29}
     ],
     "stop_pct": -8.0,
     "sample_size": 142,
     "data_quality": "ohlcv" | "close",
     "curve": [{"day": 1, "median": 0.3, "p25": -1.1, "p75": 1.9, "mae": -1.4}, ...]
   }
   ```

**Sub-bucketing.** When a strategy exposes a natural bucket key (IPO Edge
`Setup_Type`, PEAD SUE decile), compute a recommendation per bucket only when the
bucket has `>= MIN_SAMPLE` (default 20) entries; otherwise fall back to the
strategy-level recommendation. `log()` how many entries were dropped or
fell back.

**Constants (named, tunable):** `MAX_HORIZON_DAYS=90`, `TARGET_PERCENTILES=(40,65,85)`,
`BOOK_FRACTIONS=(40,35,25)`, `STOP_PERCENTILE=75`, `MIN_SAMPLE=20`,
`MAE_FLOOR=0.5` (%).

### 2. `precompute_exit_recommendations.py`

Follows the existing precompute pattern (`precompute_momentum_signals.py`). Runs
once in the data pipeline, after the backtest scripts. For each strategy:

- Load entries from that strategy's trades source.
- Load the price panel via `core/data_io.load_ohlcv` for the strategy's folder.
- Call `exit_analyzer.analyze()` (strategy-level + any buckets).
- Collect into one `exit_recommendations.json` keyed by strategy name.

Wire into `run_all.py` and `refresh_data.bat` after the backtest steps.

### 3. `master_dashboard.py` display

Two new helpers, both reading the loaded `exit_recommendations.json`:

- **`_exit_playbook_card(rec)`** — detail card placed above each strategy's
  signal table: hold-days, a ladder table (target % / book % / historical
  hit-rate), stop level, sample size, a data-quality note, and a small Plotly
  return-by-day curve reusing the existing chart style.
- **`_exit_badge(rec)`** — compact one-line string, e.g.
  `Hold ~32d · T1/T2/T3 +6/+12/+22% · Stop −8%`, injected as a cell/column into
  the live signal and ranking tables (`live_rankings`, `momentum_edge_signals`,
  IPO signals, PEAD signals). Where a bucket-level recommendation exists for a
  row's setup-type/decile, use it; else the strategy-level one.

Both degrade gracefully: if a strategy has too few trades, show an
"insufficient history" empty state instead of a recommendation.

### 4. `tests/test_exit_analyzer.py`

Pure-function tests, no Streamlit or network:

- Synthetic entries with known forward paths → assert correct MFE/MAE,
  return-by-day curve, and argmax hold day.
- Risk-adjusted objective tie-breaking.
- MFE-percentile target derivation and MAE-percentile stop.
- Close-only fallback path (panel with no High/Low).
- Sub-bucket falls back to strategy-level when sample < `MIN_SAMPLE`.
- Empty / too-short history returns an insufficient-history result.

## Edge Cases

- **Entry near data end:** path shorter than horizon → use available days;
  curve aggregation weights each day by its sample count.
- **Survivorship / missing data:** only entries with available price data are
  analyzed; skipped entries are logged.
- **Close-only data (Monthly Rotation):** flagged `data_quality: "close"`; the
  card notes that excursions are close-based approximations.
- **Tiny universe (IPO Edge):** likely below `MIN_SAMPLE` for sub-buckets;
  strategy-level recommendation used, card shows the small sample size honestly.

## Out of Scope (YAGNI)

- Per-signal forward simulation.
- Re-running or changing any backtest's own exit logic — this is an advisory
  overlay only; backtests are untouched.
- Configurable tier counts in the UI (fixed at 3; constants tunable in code).
- Live intraday execution / order placement.

## Success Criteria

- `core/exit_analyzer.analyze()` returns a correct `Recommendation` for synthetic
  inputs with hand-verifiable MFE/MAE and hold-day argmax (covered by tests).
- `precompute_exit_recommendations.py` produces `exit_recommendations.json` for
  all four strategies without error.
- Each strategy page shows the Exit Playbook card and a per-signal badge, reading
  from the JSON in well under a second (no live compute on page load).
- Strategies with insufficient history show a clear empty state, not a crash or a
  misleading recommendation.
