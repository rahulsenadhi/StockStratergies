# Brainstorm — Personal Algo Platform Features

**Date:** 2026-05-31
**Vision file:** `1-product-vision.md`
**Strategy canvas:** `2-strategy-canvas.md`
**Format:** PM + Designer + Engineer trio, 10+ ideas each.

Each idea tagged: **Vision-aligned** (Y/N), **Effort** (S=hours / M=days / L=weeks), **Impact** (low/med/high on North Star CAGR or trust-in-strategies).

---

## PM Perspective — Business/Strategic Value (12 ideas)

| # | Idea | Vision | Effort | Impact |
|---|---|---|---|---|
| PM1 | **Research-paper PDF ingester** — drag PDF → app extracts factor name, formula, universe, holding period; auto-creates strategy spec scaffold | Y | L | High |
| PM2 | **Strategy library page** — single grid view of all strategies with: name, CAGR, Sharpe, Max DD, years-live, confidence tier (Research / Paper / Live) | Y | M | High |
| PM3 | **Confidence-tier gating** — strategies must pass: lookahead-audit ✓ → 60-day paper-trade ✓ → 90-day paper-trade ≥ Nifty before "deploy" badge unlocks | Y | M | High |
| PM4 | **Monthly performance report (auto-generated)** — PDF/markdown sent to self with: each strategy's MoM/YoY return, regime context, any data-quality alerts | Y | M | Med |
| PM5 | **Strategy retirement triggers** — auto-flag when strategy underperforms benchmark for 6 months OR Sharpe drops >50% from baseline | Y | S | High |
| PM6 | **Backtest reproducibility seal** — every backtest output includes git SHA + data snapshot hash + lib versions; click "reproduce" = same numbers always | Y | M | High |
| PM7 | **Universe presets** — Nifty 50 / Nifty 200 / Nifty 500 / sector subsets / custom CSV — applied uniformly across all strategies | Y | S | Med |
| PM8 | **Per-strategy cost model** — slippage, broker fees, STT, GST factored in. Net CAGR vs gross CAGR displayed | Y | M | High |
| PM9 | **Annual strategy review template** — guided self-Q&A: "is this still working? what changed? keep / iterate / retire?" | Y | S | Med |
| PM10 | **Glossary linked to every term** — hover over "SUE" → 2-line plain definition; click → full explainer page | Y | S | Med |
| PM11 | **Source-of-truth ledger** — every signal logged: what fired, what I did, what happened. Reconciles "strategy says" vs "I traded" gap. | Y | M | High |
| PM12 | **Open-source release prep** — README, LICENSE, contribution guide, anonymized data fixtures for tests | Y | M | Low (now); High (year 2) |

---

## Designer Perspective — UX/Usability/Delight (12 ideas)

| # | Idea | Vision | Effort | Impact |
|---|---|---|---|---|
| DE1 | **Strategy comparison table** — side-by-side: equity curves, KPIs, Sharpe, drawdown, win rate. Pick any 2-4 strategies, see them stacked. | Y | M | High |
| DE2 | **Equity curve hover-tooltip** — hover any point → "On this date, you held X stocks worth ₹Y, this was a -3.2% drawdown day, trigger event = NIFTY -2%" | Y | M | Med |
| DE3 | **Single-stock detail page** — click ticker anywhere in dashboard → full context: which strategies hold/held it, all entry/exit dates, fundamentals snapshot, fwd 60d return | Y | M | High |
| DE4 | **Confidence-tier visual chips** — Research (🔬 gray) / Paper (📄 blue) / Live (🚀 green) on every strategy card. Color flips signal trust at a glance | Y | S | Med |
| DE5 | **Onboarding-style "first run" walkthrough** — for future open-source users: 5-step tour explaining what each tab does | N (deferred) | M | Low (year 2 onwards) |
| DE6 | **Dark/Light toggle** — already implemented per recent commit | Y | done | Med |
| DE7 | **Filter chips above every table** — Sector / Mcap / Period / Strategy / Year as click-toggle chips, not dropdowns | Y | S | Med |
| DE8 | **"What changed since yesterday" diff page** — new signals appeared, signals closed, strategies that flipped regime. One scroll catches up. | Y | M | High |
| DE9 | **Audit-trail flame chart** — visual time series of every lookahead check + data quality alert per strategy. Spot patterns of failures. | Y | M | Med |
| DE10 | **Glossary tooltip on every column header** | Y | S | Med |
| DE11 | **Print-friendly view for monthly review** — clean black-on-white tables + charts, hide chrome | Y | S | Med |
| DE12 | **Sound/desktop notification when paper-trade signal fires** — opt-in. "INFY new Live signal — 30s ago" while you're on dashboard | N | S | Low (over-engineering for solo use) |

