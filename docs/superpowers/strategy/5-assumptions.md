# Assumption Map — Personal Algo Platform

**Date:** 2026-05-31
**Scope:** All Phase A-D items in OST (`4-ost.md`) — Formula DSL, Strategy Library, Confidence Tiers, nselib Migration, Walk-Forward, Bayesian Significance Test
**Method:** Devil's advocate × 4 risk areas (Value / Usability / Viability / Feasibility)

Confidence scale: **L** = guessing, **M** = some evidence, **H** = proven
Risk-if-wrong: **L** = nuisance, **M** = lose months, **H** = entire project dead

---

## Value Assumptions

| # | Assumption | Confidence | Risk-if-wrong | How to test |
|---|---|---|---|---|
| V1 | **Indian retail can sustain Nifty +10pp alpha via systematic strategies (after slippage, fees, taxes).** | M | **H** — North Star unachievable | Track aggregate live portfolio for 12 mo; compare to benchmark net of all costs. Already have Monthly Rotation +12.7% alpha for 4yr — partial evidence. |
| V2 | **Walk-forward validation reveals current strategies' alpha as real, not regime luck.** | L | **H** — could discover 3 of 4 strategies overfit | Run walk-forward on Monthly Rotation first (highest stated alpha). If OOS Sharpe drops >50%, the alpha is regime-dependent. |
| V3 | **Research papers contain extractable, NSE-applicable strategy logic.** | M | M — manual coding stays slower but works | Pick 5 known Indian papers; manually extract specs; rate "how mechanical was the translation" 1-10. |
| V4 | **Formula DSL handles 80% of strategies you'd want to write.** | M | M — fall back to Python everywhere | Translate top 5 brainstorm-pick strategies to DSL on paper. Count expressible vs needs-Python. |
| V5 | **PEAD has a real edge in Indian markets (vs published-only-in-US).** | L | M — entire PEAD branch wasted | Per pre-mortem E1: decile-spread test post-nselib migration. If D10 − D1 ≤ 0.5%, kill PEAD. |
| V6 | **Confidence tiers (60-day paper before deploy) actually reduce bad-deploy losses.** | L | L — at worst, slower; you keep tier behavior anyway | Look at past trades retrospectively: would 60-day paper-trade have filtered out the losers? Backward simulation. |
| V7 | **The vision "library of edges" matches what you want once built.** | M | H — wrong vision = 6 months wasted | Re-read `1-product-vision.md` in 90 days. Does it still feel right? Or has it drifted toward "fast trading"? |

---

## Usability Assumptions

| # | Assumption | Confidence | Risk-if-wrong | How to test |
|---|---|---|---|---|
| U1 | **You'll use the DSL instead of dropping back to Python.** | L | M — DSL becomes dead code | After DSL ships, track ratio: # DSL strategies created vs # Python strategies created in 90d. Target ≥50% DSL. |
| U2 | **Strategy Library page reduces friction enough to use weekly.** | M | L — keep using current scattered files | After ship, self-time "find KPI for strategy X" before/after. Target: 5s vs 30s. |
| U3 | **Confidence tiers visible enough to act on (not just decoration).** | M | L — tier exists, but you override it anyway | Track over 90d: # of "Live" deploys that bypassed paper-trade tier. Target = 0. |
| U4 | **Q/A toggle on PEAD page is intuitive without explanation.** | M | L — minor UX confusion | Self-test: 7 days after ship, can you remember which flavor is selected without checking? |
| U5 | **Glossary tooltips are read (not ignored).** | M | L — terms stay confusing, friction continues | Track hover events if instrumentable; else self-report after 30d use. |
| U6 | **Open-source forkers (year 2) figure out the codebase in <1h.** | L | L (today) — defer to release time | When ready, ask 1 friend to clone + run. Time to first backtest. Target <60min. |
| U7 | **Streamlit can scale to 10+ strategies in library without rewriting in React/Next.** | M | M — re-platform = 2-month delay | Build at 10 strategies, profile dashboard load. If >5s, optimize or rewrite. |

---

## Viability Assumptions

