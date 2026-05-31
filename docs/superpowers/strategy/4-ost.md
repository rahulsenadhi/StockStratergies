# Opportunity Solution Tree — Personal Algo Platform

**Date:** 2026-05-31
**Owner:** rahul.senadhi
**Outcome window:** 12–36 months

---

## Desired Outcome (North Star)

> **Sustain Nifty + 10pp annualized return across the live-deployed strategy portfolio, over rolling 3-year windows, net of fees.**

- Current state: Monthly Rotation +12.7% alpha (4-yr); IPO Edge -2pp alpha (2-yr); Momentum Edge +0.3pp alpha (10-yr); PEAD 4 trades (TBD).
- Portfolio-weighted alpha today: ~+5pp (one strategy carrying the rest).
- Gap to outcome: **need ≥5pp more alpha, sustained**.

---

## Opportunity Map (customer = self / DRQ persona)

5 opportunities ranked by **Opportunity Score = Importance × (1 − Satisfaction)**, 0–1 scale.

| # | Opportunity (from customer view) | Importance | Satisfaction | Score | Rank |
|---|---|---|---|---|---|
| O1 | "I struggle to translate a research paper into a runnable strategy in less than a week." | 0.9 | 0.1 | **0.81** | 🥇 |
| O2 | "I can't tell if my backtested edge is real or overfit." | 0.95 | 0.3 | **0.67** | 🥈 |
| O3 | "I don't trust my data — yfinance gives wrong Indian EPS; I re-verify on Screener." | 0.9 | 0.3 | **0.63** | 🥉 |
| O4 | "I can't see all my strategies at a glance — which is live, paper, retired, candidate?" | 0.7 | 0.2 | **0.56** | 4 |
| O5 | "I deploy strategies before they're truly ready, then lose money and abandon them." | 0.85 | 0.4 | **0.51** | 5 |

Focus the tree on **O1 + O2 + O3** (top 3). O4 and O5 are still in the tree but with fewer solutions.

---

## Tree Visualization (ASCII)

```
                    OUTCOME: Nifty + 10pp CAGR (3yr rolling)
                                     │
        ┌──────┬──────┬──────────┬───┴──────┬────────────┐
        │      │      │          │          │            │
       O1     O2     O3         O4         O5          (future opps)
   "paper  "real "trust       "library   "deploy
   to spec  vs    data         visible"   too early"
   <week"  noise"
        │      │      │          │          │
   ┌────┼────┐ │  ┌───┼───┐    ┌─┴─┐     ┌──┴──┐
  S1.1 S1.2 S1.3 S2.1 S2.2 S2.3 …  …     S5.1 S5.2
   │    │    │   │    │    │
   E    E    E   E    E    E
```

Detail per branch below.

---

## O1 — "Translate research paper to runnable strategy in <1 week"

### Solutions

**S1.1 — Formula DSL builder** *(top brainstorm pick EN1)*
- User types: `sue > 2 AND piotroski >= 7 AND pb < sector_median` → app generates strategy module → backtest runs
- Uses `pandas.eval` or `polars.sql` under the hood
- Effort: L (~2 weeks). Impact: High.

**S1.2 — Paper PDF → spec extractor**
- Drop PDF → LLM extracts (factor name, formula, universe, hold period) into Pydantic schema → manual review → committed as DSL strategy
- Uses Claude API or local Llama
- Effort: L (~3 weeks). Impact: High once S1.1 exists.

**S1.3 — Strategy plugin folder**
- Drop a `.py` file in `strategies/` → dashboard auto-discovers, registers, runs
- Decorator pattern: `@strategy(name="X", universe="nifty200", hold=60)`
- Effort: M (~1 week). Impact: Med — engineer-quality-of-life.

**S1.4 — Curated 5-paper starter pack**
- Pre-translate 5 famous Indian-market papers (PEAD, Quality + Momentum, Low Vol, Value Spread, Earnings Quality) into DSL strategies as templates
- Effort: M (~1 week + reading time). Impact: Med — seeds the library.

### Experiments

