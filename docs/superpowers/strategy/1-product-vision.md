# Product Vision — Personal Algo Stock Platform

**Date:** 2026-05-31
**Owner:** rahul.senadhi
**Stage:** First draft

---

## Core Problem

Indian retail traders are stuck between three bad options:
1. **Tip-based services** (Telegram, broker recommendations) — random hits, no edge, no audit trail
2. **Pre-built platforms** (Smallcase, Streak, Quantsbin) — locked into vendor-curated strategies, no research-paper ingestion, formula builders are templates not real DSLs
3. **Roll-your-own** (Python notebooks) — most never finish, no UI, no paper trade, no honest performance log

Meanwhile, world-class algo desks ingest 100+ research papers/yr, prototype 10+ strategies/mo, backtest with audit-grade rigor, ship the 1 that survives. Retail can never match the throughput — but **one disciplined person can match the rigor**.

---

## Ideal Future State

A single trader sits at the dashboard:
- Pastes a research paper PDF → app reads it, suggests a backtestable strategy spec
- Types: "buy stocks where SUE > 2 AND Piotroski >= 7" — app generates code, backfills universe, runs backtest, shows decile-spread within 60 seconds
- Sees 6 strategies running in paper-trade with audit-grade logs
- Confidently deploys real capital on the 2 that consistently beat Nifty over 3+ years
- Each month spends 30 minutes reviewing, 0 minutes guessing

The dashboard is their entire alpha-generation system.

---

## 5 Vision Statements

### Option A — *"Personal Quant Desk"*
> **"My one-person quant desk — research-paper to live trade in under a week."**

- Inspiring: positions trader as small-shop quant, not retail punter
- Achievable: matches existing 4-strategy + PEAD pipeline ambition
- Emotional: dignity of being a builder, not a follower

### Option B — *"Edge Compounder"*
> **"Compound a personal library of statistically-proven edges, one strategy at a time."**

- Inspiring: long-game framing, library grows over years
- Achievable: 1 new strategy/quarter is realistic
- Emotional: pride of ownership, anti-tip-culture

### Option C — *"Honest Alpha"*
> **"Backtest before belief. Paper-trade before capital. Deploy only what survives both."**

- Inspiring: discipline-first manifesto
- Achievable: literally the existing workflow, just named
- Emotional: hits hardest for traders burned by past losses

### Option D — *"Library of Edges"* ⭐
> **"Build a personal library of audit-grade trading strategies — sourced from research, validated by backtest, deployed with confidence."**

- Inspiring: positions user as researcher + practitioner
- Achievable: explicit on three steps (source, validate, deploy)
- Emotional: turns trading from gambling into craft

### Option E — *"Citizen Quant"*
> **"A retail trader with the rigor of a hedge fund — minus the cost, minus the gatekeepers."**

- Inspiring: democratization angle (good for open-source)
- Achievable: positions tooling against big-firm advantage
- Emotional: anti-establishment, agency

---

## Recommendation: **Option D — "Library of Edges"**

> **"Build a personal library of audit-grade trading strategies — sourced from research, validated by backtest, deployed with confidence."**

### Why this wins

**Inspiring** — "Library of Edges" is concrete and aspirational. You can picture 20 strategies in a list, each labeled with CAGR/Sharpe/years-live. That mental image drives daily work.

**Achievable** — Three verbs (source / validate / deploy) match the actual stages already in your codebase:
- *Source* = research-paper ingestion + formula builder (to build)
- *Validate* = existing backtest + decile-spread + audit (already 80% there)
- *Deploy* = paper-trade tracker + real-broker hook (future scope)

**Emotional** — "audit-grade" + "confidence" target the trader's deepest fear: trading on hunches and losing. The vision sells *discipline*, not *promises of riches*. That's why it survives the inevitable losing month.

### How it shapes feature priorities

| Vision phrase | Direct feature implication |
|---|---|
| "library" | Strategies must be browsable, comparable, persistent — not one-off scripts |
| "audit-grade" | Every backtest has lookahead audit, sample-size warnings, source-tagged data |
| "sourced from research" | Paper PDF parser + formula DSL are top-priority new features |
| "validated by backtest" | Tighten existing backtest engine (cross-validation, walk-forward) |
| "deployed with confidence" | Paper-trading tracker is a deploy-gate, not a nice-to-have |

### Memorability test

Can you say it in 1 breath? **"Library of audit-grade edges — research → backtest → deploy."** ✅

Can your future self in a losing month re-read this and remember why you're doing it? ✅

Does it inform a "no" to off-vision feature requests? ✅
- "Should I add a social leaderboard?" → off-vision (not about audit-grade edges)
- "Should I add walk-forward validation?" → on-vision
- "Should I add a tip-feed?" → hard no

---

## Alignment Check

| Stakeholder lens | Reaction |
|---|---|
| **You (creator/user)** | Motivating — turns daily grind into library-building craft |
| **A future open-source forker** | Clear value prop — joins because they want the same rigor |
| **A skeptical friend** | Believable — three concrete steps, not "AI for trading" hype |
| **An algo-trading mentor** | Approves — matches how real quant desks talk about their playbooks |

---

## Vision lifecycle

This is **rev 1**. Re-read every 6 months. Update when:
- You've deployed 3+ strategies live and the focus shifts (next vision: "scale + optimize")
- You decide to commercialize (next vision: customer-facing)
- A losing year forces a rethink (next vision: "anti-fragile portfolio")

For now, the next 12 months are **building the library**.
