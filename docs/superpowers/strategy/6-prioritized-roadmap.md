# Prioritized Roadmap — Next 90 Days

**Date:** 2026-05-31
**Owner:** rahul.senadhi
**Source inputs:** `1-product-vision.md` · `2-strategy-canvas.md` · `3-brainstorm.md` · `4-ost.md` · `5-assumptions.md`

---

## Scoring Method

**RICE × Strategic-Fit (modified for n=1 user)**

```
Score = (Impact × Confidence × StrategicFit) / Effort
```

- **Reach** dropped (always 1 — single user)
- **Impact**: 1–10 on North Star (Nifty + 10pp CAGR)
- **Confidence**: 0.1–1.0 (how sure you are the feature delivers Impact)
- **StrategicFit**: 0 (off-vision), 0.5 (neutral), 1.0 (directly on-vision)
- **Effort**: 1–10 (1 = hours, 5 = week, 10 = month+)

Higher score = higher priority.

---

## Candidate Pool (from OST + Brainstorm)

| ID | Feature | Source | OST phase |
|---|---|---|---|
| C1 | nselib data migration | OST S3.1 / PRD | Phase A |
| C2 | Daily data-quality audit | OST S3.2 | Phase A |
| C3 | Bayesian decile-spread significance test | OST S2.2 / Brainstorm EN10 | Phase A |
| C4 | Walk-forward validation harness | OST S2.1 / Brainstorm EN2 | Phase B |
| C5 | Confidence-tier gating + paper-trade tracker | OST S5.1 / Brainstorm PM3 | Phase B |
| C6 | Strategy Library page | OST S4.1 / Brainstorm PM2 | Phase B |
| C7 | Cost-aware backtest (slippage + STT + brokerage) | OST S5.x / new from assumptions V1 | Phase A (added by assumption check) |
| C8 | Strategy plugin folder + decorator | OST S1.3 | Phase C |
| C9 | Formula DSL builder | OST S1.1 / Brainstorm EN1 | Phase C |
| C10 | 5-paper curated starter pack | OST S1.4 | Phase C |
| C11 | Paper PDF → spec extractor (LLM) | OST S1.2 / Brainstorm EN14 | Phase D |
| C12 | Sector-conditional metrics | OST S2.3 | Phase D |
| C13 | Regime-conditional metrics | OST S2.4 / Brainstorm EN12 | Phase D |
| C14 | Backtest reproducibility seal (git+data hash) | Brainstorm PM6 | Phase A-B |
| C15 | What-changed-since-yesterday diff page | Brainstorm DE8 | Phase B |
| C16 | Strategy comparison view | Brainstorm DE1 | Phase D |

---

## Scoring Table

| ID | Feature | Impact (1-10) | Conf (0-1) | Fit (0-1) | Effort (1-10) | Score | Rank |
|---|---|---|---|---|---|---|---|
| C1 | nselib data migration | 9 | 0.9 | 1.0 | 4 | **2.03** | 1 |
| C7 | Cost-aware backtest | 8 | 0.9 | 1.0 | 2 | **3.60** | (recalc — see below) |
| C3 | Bayesian significance test | 8 | 0.8 | 1.0 | 2 | **3.20** | (recalc — see below) |
| C4 | Walk-forward validation | 9 | 0.7 | 1.0 | 4 | **1.58** | 4 |
| C5 | Confidence tiers + paper-trade | 8 | 0.7 | 1.0 | 6 | **0.93** | 5 |
| C6 | Strategy Library page | 6 | 0.8 | 0.8 | 4 | **0.96** | 6 |
| C2 | Data-quality audit | 6 | 0.9 | 1.0 | 2 | **2.70** | 3 |
| C14 | Reproducibility seal | 5 | 0.7 | 1.0 | 3 | **1.17** | 7 |
| C8 | Strategy plugin folder | 5 | 0.8 | 0.8 | 4 | **0.80** | 8 |
| C9 | Formula DSL | 8 | 0.5 | 1.0 | 8 | **0.50** | 9 |
| C10 | Curated 5-paper pack | 6 | 0.7 | 1.0 | 4 | **1.05** | 10 |
| C11 | LLM PDF extractor | 7 | 0.3 | 1.0 | 8 | **0.26** | 11 |
| C12 | Sector metrics | 4 | 0.7 | 0.5 | 4 | **0.35** | 12 |
| C13 | Regime metrics | 5 | 0.7 | 0.5 | 4 | **0.44** | 13 |
| C15 | What-changed diff | 4 | 0.7 | 0.5 | 4 | **0.35** | 14 |
| C16 | Strategy comparison view | 5 | 0.7 | 0.5 | 4 | **0.44** | 15 |

After recalc (highest-scoring on top):

