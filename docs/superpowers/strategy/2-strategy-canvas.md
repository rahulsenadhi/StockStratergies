# Product Strategy Canvas — Personal Algo Stock Platform

**Date:** 2026-05-31
**Owner:** rahul.senadhi
**Stage:** Rev 1
**Vision file:** `1-product-vision.md`

---

## 1. Vision

> **"Build a personal library of audit-grade trading strategies — sourced from research, validated by backtest, deployed with confidence."**

Aspiration: match world-class quant rigor as a single retail trader. Values: discipline, evidence, transparency, anti-tip-culture.

---

## 2. Market Segments

### Primary segment: **The Disciplined Retail Quant (DRQ)**

| Dimension | Detail |
|---|---|
| **JTBD** | "Find Indian-market strategies that survive rigorous backtest, and trade them with confidence — not hunches." |
| **Desired outcomes** | Beat Nifty by 5–15% CAGR over 5 years; sleep at night; not chase tips |
| **Constraints** | Solo, ₹5–50 lakh portfolio, evenings/weekends only, no Bloomberg, no team |
| **Who** | Indian retail trader with 3+ yrs market experience, can code in Python OR is willing to learn, burned by past tip-followers' losses |
| **First user** | Self (rahul.senadhi) |
| **Why this segment first** | Single user = fastest iteration; rigor-first DNA happens to be open-source-friendly later; product is built FOR this person, BY this person |

### Secondary segment: **Open-Source Forker (deferred)**

| Dimension | Detail |
|---|---|
| **JTBD** | "Clone a battle-tested Indian quant repo so I don't reinvent backtest infra; modify for my own strategies." |
| **Outcome** | Skip 6 months of plumbing |
| **Why later** | Don't optimize for community until self-use is rock-solid; community needs docs, tests, license clarity that distract from #1 |

### Explicitly NOT a segment

- **Hedge funds / prop desks** — wrong scale, wrong asset classes, wrong UI
- **Tip-followers / Telegram channel users** — opposite philosophy; would actively reject "discipline-first"
- **HFT / intraday scalpers** — different infra (microsecond latency, co-location); explicit non-goal
- **F&O / options-only traders** — derivative complexity belongs in v3+

---

## 3. Relative Costs

**Position: Unique value, NOT low cost.**

- Smallcase / Streak / Quantsbin compete on price (₹0–₹500/mo). Subscription product, broad audience.
- **You compete on rigor and customization.** Your "price" = your own time. The DRQ values audit-grade trust over zero monthly fee, so unique value wins.
- Hardware/data costs are minimal (~₹0–500/mo: free nselib/yfinance, ₹0 hosting on localhost). Cost position is naturally low — but that's a side effect of being personal, not the strategy.

**Comparison:**

| Vendor | Cost position | Their bet | Why you're different |
|---|---|---|---|
| Smallcase | Premium curated | Trust the SEBI-registered advisor | You don't trust anyone, you trust audited backtests |
| Streak | Freemium DSL | Easy no-code strategies | You want full Python + research papers, not templated rules |
| Quantsbin | Free DIY | Power user friendly | Same audience, less batteries-included; you bundle dashboard + audit + paper-trade |
| Tijori | Premium data | Institutional users pay for clean data | Your data is "good enough" via nselib + yfinance + manual audits |

---

## 4. Value Proposition (per segment)

### DRQ (primary)

**Before** *(current pain)*:
- Has 10 saved research papers, 5 Python notebooks, 0 deployed strategies
- Backtests give different results each run — no audit trail
- Manually verifies EPS on Screener after every signal (no trust in tools)
- Worst: trades a strategy in real money before paper-trading it, loses 8%, abandons

**How** *(what you deliver)*:
- One dashboard with 4+ working strategies, each with backtest equity curve + audit log
- Paste research paper → app suggests strategy spec → backtest in <60s
- Formula DSL: "buy when SUE > 2 AND Piotroski >= 7" → executable code generated
- Built-in paper-trade tracker — strategy must survive 30+ days paper before "deploy" badge
- Lookahead audit, walk-forward validation, source-tagged data — no silent corruption

**After** *(future state)*:
- Library of 10–20 strategies with confidence-tiered: Tier 1 (live capital), Tier 2 (paper), Tier 3 (research)
- Spend 30 min/month reviewing the library, not building from scratch each weekend
- 5-year CAGR target: Nifty + 10pp (Nifty ~10%, target 20%+)
- Mental: traded with conviction. Lost months happen but no panic, no abandonment

**Alternatives today** *(what users do without you)*:
- Pay Smallcase ₹500/mo, accept their curation
- Cobble Python notebooks together (most never finish)
- Subscribe to a Telegram tip channel (worst option, but easiest)
- Trust gut feel / news / friends

---

## 5. Trade-offs (Explicit NO list)

