# Pre-Mortem: PEAD nselib Migration

**Date:** 2026-05-31
**Status:** Draft
**Scoped PRD:** `docs/superpowers/prds/2026-05-31-pead-nselib-migration.md`
**Imagined failure date:** 2026-06-07 (1 week post-merge)

> *"It's a week after merge. PEAD is producing worse signals than before, the dashboard is throwing errors, and I'm manually re-checking every ticker on Screener.in like I was doing before the migration. What went wrong?"*

---

## Risk Summary

- **Tigers**: 9 (3 launch-blocking, 4 fast-follow, 2 track)
- **Paper Tigers**: 4
- **Elephants**: 3

---

## Launch-Blocking Tigers

| # | Risk | Likelihood | Impact | Mitigation | Owner | Deadline |
|---|---|---|---|---|---|---|
| LB1 | **nselib's "EPS" is not what we think — could be Basic EPS, Diluted EPS, Adjusted EPS, or even raw Net Profit / shares.** PRD Q1 calls this out but defers to Phase 1 spike. If the spike shows nselib doesn't expose EPS at all (only Net Profit), the whole plan needs revision. | Med | High — entire migration premise breaks | Phase 1 spike MUST happen first. Hard gate: if nselib POWERGRID 2026-Q4 EPS ≠ 2.22 (±0.05), STOP and re-evaluate. Don't write any other code until spike result confirmed. Document the exact field name + derivation in `core/nse_data.py` docstring. | Self | Day 1 morning |
| LB2 | **nselib `financial_results_for_equity()` doesn't accept ticker-specific queries — only date-range bulk queries.** If true, every "get this ticker's quarterly EPS" call fetches the whole NSE corpus and filters locally. Cache size explodes, latency increases 10×. | Med | High — performance target (90s warm) unachievable | Phase 1 spike second priority: confirm `symbol=` arg works. If not, cache the bulk pull once per day and index it. Add to PRD as design constraint. | Self | Day 1 morning |
| LB3 | **Re-backfill drops qualifies_long from 12 to 0 once SUEs are correct.** Old yfinance-derived signals were wrong but produced trades. Real signals may be much rarer (POWERGRID 2.22 vs 3.94 mean → SUE = -3, bottom decile, not top). User may interpret "0 trades" as broken when it's actually correct behavior. | High | Med — confusion + possible rollback decision | Phase 4 audit prints a side-by-side: 'OLD SUE / NEW SUE' for every event. Dashboard banner: "Switched to NSE data 2026-05-31 — historical signals are revised, not lost." Document baseline in MEMORY.md. | Self | Phase 4 |

---

## Fast-Follow Tigers

| # | Risk | Likelihood | Impact | Planned Response | Owner |
|---|---|---|---|---|---|
| FF1 | **NSE consolidated vs standalone filings handled wrong.** POWERGRID files both. PRD default says "prefer consolidated" but nselib may not flag which row is which. SUE could be computed on standalone-EPS using consolidated-prior history → garbage. | Med | High | Add filter logic in `core/nse_data.py`: parse `auditedFlag` / `consolidated` field. Default to consolidated; log when fallback to standalone. Unit test with both fixtures. | Implementer |
| FF2 | **nselib cache files become stale silently.** 7-day TTL means a result declared Mon may not be reflected until following Mon. PEAD signals miss the drift window if you back-test ranges spanning a stale period. | Med | Med | Force-refresh `core.fundamentals_cache` on any backfill run. Add `--no-cache` flag to `pead_build_history.py`. Status JSON should report oldest cache entry. | Implementer |
| FF3 | **Q/A toggle doesn't filter `live_signals.csv` properly** because that CSV currently has mixed Q+A events. Live tab shows annual stocks bleeding into quarterly view. | Med | Low — UI confusion | Live tab respects toggle; if "Both" selected, two sub-tables. Add toggle indicator above each table. | Implementer |
| FF4 | **Decile spread for Annual flavor has too few events to plot meaningfully.** 54 tickers × ~1-2 annual results in 2yr window = ~80 events. Splitting into 10 deciles = 8 per bucket. Cohort window collapses to "everything." | High | Low — diagnostic noisy but not wrong | Display N per decile alongside spread chart. If N < 30 per decile, show "insufficient sample" badge. Recommend expanding universe to Nifty 200 in follow-up. | Implementer |

---

## Track Tigers

| # | Risk | Trigger condition |
|---|---|---|
| T1 | **NSE API endpoint changes mid-quarter.** Both nselib and yfinance fallback could break simultaneously. | Monitor `pead_data/last_run_status.json` daily. Alert when `error: NSE_BLOCKED` appears 2 days in row. Action: hotfix nselib version OR add Screener.in scrape as 3rd fallback. |
| T2 | **EPS data accuracy degrades for mid-caps as universe expands to Nifty 200.** NSE filings cleaner for large caps; smaller companies may have inconsistent reporting. | After Nifty 200 expansion (separate task), run audit on bottom-100-mcap tickers. If >10% mismatch vs Screener, fall back to manual list of "yfinance-only" tickers. |