| Rank | Feature | Score | Effort | Why |
|---|---|---|---|---|
| **1** | C7 Cost-aware backtest | 3.60 | 2 (S) | Cheapest way to validate V1 (₹10pp alpha after costs) |
| **2** | C3 Bayesian significance | 3.20 | 2 (S) | Tells "edge real or noise?" for every strategy |
| **3** | C2 Daily data-quality audit | 2.70 | 2 (S) | Catches POWERGRID-class bugs before they corrupt signals |
| **4** | C1 nselib migration | 2.03 | 4 (M) | Foundation; in-flight PRD already |
| **5** | C4 Walk-forward validation | 1.58 | 4 (M) | Tells if Monthly Rotation alpha is real or regime-luck |

---

## TOP 5 for Next 90 Days

### 🥇 #1 — **C7: Cost-aware backtest** (Phase A)

**Score:** 3.60
**Effort:** 2 (one weekend, ~8h)
**Dependencies:** None — pure code change to existing backtest engines.

**What:** Add per-trade cost model to all 4 backtest engines:
- Brokerage: 0.03% buy + 0.03% sell (Zerodha-like)
- STT: 0.1% sell-side (delivery)
- GST: 18% on brokerage
- Slippage: 0.1% per side (large/mid caps) or 0.3% (small)
- Stamp duty: 0.015% on buy

Re-run all 4 strategies. Publish "Net CAGR" alongside gross.

**Why P1:**
- Resolves assumption V1 (highest-risk fundamental bet)
- Cheap (~8h)
- High signal: tells you if "Nifty + 10pp" is realistic or fantasy
- Forces re-baselining of North Star if alpha collapses (e.g., Monthly Rotation may drop from +12.7% to +9% net)

**Acceptance criteria:**
- All 4 strategy backtests show Gross CAGR + Net CAGR side-by-side
- Per-trade cost breakdown logged
- Updated dashboards show "after costs" by default
- North Star target revised if net-Monthly-Rotation alpha < 8pp

**Risks:**
- Slippage estimates may be too optimistic for small-caps → use 0.3% conservatively
- Different broker pricing → publish costs as configurable

---

### 🥈 #2 — **C3: Bayesian Significance Test** (Phase A)

**Score:** 3.20
**Effort:** 2 (~8h, ~50–100 LoC)
**Dependencies:** None.

**What:** Bootstrap significance test on decile-spread (D10 fwd-60d − D1 fwd-60d):
- N=1000 resamples with replacement
- 95% confidence interval on spread
- Display: "Edge: +2.3% (CI: 0.8% to 3.7%) — likely real" vs "Edge: +0.4% (CI: -1.2% to 2.0%) — noise"

Apply to all 4 strategies' decile diagnostic.

**Why P1:**
- Generalizes — every new strategy gets "is it real?" answer for free
- Pairs with C5 (confidence tiers feed off this)
- Resolves pre-mortem E1 ("PEAD might have no edge")
- Tiny LoC, huge credibility upgrade

**Acceptance criteria:**
- `pead_diagnostics.py` adds `bootstrap_decile_spread(events, n=1000)` returning `(spread, ci_low, ci_high)`
- Dashboard backtest tab shows the CI alongside decile chart
- Strategies with CI overlapping 0 flagged as "insufficient evidence"

**Risks:**
- N=1000 may be slow on large universes — fallback N=500 if >5s
- Bootstrap assumes IID; events clustered around earnings season aren't strictly IID → flag this caveat in glossary

---

### 🥉 #3 — **C2: Daily Data-Quality Audit Script** (Phase A)

**Score:** 2.70
**Effort:** 2 (~8h)
**Dependencies:** Best run after C1 (nselib in place) but can mock for now.

**What:** Script `pead_data_audit.py`:
- Compare 10 sentinel tickers' last-4-quarter EPS vs hand-verified `known_good_eps.json`
- Run after every daily refresh
- Alert if any diff >5%
- Append to `pead_data/audit_log.csv`

Dashboard footer shows: "Data audit: 10/10 passing • Last check 2026-05-31 01:23"

**Why P1:**
- Catches POWERGRID-class bugs within 1 day instead of weeks
- Foundation for trust in any future strategy
- Tests assumption F1 + Vi3 (free data sufficient) continuously
- ~50 LoC; runs in 5s

**Acceptance criteria:**
- Script exits 0 if all pass, 1 if any drift > 5%
- Wired into `refresh_data.bat` as step [5/5]
- Dashboard surfaces last-audit status
- Hand-verified fixture covers 10 Nifty 50 tickers, last 4 Qs each

**Risks:**
- Fixture goes stale as new quarters are filed → audit script auto-updates fixture only for fresh quarters NSE confirms (separate from accuracy check)
- 5% threshold too tight/loose → calibrate after first month

---

### #4 — **C1: nselib Data Migration** (Phase A)

**Score:** 2.03
**Effort:** 4 (~8h per PRD; ~16h with conservative buffer)
**Dependencies:** None. PRD already written.

**What:** Per `docs/superpowers/prds/2026-05-31-pead-nselib-migration.md`:
- New `core/nse_data.py` with cached nselib wrapper
- `core/fundamentals.py:get_quarterly_eps_history` becomes nselib-first
- `eps_source` column added to events.parquet
- Q/A toggle on PEAD dashboard