| Sol | Hypothesis | Test | Metric | Pass |
|---|---|---|---|---|
| S1.1 | DSL handles 80% of factor strategies you'd write | Translate top 5 brainstorm-pick strategies into DSL on paper. Count "expressible" vs "needs Python escape hatch". | % expressible | ≥4/5 |
| S1.2 | LLM extracts paper formula ≥80% correct | Feed 1 paper to Claude API with Pydantic schema. Manually grade output vs hand-extracted ground truth. | accuracy % | ≥80% |
| S1.3 | Plugin folder cuts strategy boilerplate >50% | Refactor 1 existing strategy to plugin pattern. Compare LoC. | LoC reduction | ≥40% |
| S1.4 | Starter pack gets used | After 30 days post-ship, count: # of starter strategies still in library | usage | ≥3/5 retained |

---

## O2 — "Tell real edge from overfit / noise"

### Solutions

**S2.1 — Walk-forward validation harness** *(top brainstorm pick EN2)*
- Sliding window: train 2-yr → test next 6mo → roll forward
- Output: rolling out-of-sample Sharpe time series
- Effort: M (~1 week). Impact: High.

**S2.2 — Bayesian decile-spread significance test** *(top brainstorm pick EN10)*
- Bootstrap N=1000 resamples → 95% CI on (decile_10 − decile_1) fwd return
- Display "Edge: +2.3% (CI: 0.8% to 3.7%) — likely real" or "Edge: +0.4% (CI: -1.2% to 2.0%) — noise"
- Effort: S (~2 days, ~50 LoC). Impact: High.

**S2.3 — Cross-validation by sector**
- Run strategy per-sector → which sectors carry the edge?
- If 1 sector accounts for all alpha → red flag (concentration risk)
- Effort: M (~1 week). Impact: Med.

**S2.4 — Regime-conditional metrics**
- Strategy CAGR split by Bull / Bear / Sideways (using SMA50/200 cross)
- Tells you when each strategy is supposed to fire
- Effort: M (~1 week). Impact: Med.

### Experiments

| Sol | Hypothesis | Test | Metric | Pass |
|---|---|---|---|---|
| S2.1 | Walk-forward exposes overfitting in at least 1 of 4 current strategies | Run on all 4. Compare in-sample vs OOS Sharpe. | Drop in Sharpe | If drop >50% on any, retire that strategy |
| S2.2 | 95% CI shrinks to "edge real" for Monthly Rotation but stays ambiguous for PEAD | Run on existing decile data | CI overlap with 0 | PEAD CI likely includes 0 (sample too small) |
| S2.3 | At least 1 strategy's edge is concentrated in 1-2 sectors | Per-sector CAGR breakdown | Sharpe stdev across sectors | If stdev > mean → concentration flag |
| S2.4 | Each strategy has a regime where it fires best | Tag every trade with regime → group by regime | Per-regime Sharpe | Lookup which strategy = which regime |

---

## O3 — "Trust the data (don't re-verify on Screener)"

### Solutions

**S3.1 — nselib + yfinance hybrid (IN-FLIGHT)** *(per PRD)*
- Already designed: nselib primary, yfinance fallback, `eps_source` tagged
- Effort: M (planned 8h per PRD). Impact: High.

**S3.2 — Daily data-quality audit script**
- After each refresh: diff 10 sentinel tickers vs hand-verified known_good_eps.json
- Alert if >5% drift on any
- Effort: S (~2 days). Impact: High.

**S3.3 — Source-tagged ledger in every event**
- Every event row: `eps_source ∈ {nselib | yfinance_fallback | none}`
- Dashboard footer: "Sources: 480 nselib / 41 fallback / 0 missing"
- Effort: S (rolled into S3.1). Impact: High (transparency).

**S3.4 — Snapshot pinning per backtest**
- Every backtest output saves the data hash + git SHA
- "Reproduce" button = same numbers always
- Effort: M (~1 week). Impact: Med.

### Experiments

| Sol | Hypothesis | Test | Metric | Pass |
|---|---|---|---|---|
| S3.1 | nselib gives POWERGRID 2026-Q4 EPS = ₹2.22 | Pip install + direct probe | EPS value | ≈ 2.22 ± 0.05 |
| S3.2 | Audit catches a data error within 1 week of it appearing | Inject synthetic bad EPS into cache → run audit | alert raised? | yes within 1 run |
| S3.4 | Two devs (or two runs) get identical backtest results | Run same `--start --end --flavor` on different days | byte-level diff | 0 bytes |