| # | Assumption | Confidence | Risk-if-wrong | How to test |
|---|---|---|---|---|
| Vi1 | **Trading personal capital on app-generated signals stays within SEBI's "self-trading" exemption.** | H | H — legal issue if marketed | Personal use only; no advisory claims; no commercialization for now. Talk to a CA if commercializing later. |
| Vi2 | **You'll keep maintaining this for 3+ years (the time needed for moat to compound).** | M | H — project dies before paying off | Re-evaluate motivation every 6mo. Set hard "kill or commit" milestones (per pre-mortem E2: paper-trade ₹1L by 2026-06-15). |
| Vi3 | **Free data sources (nselib, yfinance, jugaad) suffice for the 5-year horizon.** | M | M — forced upgrade to ₹10–50k/yr feed | Quarterly audit (S3.2 in OST). If >5% mismatch rate persists, budget paid feed. |
| Vi4 | **Hosting cost stays at ~₹0 (localhost).** | H | L — even cloud Streamlit on Hugging Face is free at low scale | Already true. Stays true unless you ship public version. |
| Vi5 | **Time investment is sustainable (≤10h/week average).** | L | H — burnout = project dies | Weekly self-track hours. Alert >15h/week 3 weeks in a row → cut scope. |
| Vi6 | **Open-sourcing later (year 2+) doesn't force compliance overhead (advisory disclaimers, etc.).** | M | M — adds dis-incentive to OSS | Pre-check SEBI rules for OSS code release. Add disclaimer template to repo before OSS push. |
| Vi7 | **Indian tax treatment of algo-traded gains is same as discretionary (STCG/LTCG).** | H | L — accounting nuance, not blocker | Already known: no special algo tax in India. Re-verify with CA when going live. |

---

## Feasibility Assumptions

| # | Assumption | Confidence | Risk-if-wrong | How to test |
|---|---|---|---|---|
| F1 | **nselib quarterly EPS field is the right value (Diluted EPS, consolidated).** | L | **H** — entire migration premise breaks | Pre-mortem LB1: Phase 1 spike. Probe POWERGRID 2026-Q4 directly. Hard gate. |
| F2 | **nselib supports per-ticker queries OR bulk-fetch + index works.** | M | M — performance regression | Per pre-mortem LB2: Phase 1 spike. If bulk-only, design cache around it. |
| F3 | **NSE API doesn't change shape during the 3-year project window.** | L | M — periodic hot-fixes required | yfinance fallback always active. Monitor `last_run_status.json` daily. |
| F4 | **`pandas.eval` is expressive enough for the formula DSL, no need for custom parser.** | M | M — build a Lark grammar = 2 extra weeks | Spike: try 10 known formulas in `pandas.eval`. Count expressible. |
| F5 | **`polars` or `duckdb` upgrade can speed up hot paths 10× when needed.** | M | L — defer until 500+ tickers | Profile cohort decile loop at 500-ticker universe. If <2s, no upgrade needed. |
| F6 | **Walk-forward validation is computationally tractable for 10yr × 200 tickers × 4 strategies.** | M | L — accept slower runs OR add concurrency | Estimate: 10yr × 4 quarters per year × 200 tickers × 4 strategies × ~100ms per event = ~16min total. Acceptable. |
| F7 | **Bayesian significance test (bootstrap) at N=1000 resamples runs in <5s on typical event set.** | M | L — reduce N | Quick benchmark on PEAD events; if >5s, drop to N=500. |
| F8 | **Streamlit doesn't crash with 50+ strategies registered.** | L | L — page-load slowdown but not crash | Stress-test with mocked dummy strategies. Profile load. |
| F9 | **LLM (Claude API) reliably extracts strategy spec from paper PDF.** | L | M — fall back to manual extraction | 5-paper spike (V3 above). Grade output. |
| F10 | **Reproducibility seal (git SHA + data hash) covers all sources of nondeterminism.** | M | M — silent drift in backtest results | After implementation, run same backtest 10× over 1 month. Byte-diff. |

---