---

## Engineer Perspective — Technical Possibility & Data Leverage (12 ideas)

| # | Idea | Vision | Effort | Impact |
|---|---|---|---|---|
| EN1 | **Formula DSL** — `sue > 2 AND piotroski >= 7 AND pb < sector_median` parsed via `pandas.eval` or `polars.sql`. Strategy = formula + universe + hold rule. | Y | L | High |
| EN2 | **Walk-forward validation harness** — sliding window backtest: train 2yr → test next 6mo → roll forward. Detect overfitting. | Y | M | High |
| EN3 | **Strategy decorator pattern** — `@strategy(name="PEAD", universe="nifty200", hold=60)` registers + auto-wires into dashboard | Y | M | High |
| EN4 | **Snapshot-based backtest** — every backtest run pinned to a git SHA + data hash. Re-run later → same answer (no silent yfinance drift) | Y | M | High |
| EN5 | **nselib + jugaad-data + screener.in fallback chain** — auto-picks best available source; logs which served each event | Y | M | High |
| EN6 | **Streaming-style daily refresh** — only re-download tickers whose results were announced; not 2,200-ticker full refresh nightly | Y | M | High |
| EN7 | **DuckDB / Polars upgrade** — replace pandas in hot paths (cohort decile loop, equity-curve mark-to-market). 10–50× speedup. | Y | M | Med |
| EN8 | **Test fixture generator from real data** — capture a "golden" snapshot of 10 tickers' fundamentals + prices, version-controlled. Tests use fixtures, never hit network. | Y | M | High |
| EN9 | **Strategy plugin folder** — drop a `.py` file in `strategies/`, dashboard auto-discovers and registers it | Y | M | High |
| EN10 | **Bayesian decile-spread significance test** — show "edge is real" vs "could be noise" with confidence interval. Sample-size aware. | Y | M | High |
| EN11 | **Cross-validation across sectors** — does strategy work in IT but not Energy? Per-sector CAGR + Sharpe breakdown auto-computed | Y | M | High |
| EN12 | **Regime-conditional metrics** — strategy CAGR split by bull / bear / sideways regimes. Tells you when each strategy fires best. | Y | M | High |
| EN13 | **Anomaly detector on event stream** — alert when SUE jumps >20% week-over-week (data error or real surprise?) | Y | S | Med |
| EN14 | **Local LLM call → spec generation** — pass paper text to local Llama or Claude API → structured Pydantic output → reviewed manually → committed as strategy | Y | L | High (enables PM1) |

---

## Total: **38 ideas** (12 PM + 12 Designer + 14 Engineer)

Trade-off filter applied: **0 ideas violate the strategy NO-list** (no AI black-boxes, no F&O, no real-time, no mobile, no broker auto-exec, no social).

---

## Top 5 Prioritized

Selection criteria: **Strategic alignment + Impact on North Star + Feasibility + Differentiation**.

### #1 — **EN1: Formula DSL** (`sue > 2 AND piotroski >= 7`)

**Why selected:**
- Direct vision lever — "sourced from research" requires a fast way to translate paper formulas to executable strategies
- Differentiation moat — Streak's DSL is templated; this one runs against your actual data with your audit layer
- Unlocks volume: 10× strategy throughput → more shots → more winners → higher portfolio CAGR

**Assumptions to validate:**
- H1: `pandas.eval` (or `polars.sql`) is expressive enough for 80% of factor strategies
- H2: User-self will actually use the DSL instead of dropping back to Python
- H3: Formulas can be safely sandboxed (no `os.system` injection)

