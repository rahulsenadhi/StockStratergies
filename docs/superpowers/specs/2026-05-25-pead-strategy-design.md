# PEAD Strategy — Design Spec

**Date:** 2026-05-25
**Status:** Approved (sections 1-6) — pending user spec-file review
**Strategy #:** 4 (after Monthly Rotation, IPO Edge, Momentum Edge)

---

## 1. Goal

Add Post-Earnings-Announcement Drift (PEAD) strategy to the existing NSE Momentum Rotation Dashboard. Trade both **quarterly** and **annual** earnings surprises. Long-only for retail cash account; paper long-short tracked as diagnostic. Integrate into `master_dashboard.py` as a 4-tab page.

PEAD edge: stocks that beat earnings consensus (high SUE) tend to drift upward for ~60 trading days post-announcement. We long top-decile SUE filtered for quality (Piotroski ≥ 7, P/B ≤ sector median).

---

## 2. Decisions Locked During Brainstorm

| Decision | Choice |
|---|---|
| Data source | yfinance (fundamentals) + NSE corporate-announce API (exact result dates) |
| Universe | Reuse `build_universe.py` output, runtime filter: market cap > ₹5,000 Cr AND listed > 5y AND ≥4 quarters non-null EPS |
| SUE flavor | Both quarterly AND annual |
| Entry rule | Top-decile SUE + Piotroski ≥ 7 + P/B ≤ sector median |
| Direction | Long-only; paper long-short as backtest diagnostic |
| Sizing | Equal-weight, unlimited concurrent positions |
| Exit | min(60 trading days, day before next earnings) |
| Entry timing | Next trading day open after `result_date` |
| Refresh cadence | Daily incremental |
| Architecture | Hybrid — strategy files at root, shared primitives in `core/` |

---

## 3. Architecture & File Layout

```
core/
  fundamentals.py     # yfinance wrapper: quarterly EPS, annual EPS, financials, P/B
                      # Caches to pead_data/fundamentals_cache.parquet
  nse_announce.py     # NSE /api/corporates-financial-results client
                      # Cookie/header dance, retry, throttle
  piotroski.py        # 9-component F-score
  sue.py              # SUE math both flavors (quarterly_sue, annual_sue)

pead_downloader.py    # Daily incremental refresh entry point
pead_backtest.py      # Historical backtest engine
pead_build_history.py # One-time historical events builder
pead_dashboard.py     # Streamlit page (4 tabs)

pead_data/
  fundamentals_cache.parquet
  events.parquet               # append-only event log (live)
  historical_events.parquet    # historical backfill
  result_dates.parquet         # forward calendar (next 30d)
  pb_sector_medians.parquet
  live_signals.csv             # tomorrow's qualifying entries
  open_positions.parquet
  data_quality_log.csv
  last_run_status.json
  nse_announce_raw/{YYYY-MM-DD}.json

tests/pead/
  test_sue.py
  test_piotroski.py
  test_nse_announce.py
  test_fundamentals.py
  test_downloader_e2e.py
  test_backtest_lookahead.py
  test_backtest_exits.py
```

Wire-ups:
- `master_dashboard.py` — register PEAD page ("📊 PEAD Strategy" sidebar entry).
- `run_all.py` — add PEAD downloader step.
- `refresh_data.bat` — call `python pead_downloader.py`.

---

## 4. Data Model

### Event record (one row per ticker × result-date × period_type)

| Column | Type | Description |
|---|---|---|
| ticker | str | yfinance ticker, e.g. `RELIANCE.NS` |
| sector | str | yfinance info["sector"] |
| result_date | date | NSE-declared announcement date |
| period_type | str | `Q` or `A` |
| period_end | date | quarter-end or fiscal-year-end |
| eps_actual | float | reported EPS for period |
| eps_history | list[4] | prior 4 same-period EPS (announced before result_date) |
| eps_expected | float | mean(eps_history) |
| eps_std | float | stdev(eps_history, ddof=1) |
| sue | float | (eps_actual - eps_expected) / eps_std |
| piotroski | int | 0..9, last announced fiscal year |
| pb | float | price / book at result_date |
| pb_sector_median | float | median P/B of same-sector universe at result_date |
| qualifies_long | bool | top-decile SUE AND piotroski≥7 AND pb≤pb_sector_median |
| qualifies_short | bool | bottom-decile SUE AND piotroski≤3 (paper diagnostic only) |
| entry_date | date | result_date + 1 trading day (filled at execution) |
| entry_price | float | next-day open |
| exit_due_date | date | min(entry+60td, next_known_result-1td) |