---

## O4 — "See all my strategies at a glance"

### Solutions

**S4.1 — Strategy Library page** *(top brainstorm pick PM2)*
- Single grid: name, CAGR, Sharpe, Max DD, # trades, years-live, confidence tier, last-touch date
- Sortable by any column
- Effort: M (~1 week). Impact: Med (UX, indirect on CAGR).

**S4.2 — "What changed since yesterday" diff page**
- New signals fired, signals closed, regime flips, strategies that crossed a threshold
- Effort: M. Impact: Med.

**S4.3 — Strategy comparison view**
- Pick 2-4 strategies → side-by-side equity curves + KPI table
- Effort: M. Impact: Med.

### Experiments

| Sol | Hypothesis | Test | Metric | Pass |
|---|---|---|---|---|
| S4.1 | Library page reduces "where's my strategy X?" friction | Self-time: navigate to KPI for any strategy. Before vs after. | seconds | <5s after vs ~30s today |

---

## O5 — "Deploy too early / abandon too quickly"

### Solutions

**S5.1 — Confidence-tier gating** *(top brainstorm pick PM3)*
- Lock "Deploy ✅" badge behind: lookahead audit ✓ + Bayesian significance ✓ + 60-day paper-trade ≥ Nifty
- Effort: M (~1 week + paper-trade infra). Impact: High.

**S5.2 — Strategy retirement triggers**
- Auto-flag when strategy underperforms benchmark 6+ months OR Sharpe drops >50% from baseline
- Effort: S. Impact: Med.

**S5.3 — Mandatory monthly review template**
- Self-Q&A: "is this still working? what changed? keep / iterate / retire?"
- Effort: S (markdown template). Impact: Med (discipline).

### Experiments

| Sol | Hypothesis | Test | Metric | Pass |
|---|---|---|---|---|
| S5.1 | Confidence gates correlate with deploy success | Look back at all past trades. Compute hypothetical "if gates existed, would I have deployed?" vs actual result. | Avoided losses if gates applied | If avoidance > 3pp gross |
| S5.2 | Retirement trigger fires on at least 1 current strategy | Apply trigger logic to last 3yr | # flagged | Likely IPO Edge under-alpha (2yr -2pp) |

---

## Prioritized Roadmap (next 6 months)

Reading the tree top-down, the path with highest **outcome leverage** in shortest time:

### Phase A (Now → +6 weeks) — Foundation
1. **S3.1** nselib migration (in-flight, PRD ready)
2. **S3.2** Daily data-quality audit
3. **S2.2** Bayesian significance test (cheap, high leverage)

### Phase B (+6 to +12 weeks) — Rigor
4. **S2.1** Walk-forward validation
5. **S5.1** Confidence-tier gating + paper-trade tracker
6. **S4.1** Strategy Library page

### Phase C (+12 to +24 weeks) — Throughput
7. **S1.3** Strategy plugin folder
8. **S1.1** Formula DSL builder
9. **S1.4** 5-paper starter pack

### Phase D (+24 weeks onwards) — Discovery throughput
10. **S1.2** Paper PDF → spec extractor (LLM)
11. **S2.3 / S2.4** Sector + regime cuts

### Deferred
- S4.2, S4.3 (UX polish)
- S5.2, S5.3 (discipline tooling — soft gates first)

---

## Open Questions for next discovery cycle

1. Does Monthly Rotation hold its +12pp alpha through walk-forward, or was 2022–2026 a lucky regime?
2. Does PEAD have any edge in Indian markets once data is right? (Per pre-mortem E1)
3. Will the LLM PDF extractor (S1.2) actually capture 80%+ of paper variants, or is manual coding still faster?
4. Does formula DSL adoption stick, or do you keep escape-hatching to Python? (S1.1)

These questions feed back into the OST quarterly. Discovery is continuous.

---

## How to read this tree in 6 weeks

When Phase A is done, re-run this exercise:
- Did O3 (data trust) get solved? → strike it from the tree
- Did O2 (real vs overfit) move? → maybe upgrade to confidence-interval-based deploy gates
- New opportunities surfaced from using Phase A? → add to tree

**Tree is alive. Update monthly.**