---

### #2 — **PM2: Strategy Library Page** + **PM3: Confidence-Tier Gating**

(treat as one feature — library page without tiers is just a list)

**Why selected:**
- Defines what "personal library of audit-grade strategies" actually LOOKS like in UI — your vision becomes tangible
- Confidence tiers enforce discipline: no strategy reaches "Live 🚀" without passing audit + paper-trade gates
- Direct moat: 3 years of tier history = personalized track record nobody else has

**Assumptions to validate:**
- H1: 3-tier model (Research / Paper / Live) is enough — not too coarse, not too fine
- H2: User-self will respect gates rather than override (discipline test)
- H3: 60–90 day paper-trade window correlates with deploy success (vs. shorter / longer)

---

### #3 — **EN5: nselib + fallback chain** (already in active PRD)

**Why selected:**
- In-flight per `docs/superpowers/prds/2026-05-31-pead-nselib-migration.md` — already prioritized
- Foundation: every other strategy idea depends on data being correct
- Blocks PM3 (no confidence tier if data isn't trustworthy)

**Assumptions:** see PRD §7 open questions.

---

### #4 — **EN2: Walk-Forward Validation Harness**

**Why selected:**
- Closes the biggest credibility hole in current backtest — "is this strategy real or did I overfit to 2020-2024?"
- Mechanical implementation: sliding window loop wrapped around existing `pead_backtest.py` / `momentum_edge_backtest.py`
- Output (rolling out-of-sample Sharpe) tells you when to retire a strategy (paired with PM5)

**Assumptions:**
- H1: 2yr train + 6mo test windows produce statistically meaningful results for Indian universe
- H2: All 4 current strategies pass walk-forward; if not, ship that finding as data-driven decision

---

### #5 — **EN10: Bayesian Decile-Spread Significance Test**

**Why selected:**
- Cheapest credibility upgrade — adds ~50 LOC, no new infra
- Direct fix for E1 in PEAD pre-mortem ("PEAD might have no edge in Indian markets")
- Generalizes: every new factor strategy gets "is this signal real?" answer for free
- Pairs perfectly with PM3 confidence tiers (significance test feeds the tier)

**Assumptions:**
- H1: Bayesian bootstrap (or simple t-test) is enough — full Bayesian regression overkill
- H2: User trusts the output; doesn't override "no edge" with hope

---

## Honorable Mentions (next 5 to revisit Q3)

| # | Idea | Why deferred |
|---|---|---|
| EN6 | Streaming daily refresh | Performance is already OK with `core/yf_cache.py`; revisit when universe → 500+ |
| EN12 | Regime-conditional metrics | Insightful but mostly diagnostic; doesn't directly raise CAGR |
| EN3 | Strategy decorator pattern | Cleaner code but doesn't change user-visible behavior |
| DE1 | Strategy comparison table | High polish; depends on PM2 library shipping first |
| EN8 | Test fixture generator | Quality-of-life for solo dev; not user-visible |

---

## Killed Outright (off-strategy)

| # | Idea | Why killed |
|---|---|---|
| DE5 | Onboarding walkthrough | n=1 user; defer to OSS release Q4 2027 |
| DE12 | Sound notification | Over-engineering for solo desktop use |
| (none proposed) | AI black-box strategies | Off-vision (audit-grade requires white-box) |
| (none proposed) | Live broker auto-execute | Off-vision (liability + compliance) |
| (none proposed) | Mobile app | Off-vision (Streamlit desktop is enough) |

---

## What this brainstorm tells you about scope

You have **5 launch-blocking features** for the next 6 months:
1. Formula DSL → unlocks research-paper-to-strategy throughput
2. Strategy Library page + Confidence tiers → makes the vision visible
3. nselib data migration → makes data trustworthy
4. Walk-forward validation → makes claims rigorous
5. Bayesian significance test → makes "is this real?" answerable

That's a **focused roadmap**. Anything else can wait. The strategy canvas's NO list and this prioritization together create a clear "north" for the year.