**Why P4 (not higher):**
- High Impact AND high Confidence AND on-vision
- But Effort 4 (more involved than C7/C3/C2 which are 2 each)
- Score formula keeps it at #4

**Acceptance criteria:** PRD §9 approval gates.

**Risks:** Pre-mortem doc covers — LB1, LB2, LB3 with mitigations.

---

### #5 — **C4: Walk-Forward Validation Harness** (Phase B)

**Score:** 1.58
**Effort:** 4 (~16h)
**Dependencies:** Conceptually independent but best after C1+C7 (clean data + realistic costs).

**What:** Sliding-window backtest:
- Train window: 2 years (rolling)
- Test window: 6 months (out-of-sample)
- Advance by 3 months, repeat across full data range
- Output: time series of OOS Sharpe, CAGR, Win Rate

Apply to all 4 strategies. Generate `walk_forward_<strategy>.csv` + chart per strategy.

**Why P5:**
- Highest-impact test of assumption V2 (overfit risk)
- More effort than top 4 — but if it kills Monthly Rotation's claimed alpha, that's a strategy-defining finding worth knowing in 2026 vs 2028

**Acceptance criteria:**
- Module `core/walk_forward.py` wraps existing backtest engines
- Each strategy reports: avg OOS Sharpe, OOS CAGR, sample size of windows
- Chart shows in-sample vs out-of-sample side-by-side
- Strategies where OOS Sharpe drops >50% from in-sample flagged "DEMOTE: regime-dependent"

**Risks:**
- Computationally heavy (multiple full backtests) — accept overnight run if needed
- Defining "fail" upfront prevents post-hoc rationalization — write the rule before seeing results

---

## Anti-Priorities (Explicit NOT-NOW)

These are good ideas that fail the strategic-fit + effort filter for 90 days:

| Feature | Why deferred |
|---|---|
| C9 Formula DSL builder | Effort 8, Confidence 0.5 (U1 unproven). Build curated 5-paper pack (C10) first; if you actually use it, then DSL has real demand. |
| C11 LLM PDF extractor | Effort 8, Confidence 0.3. Manual translation of 5 papers proves whether mechanical extraction is even possible (V3). Don't build LLM before manual baseline exists. |
| C6 Strategy Library page | UX polish — wait until you have 8+ strategies. Today you have 4; current dashboard is fine. |
| C8 Plugin folder | Engineer ergonomics — clean code but no user-visible CAGR impact. Refactor when adding strategy #6 or #7. |
| C12/C13 Sector + Regime metrics | Diagnostic, not generative. Build after walk-forward (C4) — that's where you'll WANT these to explain failures. |
| C15 What-changed diff page | UX polish. Build only if dashboard usage drops because you can't find new info. |
| C16 Strategy comparison view | Depends on C6. |
| Anything from the "killed outright" brainstorm list | Already off-vision. Don't reconsider for 12 months. |

---

## 90-Day Schedule

```
Week 1-2   ████  C7 Cost-aware backtest      [P1, 8h]
Week 1-2   ██    C3 Bayesian significance     [P2, 8h]   (in parallel)
Week 3-4   ████  C2 Data-quality audit        [P3, 8h]
Week 3-6   ████████████████  C1 nselib migration   [P4, 16h]
Week 7-10  ████████████████  C4 Walk-forward       [P5, 16h]
Week 11-12 BUFFER · documentation · STRATEGY_GUIDE.md updates · review
```

**Total: ~56h productive work spread over 12 weeks. Average 4.7h/week — well within Vi5's 10h/week sustainability budget.**

---

## Decision Gates

At end of Week 4 (after Phase A complete):
- Did C7 reveal "+10pp" is unrealistic? → revise North Star
- Did C3 reveal any strategy as noise? → demote in confidence tier
- Did C2 reveal recurring data quality issues? → consider paid feed budget

At end of Week 6 (after C1):
- Did POWERGRID test pass? → continue to Walk-Forward
- Did it fail? → escalate, possibly add Screener.in fallback chain

At end of Week 10 (after Walk-Forward):
- Do all 4 strategies survive OOS? → proceed to Phase B (paper-trade + tiers)
- Did 2+ fail? → STOP. Project pivot needed: focus on the 1-2 strategies that survived.

---

## What this prioritization tells you

The roadmap is intentionally **conservative**: 4 of top 5 are de-risking work (data, costs, significance, overfit). Only #5 onwards starts adding new strategy throughput.

**The lesson:** before building the formula DSL and the LLM PDF extractor (the "exciting" features), prove the foundation is real. If walk-forward kills Monthly Rotation, you don't need a faster way to author strategies — you need to find a strategy that holds up.

Build the boring, foundational, evidence-gathering work first. Glamour features later — and only on evidence-validated ground.

---

## Re-prioritize trigger

Re-run this prioritization when:
- Any decision gate fails (above)
- You complete top 5 (90 days from now)
- Vision changes meaningfully (re-read at month 3)
- A new opportunity emerges that scores higher than current #5