| Won't do | Why |
|---|---|
| **Multi-user SaaS with subscriptions** | Adds compliance burden (SEBI advisory rules), customer support, billing. Off-vision. |
| **Live broker integration (Zerodha Kite, etc.) in v1** | Trust requires manual deploy through user's broker for now. Auto-execution = liability. |
| **Real-time / intraday strategies** | Different infra class (sub-second feed, co-location). Daily EOD is the sweet spot. |
| **Options / F&O strategies** | Higher dim (Greeks, expiry), wrong tooling. Cash equity first. |
| **Crypto / forex / commodity** | NSE focus reinforces audit-grade pitch. Multi-asset dilutes. |
| **Social leaderboard / copy-trading** | Off-vision (anti-tip-culture). Plus encourages performance-chasing. |
| **Machine learning "AI strategies"** | Black-box defeats "audit-grade." White-box features (formulas, factor exposures) only. |
| **Mobile app** | Streamlit on desktop is fine. Mobile = scope-creep. |
| **News sentiment / NLP scoring** | Indian-news quality is poor. Adds noise, not edge. Reconsider in v3+ if research paper warrants. |
| **Charts beyond Streamlit's built-in** | Don't build a TradingView clone. Use TradingView for charts, this app for strategy logic. |

Saying "no" to these creates focus on the 3 core capabilities: **strategy library + audit + paper-trade**.

---

## 6. Key Metrics

### North Star Metric (single number that proves you're winning)

> **Annualized CAGR of the live-deployed strategy portfolio, net of fees, over rolling 3-year windows.**

- Target: **Nifty + 10pp** (Nifty ~10%, you ~20%)
- Why this beats "# of strategies": you can have 50 strategies and still lose money. CAGR forces signal-not-noise.
- Why 3-year rolling: smooths out lucky quarters; aligns with how real quant desks evaluate.

### Supporting metrics (input/leading indicators)

| Metric | Target | Cadence |
|---|---|---|
| # of paper-trade strategies (live ≥30 days) | 8 by 2026-12 | Monthly |
| # of "deployed" strategies (real capital, ≥90 days live) | 3 by 2026-12 | Monthly |
| Avg Sharpe across deployed strategies | ≥1.0 | Quarterly |
| Backtest-to-deploy ratio (validates ≥1/4 makes it through) | 25–50% | Quarterly |
| Data-quality alerts (LOOKAHEAD, MISSING, STALE) per month | < 5 | Weekly |
| Hours/week on dashboard | 2-5h | Weekly self-report |

### OMTM (this quarter — Q2 2026)

> **Ship nselib migration + Q/A toggle + first paper-trade tracker by 2026-07-31.**

One metric: **# of strategies in paper-trade with full audit log** — target = 5 (currently 0 — only backtest exists, no paper-trade infra).

---

## 7. Growth

**Mode: Product-Led, Self-Use first → Eventual Open-Source community**

| Phase | Audience | Channel | Mechanic |
|---|---|---|---|
| **Now (2026)** | n=1 (self) | n/a — you are user | Daily use compounds quality |
| **2027** | 10-50 forkers | GitHub release + 1 Reddit/r/IndiaInvestments post | "Here's my Indian quant repo — 4 strategies, audit-graded, free" |
| **2028+** | 500–5k forkers | Quant blog (1 post/quarter), Twitter | Each new strategy = new blog post = new fork |

**Unit economics: irrelevant for personal use.** When/if open-sourced, the "cost" is documentation + issue triage time. **Revenue stays at zero**. The "return" is portfolio CAGR — that's the only payout.

If commercialization ever happens (v3+): paid tier might add cloud-hosted version with broker auto-deploy. But ONLY after a 3-year track record. Not a 2026/2027 concern.

---

## 8. Capabilities (what you need)

| Capability | Have today | Build / acquire | Priority |
|---|---|---|---|
| Python + pandas + Streamlit fluency | ✅ | — | Have |
| Indian market knowledge | ✅ | — | Have |
| Backtest engine | ✅ (4 strategies running) | Polish: walk-forward, cross-validation | P1 |
| Lookahead audit | ✅ (basic) | Extend to every new strategy | P0 |
| Data pipeline (NSE + yfinance + nselib) | ⚠️ (yfinance broken for India Q EPS — in flight per PRD) | Finish nselib migration | P0 |
| Research-paper PDF parser | ❌ | LLM + structured-output (Claude API + Pydantic schema) | P1 next quarter |
| Formula DSL ("SUE > 2 AND Piotroski >= 7") | ❌ | Build mini-parser (or use `polars.sql`/pandas `query`) | P1 next quarter |
| Paper-trade tracker | ❌ | New module: positions.parquet + daily mark-to-market | P0 this quarter |
| Walk-forward validation | ❌ | Existing backtest engine + sliding window loop | P1 |
| Open-source ops (issues, releases, docs) | ❌ | Defer to 2027 | P3 |

**Build vs partner:**
- **Build:** strategy library, backtest engine, audit layer, paper-trade tracker, dashboard — all core IP
- **Partner / use OSS:** yfinance, nselib, Streamlit, pandas, plotly — don't reinvent
- **Pay for if needed:** Tijori or Sensibull data API ONLY if nselib breaks repeatedly (per pre-mortem T1)

---

## 9. Can't / Won't (Defensibility)