---

## Paper Tigers

| Concern | Why it's overblown |
|---|---|
| **"nselib could be abandoned next year."** | Active 2026 maintenance (v2.5.1 May). Even if abandoned, we own the cache + yfinance fallback. Worst case: 4-hour effort to clone the working endpoint code into our repo. Not a launch blocker. |
| **"yfinance might break too, leaving us with no fallback."** | Has been continuously maintained since 2017. Used by millions. India coverage degrades occasionally but rarely zero. If both die simultaneously, that's existential — but the probability over 12 months is sub-5%. |
| **"Performance regression from extra HTTP round-trip to NSE."** | Mitigated by aggressive caching. Cold backfill 2m33s already includes a yfinance pass; adding nselib makes cold worse but warm cache is identical. Daily refresh hits warm cache. |
| **"Q/A toggle adds UI complexity that confuses casual users."** | Default = "Both" preserves existing behavior. Toggle is opt-in. Casual user never touches it. Not a real risk. |

---

## Elephants in the Room

### E1: **"PEAD might not have a real edge in Indian markets anyway."**

The whole strategy might be a dressed-up cargo cult. Indian market is dominated by retail, FII flows, and announcement-day price gaps that close intraday. The 60-day drift premise comes from US academic literature on US markets with different microstructure. After fixing the data, we may discover decile 10 fwd-60d ≈ decile 1 fwd-60d, i.e. **no edge at all**.

**Conversation starter:** "Before we invest 7 hours migrating data sources, can we run a back-of-envelope sanity check? Plot decile 10 vs decile 1 fwd-60d return for the *current* data, then again post-migration. If both show no spread, the strategy itself is broken regardless of data source."

Concrete check: Phase 4 audit should print **decile spread DELTA** (old vs new). If new spread is also flat, escalate — don't ship.

### E2: **"You'll keep migrating data sources forever rather than trading."**

This is the third data-quality round (Piotroski coverage fix → cache layer → now nselib). Pattern suggests the actual blocker isn't data, it's **lack of confidence to deploy real money**. Each migration is a delay tactic.

**Conversation starter:** "Set a hard deadline: if the post-migration backtest shows the predicted edge AND POWERGRID test passes, commit ₹1 lakh to paper trading for 1 month. If you find a 4th data-quality reason to delay, that's the signal to stop building and start paper-trading with whatever we have."

### E3: **"The PEAD universe is too small (54 tickers) for the strategy to matter even if the data is perfect."**

Even with correct EPS, 54 stocks × 4 quarters × 2 years = 432 events. After filtering for top decile + Piotroski≥7 + P/B≤sector-median, you get the 12 qualifying events you see now. With 4-12 trades over 2 years, statistical significance is unreachable. The data-source fix is solving the wrong problem if universe stays narrow.

**Conversation starter:** "Universe expansion to Nifty 200 should be the NEXT task after nselib migration. Add it to MEMORY.md as a hard follow-up. Otherwise we'll have clean signals on a sample too small to trust."

---

## Go/No-Go Checklist

- [ ] **LB1 mitigated** — Phase 1 spike confirms nselib returns POWERGRID 2026-Q4 EPS ≈ 2.22
- [ ] **LB2 mitigated** — nselib supports per-ticker queries OR bulk-fetch+local-index strategy locked in
- [ ] **LB3 mitigated** — Audit script prints OLD/NEW SUE side-by-side; banner added; baseline documented
- [ ] **FF1 plan filed** — consolidated-vs-standalone handling in `core/nse_data.py`
- [ ] **FF2 plan filed** — `--no-cache` flag exists; cache age in status JSON
- [ ] **FF3 plan filed** — Q/A toggle filters Live tab CSVs
- [ ] **FF4 plan filed** — sample-size badge on decile chart
- [ ] **T1 monitoring** — daily check on `last_run_status.json`
- [ ] **E1 conversation had** — decile-spread sanity check is hard gate
- [ ] **E2 conversation had** — paper-trade deadline set
- [ ] **E3 conversation had** — Nifty 200 expansion is queued as next task
- [ ] **Rollback plan** — keep `pead_data/historical_events.parquet.pre-nselib.bak` snapshot before re-backfill
- [ ] **Support brief** — STRATEGY_GUIDE.md updated noting data-source change + how to interpret revised signals

---

## Recommendation

**Conditional GO**, gated on:

1. **Phase 1 spike must run BEFORE any other code change.** No `nse_data.py` until spike confirms POWERGRID EPS = 2.22 via nselib.
2. **Decile-spread sanity check from E1 must run BEFORE merge.** If post-migration decile-10 - decile-1 spread ≤ 0.5%, do not merge — the strategy itself is the bug, not the data source.
3. **Set hard deadline (E2): 2026-06-15 paper-trade start.** If migration drags past that, fall back to current data and accept the quarterly EPS bug for now.
4. **Pre-create Nifty 200 expansion task in plan (E3) — required follow-up.**

If those 4 gates pass: build. If LB1 or E1 fails: stop, escalate, don't build.
