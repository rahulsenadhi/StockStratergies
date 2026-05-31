# Competitive Analysis: Indian Stock Fundamentals Data Source

**Date:** 2026-05-31
**Question:** Which data source to feed PEAD strategy's quarterly EPS, balance sheet, and P/B requirements for NSE stocks?
**Current source:** yfinance (US Yahoo Finance) — **shown to misreport Indian quarterly EPS** (POWERGRID 2026-Q4 reported as 8.94 vs correct ~2.22 from NSE filings).

---

## Market Overview

Indian retail quant tooling sits between two extremes. **Free libraries** (jugaad-data, nselib) scrape NSE/BSE public endpoints — accurate but hobby-maintained. **Paid platforms** (Tijori, FMP, Sensibull) target either institutions (no public API) or US-centric retail (poor India coverage). **Screener.in** is the de-facto Indian retail standard but offers no programmatic API. yfinance bridges the gap globally but mangles Indian quarterly EPS (annual numbers leak into quarterly slots, units sometimes off, consolidated vs standalone mixed). Result: serious Indian quant work requires either NSE-direct scraping or a paid Indian-specific feed.

---

## Competitive Landscape

| Source | Type | Target | Positioning | Strength | Weakness |
|---|---|---|---|---|---|
| **yfinance** | Free OSS | Global retail | Universal market data wrapper | One-stop for global markets | India quarterly EPS unreliable |
| **jugaad-data** | Free OSS | Indian retail quants | NSE-native OHLCV + bhavcopy | Lightweight price fetcher | **Zero fundamental data** |
| **nselib** | Free OSS | Indian retail quants | NSE-native including financials | Only free lib with NSE quarterly results endpoint | Shallow fundamentals (no balance sheet detail) |
| **Screener.in** | Freemium web | Indian retail investors | Best Indian fundamental UI | 10+yr balance sheet, PnL, ratios | No official API; scrape required |
| **Tijori Finance** | Paid SaaS | Indian institutions | Vendor-licensed Indian fundamentals | Exchange-sourced, high quality | No public API, B2B-only pricing |
| **FinancialModelingPrep India** | Paid API | Global devs | Mature API stack | Clean docs + SDK | Minimal India coverage; US-first |

---

## Feature Comparison Matrix

| Capability | yfinance | jugaad-data | nselib | Screener.in | Tijori | FMP |
|---|---|---|---|---|---|---|
| NSE quarterly EPS | ⚠️ wrong values | ❌ none | ✅ shallow | ✅ via scrape | ✅ deep | ❌ minimal |
| Annual EPS / income stmt | ✅ | ❌ | ⚠️ partial | ✅ | ✅ | ⚠️ |
| Balance sheet (annual) | ✅ | ❌ | ⚠️ partial | ✅ | ✅ | ⚠️ |
| P/B ratio | ⚠️ stale | ❌ | ✅ | ✅ | ✅ | ⚠️ |
| OHLCV pricing | ✅ | ✅ | ✅ | ❌ | ✅ | ⚠️ |
| Corporate-announce / result dates | ❌ | ✅ | ✅ | ✅ | ✅ | ❌ |
| Python pip install | ✅ | ✅ | ✅ | ❌ (scrape) | ❌ | ✅ |
| Free | ✅ | ✅ | ✅ | partial | ❌ | partial |
| ToS / license clarity | Apache | YOLO* | Apache 2.0 | Grey zone | B2B contract | Standard SaaS |
| Maintenance activity 2026 | ✅ active | ✅ active | ✅ active | n/a | n/a | ✅ active |
| Indian-quarterly accuracy | ❌ | n/a | ✅ | ✅ | ✅ | ❌ |

*YOLO license: non-standard but permissive. Not a blocker for personal use.

---

## Positioning Map

```
  India accuracy ↑
                │  Tijori        Screener.in
                │  ●             ●
                │
                │           nselib
                │           ●
                │
                │           jugaad-data
                │           ●
                │
                │   FMP            yfinance
                │   ●              ●
                └──────────────────────────────→
                Programmatic-API friendliness →
```

Top-right quadrant (high accuracy + programmatic) is **Tijori (paid, no public API)**.
Best free spot in that quadrant = **nselib**.

---

## Key Finding That Changes the Recommendation

