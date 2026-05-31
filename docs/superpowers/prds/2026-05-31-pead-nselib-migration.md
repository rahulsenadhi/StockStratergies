# Product Requirements Document: PEAD Data Source Migration (nselib + Q/A Toggle)

**Author:** rahul.senadhi
**Date:** 2026-05-31
**Status:** Draft
**Strategy:** PEAD (Strategy #4)
**Stakeholders:** Self (retail trader / dev)
**Related Docs:**
- Strategy spec: `docs/superpowers/specs/2026-05-25-pead-strategy-design.md`
- Competitive research: `docs/superpowers/research/2026-05-31-india-fundamentals-data-source-scan.md`
- Implementation plan (to follow): `docs/superpowers/plans/2026-05-31-pead-nselib-migration.md`

---

## 1. Executive Summary

PEAD strategy is currently producing **incorrect SUE scores** because yfinance reports Indian quarterly EPS wrong (POWERGRID 2026-Q4 = 8.94 in yfinance vs ₹2.22 in NSE filings, a 4× error). This migration replaces yfinance's quarterly-EPS source with `nselib` (NSE-native, free, Apache-2.0) while keeping yfinance as fallback for annual financials and as recovery path during NSE API drift. Adds a Quarterly/Annual/Both toggle to the PEAD dashboard so users can analyze the two flavors independently.

---

## 2. Background & Context

### The bug

POWERGRID.NS, quarterly result declared 2026-05-15:
- yfinance Reported EPS: **8.94**
- NSE filing Reported EPS: **₹2.22**
- 4-quarter prior history (yfinance): [4.19, 3.28, 3.7, 4.61] → mean 3.945
- yfinance-derived SUE: **8.63** (top decile, looks like a huge beat)
- Real SUE if 2.22 used: **(2.22 − 3.945) / 0.578 = −2.99** (bottom decile, actual miss)

This **inverts the trading signal** — yfinance says BUY, reality says SELL. Every POWERGRID-type ticker that yfinance mis-scales corrupts a PEAD trade.

### Why yfinance fails for India

yfinance scrapes US-Yahoo, which mixes Indian quarterly with annual/half-year EPS depending on broker filing, mis-handles consolidated vs standalone, occasionally reports in wrong units (×100). Annual income_stmt (used for Piotroski) is less affected because the broader line items (Net Income, Total Assets) come from filed 10-K equivalents and are usually intact.

### Why nselib

Per `docs/superpowers/research/2026-05-31-india-fundamentals-data-source-scan.md`:
- Only free Python lib with NSE-filed quarterly results endpoint
- Apache 2.0 license, active 2026 maintenance (v2.5.1 May 2026)
- Same data source as Screener.in (NSE filings) but raw + programmatic
- 163 GitHub stars, no critical issues
- pip install, zero auth, no API key

### Other options ruled out

- **jugaad-data:** zero fundamentals (price-only). Not a contender.
- **Screener.in:** no official API; ToS-grey scraping. Backup only.
- **Tijori:** no public API. B2B-only.
- **FMP:** US-centric; minimal India coverage.

---

## 3. Objectives & Success Metrics

### Goals

1. **Correct Indian quarterly EPS** for all 54 Nifty 50-ish tickers currently in PEAD universe — verify against NSE filings for top 10 tickers.
2. **Backward compatible** — backtest still runs, all existing 60+ unit tests pass after migration.
3. **Q/A flavor toggle** — user can switch between Quarterly PEAD / Annual PEAD / Both on every dashboard tab.
4. **Resilient** — when nselib fails or times out, yfinance fallback kicks in automatically; no exceptions bubble to UI.

### Non-Goals

1. **Replacing yfinance entirely** — keeping for Piotroski (annual income_stmt / balance_sheet / cashflow). Migration is scoped to quarterly EPS only.
2. **Real-time intraday EPS feed** — still daily EOD refresh per existing PEAD spec.
3. **Wider universe** (Nifty 200/500) — separate task; not part of this migration.
4. **Live-trading hookup** (broker API) — paper analysis only, same as today.
5. **Screener.in scrape** — explicit non-goal; ToS-grey, fragile, no programmatic API. Re-evaluate only if nselib + yfinance both fail on >10% of tickers.

### Success Metrics

| Metric | Current | Target | Measurement |
|---|---|---|---|
| Quarterly EPS accuracy (top 10 Nifty tickers, last 4 Q) | ~50% (yfinance) | ≥95% | Manual diff vs NSE filings |
| POWERGRID 2026-Q4 EPS reported | 8.94 ❌ | 2.22 ✅ | Read `pead_data/historical_events.parquet` |
| qualifies_long count over 2yr backfill | 12 | 12 ± 6 (acceptable swing) | Backfill output count |
| Backtest trades (2024-06-01 → 2026-05-31) | 4 | 4 ± 2 | `pead_trades.csv` row count |
| Unit tests pass | 60/60 | ≥60/60 | `pytest tests/pead/` |
| Backfill warm-cache runtime | 41s | ≤ 90s | `time python pead_build_history.py …` |
| Dashboard Q/A filter — load time | n/a | < 2s | Streamlit page render |
| Dashboard renders without error on each flavor | dark+light fine | ✅ Q, A, Both all render | Manual click-through |

---

## 4. Target Users & Segments

**Primary:** Self (rahul.senadhi) — retail Indian quant trader running a 4-strategy Streamlit dashboard. Decides positions based on dashboard signals.

**Secondary:** Future users who fork the repo (open-source friendly Indian retail quant community).

### Primary user JTBD (jobs-to-be-done)

When I evaluate PEAD signals → I need quarterly EPS values that match what NSE actually filed → so I can trust the SUE score and act on it without manually re-verifying every ticker on Screener.in.

---

## 5. User Stories & Requirements

### P0 — Must Have

| # | User Story | Acceptance Criteria |
|---|---|---|
| P0-1 | As a trader, I want PEAD quarterly EPS to match NSE filings, so SUE is accurate. | POWERGRID 2026-05-15 event shows eps_actual = 2.22 (±0.05) in `historical_events.parquet`. Verify same for 9 other Nifty tickers (RELIANCE, TCS, INFY, HDFCBANK, ICICIBANK, WIPRO, BAJFINANCE, ITC, LT). |
| P0-2 | As a trader, I want nselib failures to never break PEAD, so backfill always finishes. | If `nselib.capital_market.financial_results_for_equity()` raises or returns empty for a ticker, yfinance fallback runs silently; backfill completes 100% of universe. |
| P0-3 | As a trader, I want all existing tests to keep passing, so I know nothing else broke. | `pytest tests/pead/` reports ≥60 passed, 0 failed. New nselib path has ≥6 new unit tests with cache hit/miss/stale/fallback coverage. |
| P0-4 | As a trader, I want a Q/A/Both toggle in the PEAD dashboard, so I can analyze each flavor separately. | Single `st.radio` at top of PEAD page; all 4 tabs (Live, Backtest, Calendar, Screener) filter `events.parquet` by `period_type` per selection. State persists across tab switches in session. |
| P0-5 | As a trader, I want the SUE-decile-spread chart to be flavor-aware, so I can confirm edge exists in each flavor separately. | Decile-spread CSV emits 2 files: `pead_decile_spread_Q.csv` and `pead_decile_spread_A.csv`. Backtest CLI `--flavor Q\|A\|both` writes accordingly. Dashboard shows the right one per toggle. |

### P1 — Should Have

| # | User Story | Acceptance Criteria |
|---|---|---|
| P1-1 | As a trader, I want the data-quality log to show which source served each event, so I can audit. | Each row in `events.parquet` gains a column `eps_source` with value `nselib`, `yfinance_fallback`, or `none`. Dashboard surfaces a footer counter ("Source: 480 nselib / 41 yfinance fallback / 0 missing"). |
| P1-2 | As a trader, I want nselib responses cached so repeat backfills are fast. | nselib responses cached via existing `core/yf_cache.py` (rename to `core/fundamentals_cache.py` to reflect multi-source). 7-day TTL same as current. Warm-cache backfill ≤ 90s. |
| P1-3 | As a trader, I want a one-command "verify accuracy" tool, so I can re-check after NSE schema changes. | `python pead_data_audit.py --tickers RELIANCE.NS,POWERGRID.NS,…` prints a per-ticker diff vs a known-good fixture file. Exit code 1 if mismatch >5%. |

### P2 — Nice to Have / Future

| # | User Story | Acceptance Criteria |
|---|---|---|
| P2-1 | As a trader, I want the Live+Open tab to show Q and A signals side by side, so I can compare. | Two sub-tables when toggle = Both. |
| P2-2 | As a trader, I want the dashboard glossary to clarify Q vs A flavor. | Glossary expander gains "Quarterly PEAD vs Annual PEAD" explanation. |
| P2-3 | As a trader, I want Screener.in scraping wired as 3rd-fallback for the top 5 most-traded tickers. | Out of scope this PRD; revisit if nselib + yfinance both fail on >10% of events for a quarter. |

---

## 6. Solution Overview

### Architecture changes

```
BEFORE
─────────────────────────────────
pead_event_builder.build_event()
   ↓
core/fundamentals.get_quarterly_eps_history()
   ↓
core/yf_cache.get_snapshot()
   ↓
yfinance.Ticker(t).earnings_dates['Reported EPS']    ← WRONG for India

AFTER
─────────────────────────────────
pead_event_builder.build_event()
   ↓
core/fundamentals.get_quarterly_eps_history()
   ├─► [primary] core/nse_data.get_quarterly_results(t, as_of)
   │       ↓ uses cached nselib.capital_market.financial_results_for_equity()
   │       ↓ returns ₹2.22 for POWERGRID
   │
   └─► [fallback] core/yf_cache.get_snapshot() — same as before
```

### New module: `core/nse_data.py`

- Wraps `nselib.capital_market.financial_results_for_equity()`
- Caches responses in `pead_data/nse_cache/<ticker>.pkl` (mirrors yf_cache structure)
- Returns normalized DataFrame: columns `period_from`, `period_to`, `period_type` (Q/A), `eps`, `revenue`, `net_profit`, `pat`. Index = filing/announce date.
- Handles NSE schema variations (consolidated vs standalone — prefer consolidated)

### Updated `core/fundamentals.py`

- `get_quarterly_eps_history(ticker, as_of, n=4)`:
  1. Try nselib via `core.nse_data` first
  2. If nselib raises or returns <n rows → fall back to yfinance
  3. Tag the result with `_source` attribute for telemetry
- `get_annual_eps_history()` — **unchanged**, still yfinance (annual EPS less affected)
- `get_piotroski_inputs()` — **unchanged**, still yfinance income_stmt/balance_sheet/cashflow

### Updated event row schema

Add column to `events.parquet`:
- `eps_source` (str: `nselib` | `yfinance_fallback` | `none`)

### Dashboard changes (`pead_dashboard.py`)

- Add `st.radio('Period type', ['Q', 'A', 'Both'], horizontal=True, key='_pead_flavor')` above tabs
- All 4 tab functions take a `flavor` arg and filter the events DataFrame
- Decile-spread chart picks the right CSV per flavor
- Source counter strip at page footer

### Backtest CLI (`pead_backtest.py`)

- `--flavor` arg already exists; ensure decile-spread output uses flavor in filename
- `pead_decile_spread.csv` → `pead_decile_spread_<flavor>.csv`

---

## 7. Open Questions

| # | Question | Owner | Deadline |
|---|---|---|---|
| Q1 | nselib `financial_results_for_equity` schema — does it expose Diluted EPS or only Net Profit? If only Net Profit, derive EPS via shares-outstanding from yfinance. | Implementer (Task 3.1) | Day 1 of build |
| Q2 | nselib rate-limit observed in practice? Need to throttle? | Implementer (during cold backfill test) | Day 1 |
| Q3 | Annual EPS comparison — does NSE corp-announce expose annual filing separately, or is it derived from Q4 + 3 prior quarters? Affects whether to migrate annual EPS too. | Implementer (Task 3.1 spike) | Day 1 |
| Q4 | Consolidated vs standalone — should we always prefer consolidated when both available? (POWERGRID files both.) | Self decision | Pre-build |

**Default decisions if not resolved by deadline:**
- Q1: derive EPS = Net Profit / shares_outstanding (yfinance source).
- Q2: 0.3s throttle between nselib calls; ThreadPool workers=8 (lower than yf's 12).
- Q3: scope this PRD to quarterly only; annual stays on yfinance.
- Q4: prefer consolidated.

---

## 8. Timeline & Phasing

### Phase 1 — Discovery & nselib spike (Day 1, 2h)
- Pip-install nselib, hit `financial_results_for_equity()` for RELIANCE + POWERGRID
- Confirm schema, EPS field, period_type encoding
- Resolve open questions Q1, Q2, Q3
- **Gate:** if nselib's quarterly EPS for POWERGRID 2026-Q4 ≠ 2.22, escalate (re-evaluate plan)

### Phase 2 — `core/nse_data.py` + cache (Day 1, 2h)
- New module with `get_quarterly_results(ticker, as_of)` API
- Pickle cache mirroring `core/yf_cache.py` pattern
- 6+ unit tests (cache hit/miss/stale/force, schema normalization, fallback shape)

### Phase 3 — Wire into `core/fundamentals.py` (Day 1, 1h)
- Modify `get_quarterly_eps_history` — nselib primary, yfinance fallback
- Add `eps_source` tagging
- Update existing tests to mock both sources

### Phase 4 — Re-backfill + audit (Day 1, 30min)
- `rm pead_data/historical_events.parquet`
- `python pead_build_history.py --start 2024-01-01 --end 2026-05-31`
- Manual diff: top 10 Nifty tickers' quarterly EPS vs NSE filings — must hit ≥95% accuracy

### Phase 5 — Q/A dashboard toggle (Day 2, 1h)
- Sidebar/page radio
- 4 tab handlers filter by `period_type`
- Decile-spread CSV split by flavor
- Source counter strip

### Phase 6 — Backtest re-run + verification (Day 2, 30min)
- `python pead_backtest.py --flavor Q --start 2024-06-01 --end 2026-05-31`
- `python pead_backtest.py --flavor A --start 2024-06-01 --end 2026-05-31`
- Decile spread Q vs A — Q should show classic upward slope, A may not (Indian annual EPS less granular)

### Phase 7 — Memory + docs (Day 2, 30min)
- Update `MEMORY.md` PEAD entry
- `STRATEGY_GUIDE.md` — update PEAD section noting data-source migration
- Commit

**Total: ~7 hours real work, spread over 2 days.**

### Risks called out

| Risk | Mitigation |
|---|---|
| nselib NSE-API drift mid-build | yfinance fallback active in production; pin nselib==2.5.1 in requirements |
| nselib's "EPS" is actually basic vs diluted vs adjusted — different from yfinance | Audit step Phase 4 catches; document choice in `core/nse_data.py` docstring |
| Q/A toggle adds UI complexity that confuses single-flavor user | Default = "Both" (current behavior); toggle is opt-in refinement |
| qualifies_long count drops to 0 after re-backfill (real SUE != fake SUE) | This is correct behavior; flag with banner: "Backfill now uses NSE data — historical signals may differ from prior runs" |
| Cache pollution from old yfinance values | New `core/fundamentals_cache.py` lives at separate path; old yf_cache untouched. Hard-delete old PEAD events before re-backfill. |

---

## Approval

- [ ] PRD reviewed by stakeholder (self)
- [ ] Phase 1 spike findings reviewed before Phase 2 start
- [ ] Phase 4 audit ≥95% accuracy before merging to main
- [ ] Final dashboard click-through on both Q and A flavors before closing