### Trade record (`pead_trades.csv`)

`ticker, entry_date, entry_price, shares, exit_date, exit_price, return_pct, hold_days, exit_reason, period_type, sue, piotroski, pb, sector`

---

## 5. SUE Math

### Quarterly
```
prior        = [E_{t-1}, E_{t-2}, E_{t-3}, E_{t-4}]   # last 4 reported quarters
eps_expected = mean(prior)
eps_std      = stdev(prior, ddof=1)
sue          = (E_t - eps_expected) / eps_std         # nan if eps_std==0 or any nan
```

### Annual
```
prior        = [E_{y-1}, E_{y-2}, E_{y-3}, E_{y-4}]
eps_expected = mean(prior)
eps_std      = stdev(prior, ddof=1)
sue          = (E_y - eps_expected) / eps_std
```

### Deciles — rolling cohort
For each `result_date`, pool events declaring within `±5 trading days` (rolling cohort). Rank SUE within cohort. Top decile = `qualifies_long` candidate set. Bottom decile = `qualifies_short`. Reason: pure same-day decile fails when only 2-3 results declare; ±5td yields 20-50 events for stable deciles.

---

## 6. Piotroski F-Score (9 binary points)

**Profitability (4):**
- ROA > 0
- OCF > 0
- ΔROA > 0 (vs prior year)
- OCF > NetIncome (accruals)

**Leverage/Liquidity (3):**
- Δ Long-term debt / assets < 0
- Δ Current ratio > 0
- No new shares issued

**Efficiency (2):**
- Δ Gross margin > 0
- Δ Asset turnover > 0