## TOP 5 Highest-Risk Assumptions (rank by Risk-if-wrong × Confidence-gap)

### 🔴 #1 — **V2: Walk-forward will validate current alpha as real**

- **Why riskiest:** If false, **the whole vision is built on regime luck.** Monthly Rotation might be a 2022–2026 phenomenon. The project's economic premise dies.
- **Test (cheap):** Implement walk-forward harness on Monthly Rotation first. 1 day's work.
- **Pre-decision:** Commit upfront to retire any strategy whose OOS Sharpe drops >50%. Write the rule before seeing results.

### 🔴 #2 — **F1: nselib quarterly EPS is the right field**

- **Why riskiest:** PRD already calls this out as launch-blocker LB1. Entire data migration depends on it.
- **Test:** Phase 1 spike — pip install + 30 minutes of probing. Gate before any other code.
- **Pre-decision:** If POWERGRID 2026-Q4 EPS via nselib ≠ ~2.22, abort migration; explore Screener.in scrape (despite ToS risk) or budget paid feed.

### 🔴 #3 — **Vi2: You'll maintain this for 3+ years**

- **Why riskiest:** Solo project mortality is real. Most personal projects die within 18 months. The defensibility argument depends on time.
- **Test:** Set hard milestones with kill conditions:
  - Aug 2026 (3mo): paper-trade ₹1L live
  - Feb 2027 (9mo): 3 deployed strategies, real capital
  - May 2027 (12mo): aggregate Nifty + 5pp YoY
- **If milestones missed by 2+ months:** honest review — kill or commit, no zombie middle.

### 🟠 #4 — **V1: Indian retail can hit Nifty +10pp net of costs**

- **Why high-risk:** Brokerage + STT + slippage on Indian small/mid-caps can erode 2-4pp alpha. The "+10pp" target may be 6-8pp realistically.
- **Test:** Re-run Monthly Rotation backtest with realistic cost model (0.1% per side + STT + slippage 0.3% per trade). Compare to gross.
- **Pre-decision:** If realistic Monthly Rotation alpha drops to <6pp, lower North Star to "Nifty + 6pp" and re-baseline.

### 🟠 #5 — **U1: You'll actually use the formula DSL**

- **Why high-risk:** If DSL adoption fails, you've burned 2 weeks on dead code AND the "throughput" thesis (10× strategies/year) fails.
- **Test:** Mock the DSL UI on paper before building. Show yourself 1 week later — would you reach for it?
- **Pre-decision:** Ship DSL with starter pack of 5 known formulas (S1.4 in OST). If you still write Python for the 6th, post-mortem why before continuing investment.

---

## Cheap Test Plan (next 2 weeks)

| Test | Effort | Assumption tested | Action if failed |
|---|---|---|---|
| Cost-aware Monthly Rotation re-backtest | 2h | V1 | Lower North Star |
| Walk-forward harness on Monthly Rotation | 4h | V2 | Retire strategy if OOS Sharpe collapses |
| nselib POWERGRID probe | 30min | F1 | Abort migration, explore Screener |
| Hand-extract 1 research paper to DSL spec | 2h | V3 + V4 | Skip LLM extractor, write DSL by hand |
| Re-read vision in 30 days | 5min | V7 | If feels off, rev2 the vision |

**Total: ~9 hours to de-risk the entire 6-month roadmap.**

---

## What this assumption map tells you about risk

The roadmap has **2 fundamental bets** (V1, V2) and **3 execution risks** (F1, Vi2, V3-V4).

- The 2 fundamental bets are testable in 1 week of work each.
- If V2 (walk-forward) reveals that 3 of 4 strategies are overfit, the project doesn't fail — it pivots to "find ONE strategy that survives walk-forward, deploy that with real capital, ignore the rest." That's still a viable thesis, just narrower.
- If V1 (alpha after costs) fails, the project doesn't fail either — it lowers the target. Nifty + 6pp is still life-changing over 20 years.

**The only assumption with no graceful degradation is Vi2 (you keeping at it for 3+ years).** That's a personal commitment risk, not a product risk. Test it with milestones, not experiments.