| Moat | Strength | Why it holds |
|---|---|---|
| **Audit-trail compounding** | High | Every strategy run logged. After 3 years you have 1000+ logged backtests + 50+ paper-trades + 5+ live deploys. Nobody else has YOUR data history. |
| **Personal-fit calibration** | High | Strategies tuned to YOUR risk tolerance, capital size, sector preferences. Vendor products are one-size-fits-all. |
| **Research → strategy translation** | Med (defensible after build) | The PDF parser + formula DSL pipeline takes 6+ months to build right. Forkers benefit but late entrants pay full cost. |
| **No regulatory exposure** | Med | Personal use. Smallcase et al must comply with SEBI advisory rules — slower iteration. You iterate freely. |
| **Cost moat (₹0 / month)** | Low | Anyone can spin up Streamlit; not a moat |
| **Network effects** | None | n=1 user. Becomes a moat at 1000+ forkers. |

**Bottom line:** moat is the personal audit history + research → strategy pipeline. Both compound over years. The product 3 years from now has 3 years of clean data that nobody else has.

---

## Coherence Check (do the 9 sections reinforce?)

| Element | Reinforces |
|---|---|
| Vision = "audit-grade edges" | Drives section 4 (value prop = audit + paper-trade), section 5 (no AI/ML black box), section 8 (lookahead audit P0), section 9 (audit history = moat) |
| Segment = DRQ | Drives section 4 (their specific JTBD), section 5 (no tip-followers, no social), section 7 (open-source as growth — DRQs love OSS) |
| Cost = unique value not low | Drives section 5 (no SaaS pricing), section 9 (no cost moat) |
| Trade-offs = no AI / no F&O / no mobile | Reinforces capability scope (section 8) — keeps team-of-one shippable |
| North Star = CAGR | Drives ALL feature prioritization — does this feature directly raise NSM? |

**Test:** "Should I add a Discord bot?" → fails coherence: doesn't raise CAGR, off-vision (anti-social-trading), uses scarce solo time. ✅ easy NO.

**Test:** "Should I add walk-forward validation?" → passes coherence: raises Sharpe → raises CAGR confidence → raises deploy rate. ✅ easy YES.

---

## Critical Hypotheses (what must be true)

| # | Hypothesis | Why it matters | How to validate |
|---|---|---|---|
| H1 | Indian retail can outperform Nifty by 10pp via rigorous backtest + paper-trade | If false, strategy itself is dead | Already proven for Monthly Rotation (+12.7% alpha over 4yr). Confirm holds over next 12 months. |
| H2 | A single person can maintain 5+ live strategies without burning out | If false, scope down to 2-3 | Track hours/week — alert if >10h sustained |
| H3 | nselib + yfinance data is "good enough" — paid API not required | If false, ₹10k+/yr cost | Pre-mortem audit gate (POWERGRID 2.22 test) |
| H4 | Research papers can be auto-translated to strategy spec | If false, manual coding only — slower but not fatal | 5-paper spike Q3 2026 |
| H5 | Formula DSL adoption — once built, you'll actually use it | If false, you'll keep coding Python directly | Track # of DSL strategies created vs Python strategies in first 90 days post-launch |

---

## Validation Experiments (low-effort)

| Hypothesis | Experiment | Effort | Pass criteria |
|---|---|---|---|
| H1 (10pp alpha achievable) | Continue running 4 existing strategies as-is for 12 months; track aggregated CAGR vs Nifty | 0h (passive) | Combined alpha ≥ 5pp at month 12 |
| H3 (free data sufficient) | nselib migration POWERGRID audit (per PRD) | 2h | POWERGRID 2026-Q4 EPS = 2.22 ✅ |
| H4 (PDF → strategy spec) | Pick 1 paper (e.g. "PEAD in Indian Markets" from IIM Bangalore). Manually translate to spec. Then prompt Claude API with paper + see if spec matches. | 3h | Claude output captures ≥80% of manual spec |
| H5 (DSL adoption) | Mock formula UI on paper. Show to yourself in 1 week. Would you use it? | 30min | Honest self-rating ≥7/10 |

---

## What this strategy says NO to (summary)

- ❌ Multi-user SaaS, billing, customer support
- ❌ Live broker auto-execute
- ❌ Real-time / HFT / intraday
- ❌ F&O / options / crypto
- ❌ Social / copy-trading / leaderboards
- ❌ Black-box ML "AI strategies"
- ❌ Mobile app
- ❌ News-sentiment NLP scoring
- ❌ Custom charting (use TradingView)

## What this strategy says YES to (summary)

- ✅ Personal library of strategies, browsable + comparable
- ✅ Research-paper PDF → strategy spec pipeline
- ✅ Formula DSL builder (white-box, auditable)
- ✅ Backtest with lookahead audit + walk-forward
- ✅ Paper-trade tracker as deploy-gate
- ✅ NSE + yfinance + nselib hybrid data layer
- ✅ Open-source release path (2027+, optional)
- ✅ Self-use first; never optimize for users you don't have

---

**Next:** read `3-brainstorm-features.md` for the multi-perspective idea list this strategy filters.