Computed annually using yfinance `income_stmt` + `balance_sheet` + `cashflow`. For quarterly events, use most-recent annual Piotroski (acceptable lag — fundamentals don't flip quarterly).

---

## 7. P/B Sector Median

At each event date, compute P/B for every ticker in same sector within the active universe. Take median. Refreshed daily during incremental run, stored to `pead_data/pb_sector_medians.parquet` keyed by `(date, sector)`. Fallback to universe median if sector unknown.

---

## 8. Look-Ahead-Bias Guards

- `eps_history` MUST use only periods **announced before** `result_date` (NSE announce date, not period_end).
- Piotroski uses last fiscal year **whose annual result was already announced** before `result_date`.
- P/B sector median uses closing prices of `result_date - 1`.
- Backtest final audit step verifies all three. Violation → abort exit code 2 with `LOOKAHEAD_VIOLATION`.

---

## 9. NSE Corporate-Announce Client

**Endpoints:**
- `https://www.nseindia.com/api/corporates-financial-results?index=equities&period=Quarterly`
- `https://www.nseindia.com/api/corporates-financial-results?index=equities&period=Annual`

**Required dance (proven in `nse_bse_downloader.py`):**
1. Seed cookies: `session.get("https://www.nseindia.com")`.
2. Headers: `User-Agent`, `Accept: application/json`, `Referer: https://www.nseindia.com/companies-listing/corporate-filings-financial-results`.
3. Call API. Retry 3× on 401/403 with cookie reseed. Sleep 2s between requests. 30s timeout.

**Response fields kept:** `symbol`, `broadcast_date` → `result_date`, `period_from`, `period_to`, `period_type` inferred from period length (Q: ~90d, A: ~365d).

**Ticker mapping:** NSE `symbol` → yfinance ticker via `clean_symbol()` from `build_universe.py`.

**Caching:** raw JSON → `pead_data/nse_announce_raw/{YYYY-MM-DD}.json`. Skip refetch if file exists; `--force` overrides.

---

## 10. Daily Downloader Flow (`pead_downloader.py`)

```
1. Load filtered universe (mkt_cap > 5000 Cr AND listed > 5y AND ≥4 q EPS).
2. fetch_results_today() via core/nse_announce
   → list of (symbol, result_date, period_type).
3. For each declaring symbol IN universe:
   a) core/fundamentals.get_fundamentals(ticker)
   b) core/sue.quarterly_sue(...) or annual_sue(...)
      using ONLY periods whose announce_date < today.
   c) core/piotroski.piotroski_score(...) — last-announced fiscal year.
   d) compute pb = price / bookValue.
   e) write event row to events.parquet (dedup key: ticker+result_date+period_type).
4. Recompute sector P/B medians → pb_sector_medians.parquet.
5. Recompute deciles over ±5td cohort. Set qualifies_long / qualifies_short.
6. Filter today's qualifies_long → live_signals.csv.
7. Refresh forward calendar (next 30d) → result_dates.parquet.
8. Write last_run_status.json with summary.
```

**Idempotent:** re-running same day produces no duplicates.

---

## 11. Backtest Engine (`pead_backtest.py`)

### History build
- Try NSE corp-announce paged by month for max range it serves.
- Fallback: yfinance `ticker.earnings_dates` (approximate to nearest day) for gaps.
- Persist to `historical_events.parquet`. Built by `pead_build_history.py` one-time.
- If history < 3yr after build → log warning, proceed.

### Loop
```
sort events by result_date asc
portfolio = {cash: 1_000_000, open: {}, equity_curve: [], trades: []}

for each trading_day in [start..end]:
    # 1. Exits first
    for ticker in list(portfolio.open):
        pos = portfolio.open[ticker]
        next_result = lookup_next_result(ticker, pos.entry_date)
        pos.exit_due = min(entry+60td, next_result-1td if next_result else +inf)
        if trading_day >= pos.exit_due:
            close at close_price; reason = "60D" or "NEXT_EARNINGS"

    # 2. Entries — events with result_date == prev_trading_day(trading_day)
    qualifying = yest_events[qualifies_long == True]
    if qualifying:
        total_after = len(open) + len(qualifying)
        cash_per_new = portfolio.cash / total_after    # NEW slots only; existing not rebalanced
        for event in qualifying:
            px = next-day open price
            shares = floor(cash_per_new / px)
            if shares == 0: skip
            buy

    # 3. Mark to market
    equity_curve.append((trading_day, cash + sum(shares * close_price)))
```

### CLI
```
python pead_backtest.py --start 2022-01-01 --end 2026-05-25 --flavor both
python pead_backtest.py --flavor Q
python pead_backtest.py --flavor A
```

### Diagnostics → `pead_diagnostics.csv`
- Paper long-short return series (long top decile − paper short bottom decile).
- Decile spread: avg 60d forward return per decile (1-10), per year.
- Hit rate, avg win, avg loss, Sharpe, Sortino, max DD, CAGR.

### Look-ahead audit
Final step prints per-trade audit: result_date, entry_date (must = result_date+1td), eps_history announce_dates (all < result_date), Piotroski fiscal year used. Any violation → abort.

---

## 12. Dashboard (`pead_dashboard.py`)

Registered in `master_dashboard.py` sidebar as **"📊 PEAD Strategy"**. 4 tabs via `st.tabs(["Live + Open", "Backtest", "Calendar + Heatmap", "Screener"])`.

### Tab 1 — Live Signals + Open Positions
- Top half: live_signals.csv table. Cols: Ticker | Sector | SUE | Decile | EPS Actual | EPS Expected | Surprise % | Piotroski | P/B | Sector Median P/B | Result Date | Period. Green chip for Piotroski≥7 and P/B≤sector median. Row click → expand EPS history bars + Piotroski 9-component checklist + 6mo price chart.
- Bottom half: open_positions.parquet. Cols: Ticker | Entry Date | Days Held | Days to Exit | Entry Px | Live Px | P&L % | Exit Reason When Due | Next Earnings | SUE@Entry. Warning chip if next_earnings ≤ today+3d.

### Tab 2 — Backtest Results
- Equity curve PEAD vs Nifty (NIFTYBEES.NS); toggle paper long-short.
- KPI strip: CAGR | Max DD | Sharpe | Sortino | Win Rate | Avg Hold | # Trades | Best | Worst.
- SUE Decile Performance bar chart (decile 1..10 × avg 60d return). Per-year facet toggle.
- Trades table filterable by year, period, exit reason.
- Edge-proof section (matches Momentum Edge UX).

### Tab 3 — Earnings Calendar + EPS Surprise Heatmap
- Top: forward 30d calendar grid, ticker chips per day, sector filter.
- Bottom: sector × quarter avg-SUE heatmap (last 8 quarters), diverging red-green. Click cell → ticker list.

### Tab 4 — Piotroski / P-B / SUE Screener
- Standalone, not PEAD-tied.
- Filters: SUE range, Piotroski min, P/B max, sector multi-select, mkt cap min.
- Save filter preset → `screener_presets.json`.
- Same row-click expansion as Tab 1.

### Shared UX
- Glossary expander on every tab.
- Last-refresh timestamp + "Run incremental refresh" button (subprocess pead_downloader.py).
- Data-quality badge: N tickers in universe / N with valid EPS history; red if <70%.

---

## 13. Error Handling

| Failure mode | Behavior |
|---|---|
| NSE 401/403 persistent | Exit 1, log `NSE_BLOCKED`, write last_run_status.json |
| NSE partial response | Continue, log gap count |
| yfinance empty quarterly_earnings | Skip ticker, log `NO_EPS_HISTORY` |
| yfinance empty financials | Piotroski = NaN, fails qualifies_long |
| yfinance 429 rate limit | Backoff 60s, resume |
| eps_std == 0 | SUE = NaN, event excluded |
| < 4 prior periods | Event excluded, logged |
| Sector unknown | Fallback to universe-wide P/B median |
| Ticker delisted | Held to exit; if price missing >5d → forced close, mark `FORCED_CLOSE_DELISTING` |
| Look-ahead violation in backtest | Exit 2, `LOOKAHEAD_VIOLATION` |

---

## 14. Testing

Framework: `pytest`. Location: `tests/pead/`. Coverage target ≥ 80%; critical paths (SUE, Piotroski, look-ahead audit) → 100%.

| Test file | Coverage |
|---|---|
| test_sue.py | quarterly_sue & annual_sue, textbook inputs, edge cases (zero std, NaN, negative history) |
| test_piotroski.py | each of 9 components in isolation + composite on synthetic financials |
| test_nse_announce.py | parser on saved JSON fixtures, date parsing, period_type inference |
| test_fundamentals.py | cache hit/miss, stale detection, ticker mapping |
| test_downloader_e2e.py | mock NSE+yfinance → events.parquet correctness, dedup, qualifies flags |
| test_backtest_lookahead.py | synthetic event triggers `LOOKAHEAD_VIOLATION` if violated |
| test_backtest_exits.py | 60d and next-earnings exits trigger correctly |

Smoke test: 6-month backtest with --flavor Q. Assert >0 trades, equity curve monotonic dates, no NaN in trades.csv.

---

## 15. Performance Targets

| Operation | Target |
|---|---|
| Daily downloader | <2 min (5-30 declaring tickers/day) |
| Backtest 4yr × ~3200 events | <60s |
| Dashboard initial load | <3s |
| Heatmap render | precomputed in pead_dashboard_cache.parquet |

I/O: pyarrow parquet. Cache via existing `core/cache.py` (LRU + disk).

---

## 16. Rollout Phases

1. **Foundation (no UI):** core/{sue, piotroski, fundamentals, nse_announce}.py + unit tests.
2. **Historical build:** pead_build_history.py → historical_events.parquet. Inspect coverage report.
3. **Backtest:** pead_backtest.py; validate SUE-decile-spread chart slopes up.
4. **Daily downloader:** pead_downloader.py; wire into run_all.py + refresh_data.bat. Monitor 1 week.
5. **Dashboard:** pead_dashboard.py 4 tabs; register in master_dashboard.py. Paper-trade 1 month before live.
6. **Memory + docs:** update MEMORY.md, project_overview.md (now 4 strategies), README.

---

## 17. Risks

| Risk | Mitigation |
|---|---|
| NSE corp-announce historical depth <4yr | yfinance earnings_dates fallback; accept 2yr if needed |
| yfinance EPS gaps for small caps | Universe filter excludes ticker if <4 q EPS |
| Indian results clustered (Jan/Apr/Jul/Oct) | Episodic signal flow expected — user-comms only |
| yfinance API changes | Thin wrapper in core/fundamentals.py isolates blast radius |
| NSE scraper blocked | Cookie/header dance pattern reused; manual fallback documented |

---

## 18. Out of Scope

- F&O shorting (Indian retail cash account focus).
- Volatility-targeted sizing (equal-weight chosen).
- Real-time intraday entry (next-day open only).
- Live capital deployment without 1-month paper validation.
- Refactoring existing strategies into `core/` (additive only).
- Web scraping screener.in or paid APIs.

---

## 19. Acceptance Criteria

- [ ] Unit tests pass with ≥80% coverage; SUE/Piotroski/look-ahead at 100%.
- [ ] `pead_downloader.py` runs daily, <2 min, writes live_signals.csv + events.parquet.
- [ ] `pead_backtest.py --flavor both --start <3yr ago>` produces equity curve, trades.csv, diagnostics.csv with no look-ahead violations.
- [ ] SUE-decile-spread chart shows monotonic-ish upward slope (decile 10 avg 60d return > decile 1).
- [ ] Dashboard 4 tabs render < 3s, no errors on empty data, glossary present.
- [ ] `master_dashboard.py` PEAD page registered, sidebar entry visible.
- [ ] MEMORY.md updated with strategy #4 entry.
