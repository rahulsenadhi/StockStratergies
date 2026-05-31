# Product Requirements Document: PEAD Data Source Migration (nselib + Q/A Toggle)

**Author:** rahul.senadhi
**Date:** 2026-05-31 (rev 2 — code-grounded)
**Status:** Draft
**Strategy:** PEAD (Strategy #4)
**Stakeholders:** Self (retail trader / dev)

**Related docs:**
- Strategy spec: `docs/superpowers/specs/2026-05-25-pead-strategy-design.md`
- Competitive research: `docs/superpowers/research/2026-05-31-india-fundamentals-data-source-scan.md`
- Pre-mortem: `docs/superpowers/prds/2026-05-31-pead-nselib-migration-premortem.md`
- Implementation plan (next): `docs/superpowers/plans/2026-05-31-pead-nselib-migration.md`

---

## 1. Executive Summary

PEAD is producing wrong SUE scores because yfinance reports Indian quarterly EPS incorrectly (POWERGRID 2026-Q4 = 8.94 in yfinance vs ₹2.22 in NSE filings, 4× error — inverts BUY/SELL signal). Migrate quarterly-EPS fetch from yfinance to `nselib` (NSE-native, Apache 2.0). Keep yfinance for annual financials (Piotroski) and as fallback. Add Quarterly / Annual / Both toggle to PEAD dashboard.

**Code touch surface (per scan):** 4 yfinance quarterly call sites, 3 yfinance annual call sites, 5 CSV outputs, 4 dashboard tabs, 12 test fixtures. See §6 for exact file:line list.

---

## 2. Background & Context

### The bug, traced through code

| Stage | File:Line | Behavior |
|---|---|---|
| Live fetch | `pead_downloader.py:45` (`get_actual_eps`) | Calls `t.quarterly_earnings` — **deprecated, returns None** |
| Pre-fetch | `core/yf_cache.py:58` (`_fetch_live`) | Calls `t.earnings_dates` — returns wrong values for India |
| History read | `core/fundamentals.py:45` (`get_quarterly_eps_history`) | Reads cached `earnings_dates["Reported EPS"]` — 8.94 leaks here |
| Build event | `pead_event_builder.py:23` (`build_event`) | Computes SUE from wrong eps_actual + wrong eps_history |
| Store | `pead_events_store.py:21` (`append_events`) | Persists corrupted row to `pead_data/events.parquet` |
| Display | `pead_dashboard.py:_tab_live_open` | Shows ticker as qualifies_long when reality is qualifies_short |

POWERGRID 2026-05-15 traced:
- `t.earnings_dates["Reported EPS"]` → **8.94**
- eps_history = [4.19, 3.28, 3.70, 4.61] → mean = 3.945, stdev = 0.578
- SUE = (8.94 − 3.945) / 0.578 = **+8.63 → decile 10 → "BUY"**
- NSE filing actual = ₹2.22 → SUE = (2.22 − 3.945) / 0.578 = **−2.99 → decile 1 → "SELL"**

### Why nselib

Per competitive scan:
- Only free Python lib with NSE-filed quarterly results endpoint (`nselib.capital_market.financial_results_for_equity`)
- Apache 2.0, active 2026 (v2.5.1 May 2026)
- Same source as Screener.in (NSE filings), raw + programmatic
- 163 GitHub stars

Ruled out: jugaad-data (zero fundamentals), Screener.in (no API, ToS-grey), Tijori (no public API), FMP (US-centric).

---

## 3. Objectives & Success Metrics

### Goals

1. **Correct Indian quarterly EPS** for all tickers in PEAD universe (currently 54, expanding to Nifty 200 separately).
2. **Backward-compatible** — all 60+ existing unit tests pass; dashboard tabs still render.
3. **Q/A toggle** — single radio drives all 4 dashboard tabs.
4. **Resilient** — nselib failure auto-falls-back to yfinance; backfill never aborts.
5. **Auditable** — every event row tagged with `eps_source` so we know which feed served it.

### Non-Goals

1. **Replacing yfinance entirely** — yfinance retained for annual `income_stmt` / `balance_sheet` / `cashflow` (Piotroski inputs) and as quarterly-EPS fallback. Per scan, these are at `core/yf_cache.py:59-61` and `core/fundamentals.py:68` — untouched by this migration.
2. **Live intraday refresh** — daily EOD only, unchanged from existing spec.
3. **Universe expansion** to Nifty 200/500 — separate task (called out in pre-mortem E3).
4. **Live broker integration** — paper analysis only.
5. **Screener.in scrape** — explicit out-of-scope; pre-mortem confirms revisit only if nselib + yfinance both fail >10%.
6. **Removing yf_cache** — keep as-is at `pead_data/yf_cache/`. nselib gets its own cache dir.

### Success Metrics (measurable, code-grounded)

| Metric | Current | Target | How to measure |
|---|---|---|---|
| POWERGRID 2026-05-15 eps_actual | 8.94 ❌ | 2.22 ✅ | Read `pead_data/historical_events.parquet`, filter ticker+date |
| Top-10 Nifty quarterly EPS accuracy (last 4 Q) | ~50% | ≥95% | Manual diff against NSE filings; recorded in `pead_data_audit.csv` |
| Unit tests pass | 60/60 | ≥66/66 (6 new nselib tests) | `pytest tests/pead/` |
| `events.parquet` row count after re-backfill (54-ticker universe, 2024-01-01 → 2026-05-31) | 521 | 480–560 (±15%) | `wc -l` post-backfill |
| qualifies_long count over 2yr | 12 | acceptable range: **0–20** | Pre-mortem LB3 — banner if drops to 0 |
| Warm-cache backfill runtime | 41s | ≤ 120s (nselib adds overhead, target is "still fast") | `time python pead_build_history.py …` |
| Dashboard tab render time (per flavor switch) | n/a | < 2s | Manual timing |
| `eps_source` column coverage | n/a | 100% rows tagged | `df["eps_source"].notna().sum() == len(df)` |
| `eps_source == "nselib"` share | 0% | ≥ 80% | Telemetry footer in dashboard |

---

## 4. Target Users & Segments

**Primary:** Self — runs `master_dashboard.py` daily, picks positions from `⚡ PEAD` page.

**Secondary:** Future forkers (open-source repo; STRATEGY_GUIDE.md is for them).

**JTBD:** "When I see a PEAD signal in the dashboard, I want eps_actual to match what NSE filed so I can act without re-verifying on Screener.in."

---

## 5. User Stories & Requirements

### P0 — Must Have (launch-blocking)

| # | User Story | Acceptance Criteria | Code touch points |
|---|---|---|---|
| P0-1 | As a trader, I want quarterly EPS values that match NSE filings | POWERGRID 2026-05-15: `eps_actual == 2.22 ± 0.05`. Same verified for RELIANCE, TCS, INFY, HDFCBANK, ICICIBANK, WIPRO, BAJFINANCE, ITC, LT. Audit CSV produced. | New `core/nse_data.py`; mod `core/fundamentals.py:45`; mod `pead_downloader.py:45` |
| P0-2 | As a trader, I want nselib failures to never crash backfill | If `nselib.capital_market.financial_results_for_equity()` raises for any ticker, yfinance fallback runs silently; backfill always exits 0. Failure logged to `pead_data/data_quality_log.csv`. | `core/fundamentals.py:get_quarterly_eps_history` wrap nselib call in try/except |
| P0-3 | As a trader, I want all existing tests to keep passing | `pytest tests/pead/` reports ≥60 passed, 0 failed. New module has ≥6 new unit tests. | Update fixtures: `tests/pead/test_fundamentals.py:_make_earnings_dates_df`, `test_yf_cache.py:_fake_snap`, `test_event_builder.py:_stub_qhist`, `test_build_history.py:_stub_yf_earnings_dates`. Add `tests/pead/test_nse_data.py`. |
| P0-4 | As a trader, I want a Q/A/Both toggle on the PEAD dashboard | Single `st.radio(['Q','A','Both'])` at top of `pead_dashboard.render()`. All 4 tab functions filter `events.parquet` by `period_type`. State persists across tab clicks via `st.session_state`. | Mod `pead_dashboard.py:_tab_live_open / _tab_backtest / _tab_calendar_heatmap / _tab_screener` — add `flavor` param. |
| P0-5 | As a trader, I want the decile-spread chart to be flavor-aware | Backtest CLI `--flavor Q\|A\|both` writes `pead_decile_spread_Q.csv` / `pead_decile_spread_A.csv` / `pead_decile_spread_both.csv`. Dashboard reads the right one per toggle. | Mod `pead_backtest.py:main()` — derive output filename from `args.flavor`. Mod `pead_dashboard.py:_tab_backtest` to pick file. |
| P0-6 | As a trader, I want a one-time backup of pre-migration data so I can roll back | Before re-backfill, snapshot `pead_data/historical_events.parquet` → `pead_data/historical_events.parquet.pre-nselib.bak`. | Add to `pead_build_history.py` CLI: `--backup` flag (default true) |

### P1 — Should Have

| # | User Story | Acceptance Criteria | Code touch points |
|---|---|---|---|
| P1-1 | As a trader, I want each event row tagged with its data source | New column `eps_source ∈ {'nselib','yfinance_fallback','none'}` in `pead_data/historical_events.parquet` and `pead_data/events.parquet`. Dashboard footer: "Source: X nselib / Y fallback / Z missing" | Schema bump in `pead_event_builder.py:build_event` return dict; mod `pead_dashboard.py` footer; update `pead_events_store.py` if any column-pin logic. |
| P1-2 | As a trader, I want nselib responses cached | Per-ticker pickle cache at `pead_data/nse_cache/<ticker>.pkl`, 7-day TTL, same shape as `core/yf_cache.py`. Warm-cache backfill ≤ 90s. | New module `core/nse_data.py` with `get_quarterly_results(ticker, force=False)`. Mirrors `yf_cache.py` API exactly. |
| P1-3 | As a trader, I want a `pead_data_audit.py` tool to verify accuracy | `python pead_data_audit.py --tickers RELIANCE.NS,POWERGRID.NS,...` prints per-ticker diff vs known-good fixture in `tests/pead/fixtures/known_good_eps.json`. Exit 1 on >5% mismatch. | New file `pead_data_audit.py` at repo root; new fixture file. |
| P1-4 | As a trader, I want the pre-mortem LB3 banner — historical signals revised | When dashboard loads, check `pead_data/last_run_status.json` for `nselib_migration_date`. If event date < that, prepend banner: "Signals before YYYY-MM-DD use revised data — historical SUEs may differ from prior runs." | Mod `pead_dashboard.py:_refresh_strip` (or new `_migration_banner` helper) |

### P2 — Nice to Have / Future

| # | User Story | Acceptance Criteria |
|---|---|---|
| P2-1 | Side-by-side Q vs A live tables when flavor = Both | Two sub-tables in `_tab_live_open` |
| P2-2 | Glossary explains Q vs A flavor | Update `_glossary_expander` in `pead_dashboard.py:42` |
| P2-3 | Sample-size badge on decile chart when N<30 per bucket | Per pre-mortem FF4 |
| P2-4 | Screener.in scrape as 3rd fallback | Per-mortem T1 trigger; out-of-scope this PRD |
| P2-5 | Annual EPS migration to nselib | Currently yfinance income_stmt's Diluted EPS row works OK; revisit if discrepancies found |

---

## 6. Solution Overview

### Architecture (with current file:line refs)

```
BEFORE (broken for India quarterly)
══════════════════════════════════════════════════════════
pead_downloader.py:45 get_actual_eps()           [LIVE, uncached, deprecated attr → None]
    ↓
pead_event_builder.py:23 build_event()
    ↓
core/fundamentals.py:45 get_quarterly_eps_history()
    ↓
core/yf_cache.py:55 get_snapshot()
    ↓
yfinance.Ticker(t).earnings_dates["Reported EPS"]    ← 8.94 for POWERGRID (wrong)


AFTER (nselib primary + yfinance fallback)
══════════════════════════════════════════════════════════
pead_downloader.py:45 get_actual_eps()
    ↓
core/fundamentals.py:get_actual_eps_nse_first(ticker, result_date)   [NEW helper]
    ├─► core/nse_data.py:get_quarterly_results(ticker)          [NEW MODULE]
    │       ↓
    │       core/nse_data.py:_cached_fetch()                    [pead_data/nse_cache/*.pkl]
    │       ↓
    │       nselib.capital_market.financial_results_for_equity(symbol=NSE_SYM)
    │       ↓
    │       returns ₹2.22 for POWERGRID
    │
    └─► [if nselib raises or returns <4 rows] core/yf_cache.py:get_snapshot()    [SAME AS BEFORE]
```

### New module: `core/nse_data.py` (~150 lines)

Public API:
```python
def get_quarterly_results(ticker: str, max_age_days: int = 7, force: bool = False) -> pd.DataFrame | None:
    """Return cached NSE-filed quarterly results for ticker.

    DataFrame columns: period_from, period_to, period_type (Q|A), eps_basic,
                       eps_diluted, eps (preferred), net_profit, revenue,
                       consolidated (bool), audited (bool).
    Index: filing/announce date (datetime).

    Returns None on irrecoverable failure (let caller decide fallback).
    """

def clear(ticker: str | None = None) -> int:
    """Wipe cache. Mirror of core.yf_cache.clear()."""
```

Implementation notes:
- Strip `.NS` suffix before calling nselib (NSE uses bare symbols like `POWERGRID`)
- Prefer consolidated over standalone when both present (FF1 from pre-mortem)
- Pickle cache shape: `{df: DataFrame, fetched_at: date, source: 'nselib'}`
- Cache dir: `pead_data/nse_cache/` (separate from yf_cache to allow independent clear)
- Throttle: 0.3s between bulk calls; reuse `time.sleep` pattern from `pead_universe.py`

### Updated `core/fundamentals.py` (mod, ~30 added lines)

```python
def get_quarterly_eps_history(ticker: str, as_of: date, n: int = 4) -> tuple[list[float], str]:
    """Returns (eps_list, source) where source ∈ {'nselib', 'yfinance_fallback', 'none'}."""
    # Try nselib first
    try:
        df = nse_data.get_quarterly_results(ticker)
        if df is not None and not df.empty:
            df = df[df.index.date < as_of].sort_index(ascending=False)
            df = df[df['period_type'] == 'Q']  # quarterly only
            if len(df) >= n and df['eps'].notna().sum() >= n:
                vals = df['eps'].head(n).tolist()
                return [_safe_float(v) for v in vals], 'nselib'
    except Exception as e:
        # Log to data_quality_log.csv; continue to fallback
        _log_data_issue(ticker, as_of, f"nselib failed: {e}")

    # Fall back to yfinance (existing logic)
    snap = get_snapshot(ticker)
    df = snap.get("earnings_dates")
    # ... existing code unchanged
    return result, 'yfinance_fallback'
```

### Updated `pead_event_builder.py:build_event` (mod)

- Capture source from `get_quarterly_eps_history`
- Add to returned dict: `"eps_source": source`
- New column flows through `events.parquet` schema automatically

### Updated `pead_downloader.py:get_actual_eps` (mod)

- Replace deprecated `t.quarterly_earnings` with nselib-first lookup
- Tag with eps_source

### Updated `pead_dashboard.py` (mod, ~40 added lines)

Add at top of `render()`:
```python
flavor = st.radio('Period type', ['Both', 'Q', 'A'], horizontal=True,
                  key='_pead_flavor', label_visibility='collapsed')
```

Modify each tab function signature to accept `flavor`. Inside tabs:
```python
ev = pd.read_parquet(DATA / 'events.parquet')
if flavor != 'Both':
    ev = ev[ev['period_type'] == flavor]
```

Add migration banner in `_refresh_strip()`.

Add source-counter footer at bottom of `render()`:
```python
src_counts = ev['eps_source'].value_counts().to_dict()
st.caption(f"Data sources — nselib: {src_counts.get('nselib',0)} · "
           f"yfinance fallback: {src_counts.get('yfinance_fallback',0)}")
```

### Updated `pead_backtest.py` (mod)

- Derive decile-spread output filename from `--flavor`: `pead_decile_spread_{flavor}.csv`
- Audit step also writes `pead_data_audit.csv` (per P1-3)

### Schema additions to `events.parquet`

| New column | Type | Default | Source |
|---|---|---|---|
| `eps_source` | str | `'none'` | tagged by `get_quarterly_eps_history` |

(Total goes from 16 → 17 columns. Dedup key unchanged: `(ticker, result_date, period_type)`.)

### Test fixture updates required (per scan §12)

| File:Line | Change |
|---|---|
| `tests/pead/test_fundamentals.py:16-28` | Add nselib mock variant of `_make_earnings_dates_df`; new test for nselib-primary path |
| `tests/pead/test_yf_cache.py:20-21` | Untouched (yf_cache itself doesn't change) |
| `tests/pead/test_event_builder.py:12-13` | Update `_stub_qhist` to return tuple (eps_list, source) |
| `tests/pead/test_build_history.py:_stub_yf_earnings_dates` | Add `_stub_nse_results` fixture for nselib path |
| **NEW** `tests/pead/test_nse_data.py` | 6+ tests: cache hit/miss/stale/force, schema normalize, consolidated-vs-standalone, ticker symbol stripping |
| **NEW** `tests/pead/fixtures/nse_quarterly_sample.pkl` | Pickled fixture from real nselib response for RELIANCE |
| **NEW** `tests/pead/fixtures/known_good_eps.json` | Hand-verified EPS for 10 Nifty tickers for audit script |

---

## 7. Open Questions

| # | Question | Default if unresolved | Owner | Deadline |
|---|---|---|---|---|
| Q1 | nselib `financial_results_for_equity` schema — exposes Diluted vs Basic EPS, or just Net Profit? | Compute eps = net_profit / shares_outstanding (yfinance fallback for shares) | Implementer Phase 1 spike | Day 1 |
| Q2 | nselib supports per-ticker `symbol=` arg, or bulk-only? | Bulk-fetch once/day, index in memory | Implementer Phase 1 spike | Day 1 |
| Q3 | NSE symbol mapping — `POWERGRID.NS` → `POWERGRID`. Edge cases (`M&M`, `BAJAJ-AUTO`)? | Reuse existing mapping in `core/nse_announce.py:nse_symbol_to_yf` inverse | Implementer | Day 1 |
| Q4 | Consolidated vs standalone — both filings appear, which to use? | Prefer consolidated; flag in `eps_source` if fallback | Self decision | Pre-build |
| Q5 | Annual EPS — does NSE expose separate annual filing or derived from Q4? | Scope this PRD to quarterly only; annual stays on yfinance | Self decision | Pre-build |
| Q6 | Pre-mortem E1 — does the strategy have any edge at all? | Run decile-spread sanity check post-migration; if D10 − D1 ≤ 0.5%, don't ship; escalate | Self | Post-Phase 4 |

---

## 8. Timeline & Phasing

### Phase 1 — nselib spike (Day 1, 1.5h) — **HARD GATE**

- `pip install nselib`
- Direct probe: `nselib.capital_market.financial_results_for_equity(symbol='POWERGRID', ...)` for 2026 Q4
- Resolve Q1, Q2, Q3, Q4
- **Exit criteria:** confirm POWERGRID 2026-Q4 EPS ≈ 2.22 via nselib. If not, STOP, re-evaluate (per pre-mortem LB1).
- Output: `docs/superpowers/spikes/2026-05-31-nselib-spike.md` with schema notes

### Phase 2 — `core/nse_data.py` + cache (Day 1, 2h)

- Create module with `get_quarterly_results()` + `clear()`
- Pickle cache at `pead_data/nse_cache/`
- Add `tests/pead/test_nse_data.py` with 6+ tests (cache hit/miss/stale/force/consolidated/symbol-strip)
- Add fixture `tests/pead/fixtures/nse_quarterly_sample.pkl`

### Phase 3 — Wire into `core/fundamentals.py` + `pead_downloader.py` (Day 1, 1.5h)

- Modify `get_quarterly_eps_history` — nselib-first, yfinance fallback, returns tuple (eps_list, source)
- Modify `pead_downloader.py:get_actual_eps` — use new helper
- Modify `pead_event_builder.py:build_event` — accept + persist `eps_source`
- Update test fixtures (`_stub_qhist`, `_make_earnings_dates_df`, etc.)

### Phase 4 — Re-backfill + audit (Day 1, 1h)

- Backup: `cp pead_data/historical_events.parquet pead_data/historical_events.parquet.pre-nselib.bak`
- `rm pead_data/historical_events.parquet`
- `python pead_build_history.py --start 2024-01-01 --end 2026-05-31`
- Run `python pead_data_audit.py --tickers RELIANCE.NS,POWERGRID.NS,TCS.NS,INFY.NS,HDFCBANK.NS,ICICIBANK.NS,WIPRO.NS,BAJFINANCE.NS,ITC.NS,LT.NS`
- **Exit criteria:** ≥95% accuracy vs hand-verified known_good_eps.json. Per pre-mortem E1: decile-10 − decile-1 fwd-60d ≥ 0.5%, else escalate.

### Phase 5 — Q/A dashboard toggle (Day 2, 1.5h)

- Add radio at top of `pead_dashboard.render()`
- Pass `flavor` to all 4 tab functions
- Decile-spread CSV split by flavor in `pead_backtest.py:main`
- Source-counter footer
- Migration banner per P1-4

### Phase 6 — Backtest re-run + verify (Day 2, 30min)

- `python pead_backtest.py --flavor Q --start 2024-06-01 --end 2026-05-31`
- `python pead_backtest.py --flavor A --start 2024-06-01 --end 2026-05-31`
- `python pead_backtest.py --flavor both --start 2024-06-01 --end 2026-05-31`
- Manual click-through on dashboard for each flavor

### Phase 7 — Memory + docs (Day 2, 30min)

- Update memory file `pead_strategy.md` — add data-source migration entry
- Update `STRATEGY_GUIDE.md` PEAD section: "as of 2026-05-31, quarterly EPS sourced from NSE filings via nselib"
- Update `README.md` (if any) noting nselib dependency
- Commit all in one final commit; close out PRD

**Total: ~8h work, 2 days.**

### Risks (per pre-mortem; full register in companion doc)

| Risk | Severity | Mitigation |
|---|---|---|
| LB1: nselib EPS field semantics unclear | Launch-blocking | Hard gate in Phase 1 |
| LB2: nselib has no per-ticker API | Launch-blocking | Bulk + index strategy if needed |
| LB3: qualifies_long drops to 0 (correct behavior, looks broken) | Launch-blocking | Banner + side-by-side OLD/NEW audit print |
| FF1: consolidated vs standalone confusion | Fast-follow | Filter logic + log |
| FF2: stale cache misses recent results | Fast-follow | `--no-cache` flag |
| FF3: Q/A toggle doesn't filter Live tab | Fast-follow | Tab-level filter on `period_type` |
| FF4: Annual decile spread too few events | Fast-follow | Sample-size badge |

---

## Approval Gates

- [ ] Phase 1 spike confirms POWERGRID nselib EPS ≈ 2.22 **(LB1)**
- [ ] Phase 1 spike confirms per-ticker query works OR bulk-index strategy locked in **(LB2)**
- [ ] Phase 4 audit reports ≥95% accuracy on 10-ticker hand-check **(P0-1)**
- [ ] Phase 4 decile-spread sanity check passes — D10 fwd-60d − D1 fwd-60d ≥ 0.5% post-migration **(E1)**
- [ ] All 66+ unit tests green pre-merge **(P0-3)**
- [ ] Dashboard renders for Q, A, Both flavors with no error **(P0-4)**
- [ ] Backup file `historical_events.parquet.pre-nselib.bak` exists before re-backfill **(P0-6)**
- [ ] Banner per P1-4 visible in dashboard
- [ ] `STRATEGY_GUIDE.md` updated **(Phase 7)**
- [ ] Pre-mortem E2 deadline noted in MEMORY.md: paper-trade ₹1L by 2026-06-15 if this ships
- [ ] Pre-mortem E3 follow-up: Nifty 200 universe expansion task created