**jugaad-data does NOT provide fundamentals.** Price/volume only. I previously recommended it for EPS data — that was wrong.

The only free, open-source, programmatic, Indian-native fundamentals source is **nselib**. It exposes `capital_market.financial_results_for_equity()` returning NSE-filed quarterly numbers (the same source as Screener.in, but raw).

---

## Differentiation Opportunities

1. **nselib + yfinance hybrid** (Recommended Primary)
   nselib for NSE-filed quarterly EPS + announce dates → solves POWERGRID 8.94 → 2.22 problem.
   yfinance retained for income_stmt / balance_sheet / P/B (Piotroski inputs) where it still works.
   **Cost: free. Risk: hobby-lib breakage.**

2. **Screener.in scrape** (Recommended Fallback)
   When nselib fails on a ticker, scrape the Screener page for that one stock.
   Adds ~3yr deeper history + cleaner annual data.
   **Cost: free (or ₹4,999/yr premium for cleaner data). Risk: ToS grey zone.**

3. **Tijori paid feed** (Future production-grade)
   Only if hobby libs become unreliable AND you're trading real capital >₹10 lakh.
   **Cost: B2B contract, likely ₹10–50k/yr. Risk: vendor lock-in.**

---

## Competitive Threats

1. **NSE API drift** — NSE silently changes endpoint shapes ~2× per year. Both nselib and jugaad-data have lagged a week or two before patching. Mitigation: cache aggressively, retry with backoff, yfinance fallback.
2. **Screener.in turning off scraping** — they have a paid tier, may eventually add cloudflare. Mitigation: don't bake critical dependency on scraping; treat as backup only.
3. **yfinance dropping Indian listings** — they've narrowed coverage before. Mitigation: nselib-first reduces yfinance exposure to non-critical paths.

---

## Recommendations

### Primary: **nselib** (replace yfinance for quarterly EPS)

**Why:**
- Only free, Apache-2.0 licensed, programmatic source for NSE-filed quarterly EPS
- Solves the data-quality bug (POWERGRID 8.94 → 2.22)
- ~150 KB install, pip-only, no auth, no API key
- Active 2026 maintenance (v2.5.1 May 2026)
- Same data source as Screener.in (NSE filings) but raw + programmatic

**Use for:** quarterly EPS, annual EPS, announce dates, P/B (where exposed).

### Secondary: **yfinance** (kept as fallback)

**Why:**
- Already integrated
- income_stmt / balance_sheet / cashflow still work for Piotroski (the bug was specific to quarterly EPS, not annual financials)
- Universal fallback when nselib lib breaks during NSE API drift

**Use for:** Piotroski 9-component inputs, fallback EPS when nselib returns empty.

### Skip:
- **jugaad-data** — no fundamentals (price-only). Adds no value over yfinance for this use case.
- **Screener.in scrape** — ToS grey, fragile, no programmatic API. Worth it only if nselib + yfinance both fail on critical tickers (rare).
- **Tijori** — no public API. Re-evaluate when scaling to real capital.
- **FMP** — minimal India coverage. Not a contender.

---

## Implementation Plan (high-level)

1. `pip install nselib`
2. `core/fundamentals.py` — new function `get_quarterly_eps_nse(ticker, as_of, n=4)` using `nselib.capital_market.financial_results_for_equity`
3. Update `get_quarterly_eps_history()` — call nselib first, fall back to yfinance only if nselib returns empty
4. Cache nselib responses in existing `core/yf_cache.py` (rename to `core/fundamentals_cache.py`)
5. Re-run PEAD backfill: `python pead_build_history.py --start 2024-01-01 --end 2026-05-31`
6. Verify POWERGRID 2026-05-15 now reports ≈2.22, not 8.94
7. Add `period_type` filter (Q / A / Both toggle) to PEAD dashboard tabs

ETA: 2h with tests.

---

**Sources:**
- [jugaad-data GitHub](https://github.com/jugaad-py/jugaad-data)
- [nselib GitHub](https://github.com/RuchiTanmay/nselib)
- [nselib PyPI v2.5.1](https://pypi.org/project/nselib/)
- [Screener.in](https://www.screener.in/)
- [Tijori Finance](https://www.tijorifinance.com/)
- [FinancialModelingPrep](https://site.financialmodelingprep.com/pricing-plans)
