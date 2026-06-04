# Product Requirements Document: NSE Strategy Hub → Wealth Platform v2

**Author:** rahulsenadhi
**Date:** 2026-06-04
**Status:** Draft
**Stakeholders:** Single user (personal product)

---

## 1. Executive Summary

Upgrade the existing local Streamlit "NSE Strategy Hub" (4 systematic strategies + backtests) into a private, modern, always-fresh personal wealth platform. It adds portfolio tracking, goal-based wealth planning with "reach-faster" suggestions, and a self-serve strategy factory with a ranked leaderboard — served through a modern web UI, backed by a fast columnar data layer, and refreshed automatically at near-zero cost.

## 2. Background & Context

The current system (documented in the architecture map, 2026-06-04) is a Python/Streamlit app running locally. It has:
- A strategy engine (`generic_backtest.py`) with a JSON-spec + formula DSL, plus 4 hardcoded strategies (Monthly Rotation, IPO Edge, Momentum Edge, PEAD).
- A precompute pattern (`precompute_*.py`) that moves slow scans off the page-load path.
- A `core/` library (indicators, regime, sue, piotroski, analytics, exit_analyzer, etc.) and a Windows-Task-Scheduler refresh (`refresh_data.bat`).

**Pain points prompting v2:**
1. **Slow local load** — `load_ipo()` scans `ipo_data/` live on every page; `load_momentum()` falls back to a ~52s live compute when `precompute_momentum_signals.py` hasn't run. 450+ per-ticker CSVs are read repeatedly.
2. **No portfolio/holdings state** — the system only backtests; it cannot track what the user actually owns or the returns received.
3. **No goal planner** — no target-corpus tracking or guidance toward a wealth goal.
4. **Strategy onboarding is manual** — adding/ranking strategies isn't a smooth, success-rate-driven loop.
5. **Local-only** — must run on the user's PC; not accessible elsewhere, refresh is manual/scheduled-local.
6. **Dated UX** — custom-CSS Streamlit; user wants best-in-class modern UI/UX.

**Decisions already made (this session):**
- **Frontend:** Next.js + TypeScript + Tailwind + shadcn/ui (charts via TradingView lightweight-charts / Recharts / ECharts).
- **Hosting:** All-Cloudflare (Pages + Workers + R2 + D1) + GitHub Actions for Python compute. Chosen because nothing deactivates on inactivity (the Supabase free-tier 7-day pause was explicitly rejected), it is private via Cloudflare Access, and stays within free tiers.
- **Compute stays Python** (correct for quant): Polars + DuckDB + Parquet, Pydantic v2 schemas.

## 3. Objectives & Success Metrics

**Goals:**
1. Dashboard page loads read precomputed data only — no heavy compute on the request path.
2. Data refreshes automatically daily after NSE close, with zero manual steps.
3. Track real holdings and compute accurate returns (XIRR/CAGR, realized + unrealized).
4. Set a wealth goal and see the gap + concrete "reach-faster" levers.
5. Add a strategy → it is auto-backtested and appears on a ranked leaderboard.
6. Private and secure — only the user can access; no financial data exposed publicly.
7. Runs at ~₹0/$0 within free tiers.

**Non-Goals:**
1. **No live brokerage execution / order placement** — advisory only (avoids regulatory + security burden).
2. **No multi-user / SaaS** — single private user; no public sign-up, billing, or tenanting.
3. **No intraday/real-time tick data** — daily EOD cadence only.
4. **No big-bang rewrite** — Streamlit keeps running until the Next.js UI reaches parity (strangler-fig).
5. **No new asset classes** in v2 (NSE/BSE equities only; crypto/MF/US out of scope).

**Success Metrics:**

| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| Dashboard initial load (cold) | up to ~52s (momentum fallback) | < 2s | Browser timing on the slowest page |
| Data freshness lag after NSE close | manual / variable | < 12h automatic | Timestamp of latest published dataset |
| Manual steps per refresh | several (run scripts, precompute) | 0 | Count of human actions |
| Holdings tracked with accurate XIRR | 0 (no feature) | 100% of entered positions | Reconcile vs manual calc on sample |
| Strategies on ranked leaderboard | 4 (no live ranking) | all strategies auto-ranked | Leaderboard renders KPIs + rank |
| Recurring infra cost | local electricity | $0 within free tiers | Monthly provider bills |
| Private-access enforcement | n/a (local) | only user can load app | Cloudflare Access logs |

## 4. Target Users & Segments

Single user: the author — a retail systematic investor managing personal NSE/BSE equity investments, technically capable (runs Python, reads code), wants a private tool to compound wealth via backtested strategies and disciplined tracking. No other segments.

## 5. User Stories & Requirements

**P0 — Must Have:**

| # | User Story | Acceptance Criteria |
|---|-----------|-------------------|
| 1 | As the user, I want price/strategy data refreshed automatically so I never run scripts manually. | Scheduled GitHub Action runs the full download→backtest→precompute pipeline daily after NSE close; on success publishes datasets to R2; failure notifies (email/issue). |
| 2 | As the user, I want fast page loads so the app is pleasant. | All views read precomputed Parquet/JSON + D1; no full-universe scan on the request path; slowest page < 2s cold. |
| 3 | As the user, I want a columnar data layer so queries are fast and storage is compact. | Per-ticker CSVs converted to partitioned Parquet; reads via DuckDB; documented conversion + query path; load benchmark vs CSV recorded. |
| 4 | As the user, I want the app private and secure. | Cloudflare Access gates all surfaces to the user's identity; no secrets in the repo; private repo; brokerage/API keys only in CI/Workers secrets. |
| 5 | As the user, I want to record buys/sells and see returns. | Ledger captures ticker, date, qty, price, fees, dividends; computes per-holding + portfolio realized/unrealized PnL, XIRR, CAGR; persisted in D1/Turso. |
| 6 | As the user, I want to add a strategy and have it auto-backtested and ranked. | Submitting a strategy spec triggers a backtest (batch); KPIs (CAGR, Sharpe, maxDD, win%, vs-Nifty) computed; strategy appears on a sortable leaderboard with a rank score. |
| 7 | As the user, I want a modern web UI. | Next.js + shadcn/ui app renders home, strategies/leaderboard, a strategy detail (equity curve + trades + exit playbook), portfolio, and goal pages with responsive, modern components. |

**P1 — Should Have:**

| # | User Story | Acceptance Criteria |
|---|-----------|-------------------|
| 8 | As the user, I want a wealth goal with gap analysis. | Set target corpus + date; app shows current corpus, required CAGR to hit target, projected trajectory, and the gap. |
| 9 | As the user, I want "reach-faster" suggestions. | Given the goal gap, app suggests levers: increase monthly contribution by X, shift allocation toward top-ranked strategies, or extend horizon; each with quantified impact. |
| 10 | As the user, I want dividends/returns received tracked. | Dividend/return entries recorded and included in XIRR; income vs capital gain split shown. |
| 11 | As the user, I want the existing 4 strategies on the same leaderboard as custom ones. | Hardcoded strategies emit standardized KPIs and rank alongside generic-engine strategies. |
| 12 | As the user, I want strategy success-rate detail. | Per-strategy: win rate, expectancy, hold-period & exit-ladder (reuse `core.exit_analyzer`), regime-conditioned performance. |

**P2 — Nice to Have / Future:**

| # | User Story | Acceptance Criteria |
|---|-----------|-------------------|
| 13 | As the user, I want on-demand backtest runs from the UI (not just nightly). | UI triggers a backtest job on a persistent worker (Fly.io/Oracle VM); result streamed back. |
| 14 | As the user, I want Monte-Carlo wealth projections. | Goal planner shows probability cones from historical/forward return distributions. |
| 15 | As the user, I want alerts. | Email/push when a tracked signal fires or a holding hits an exit-ladder target. |
| 16 | As the user, I want broker-statement import. | Parse a broker contract-note/holdings CSV into the ledger. |

## 6. Solution Overview

**Architecture (three decoupled tiers):**

1. **Refresh/compute tier (batch, Python):** GitHub Actions cron (post-NSE-close). Runs the existing downloaders + backtests + precompute, now writing **partitioned Parquet** + a **DuckDB** file + result **JSON**. Publishes to **Cloudflare R2**. Heavy Python never touches the request path.
2. **Data tier:** **R2** holds price/strategy datasets (Parquet/DuckDB/JSON). **D1** (or Turso) holds mutable app state — ledger, goals, strategy registry. Polars/DuckDB used in the compute tier; Workers query R2/D1 on read.
3. **Serving tier:** **Next.js + shadcn/ui** on **Cloudflare Pages**; **Workers** API reads R2 + D1 → typed JSON (Pydantic-equivalent schemas validated at the boundary). **Cloudflare Access** fronts everything for private auth.

**Migration strategy — strangler-fig:** Build Subsystem 0 (data + refresh + publish) first; point the *existing Streamlit* app at the new Parquet/DuckDB layer to immediately fix slow loads. Then stand up the Next.js UI page-by-page reading the Workers API, retiring Streamlit pages as parity is reached. No flag day.

**Reuse:** Keep `generic_backtest.py`, `core/*` (indicators, regime, sue, piotroski, analytics, exit_analyzer, scorer) as the compute kernel — refactor I/O to read Parquet/DuckDB instead of per-ticker CSV. Standardize all strategies (hardcoded + generic) on one KPI contract for the leaderboard.

**Decomposition into buildable subsystems (each gets its own spec → plan → build):**
- **S0 — Data + refresh + publish foundation** (build first; unblocks all; fixes slow load).
- **S1 — Strategy factory + leaderboard** (extends existing engine + `strategies_index.json`).
- **S2 — Portfolio tracker** (new mutable state in D1; XIRR/PnL).
- **S3 — Goal/wealth planner** (depends on S2 + S1).
- **S4 — Next.js + shadcn/ui frontend + Workers API + Cloudflare Access** (progressive; can begin in parallel after S0's API contract is defined).

## 7. Open Questions

| Question | Owner | Deadline |
|----------|-------|----------|
| D1 vs Turso for app state (both SQLite, free, no-pause) — which integrates cleaner with Workers? | user | before S2 |
| Can the full nightly pipeline (downloads + 10y NSE/BSE backtests) complete within GitHub Actions free minutes + 6h job limit? Or split across jobs / cache datasets? | user | before S0 build |
| yfinance/NSE rate limits + IP blocking from GitHub Actions runners — need a proxy or self-hosted runner? | user | before S0 build |
| Ledger input method for v2 — manual entry only, or CSV import (P2 #16) deferred? | user | before S2 |
| Authoritative source for dividends/corporate actions (yfinance vs NSE) for return tracking. | user | before S1/S2 |
| Exact "rank score" formula for the leaderboard (weighting of CAGR/Sharpe/maxDD/win%/vs-Nifty). | user | during S1 brainstorm |

## 8. Timeline & Phasing

Phased; each phase ships independently and leaves the system working.

- **Phase 0 — Data foundation (S0):** Parquet/DuckDB conversion, Polars hot-path refactor, GitHub Actions nightly pipeline, R2 publish, point Streamlit at new layer. *Outcome: fast loads + auto-refresh, no UI change.*
- **Phase 1 — Strategy factory + leaderboard (S1):** standardized KPI contract, auto-backtest-on-add, ranked leaderboard (data + Streamlit view first). *Outcome: add/rank strategies.*
- **Phase 2 — Frontend cutover (S4):** Next.js + shadcn/ui + Workers API + Cloudflare Access; migrate home/strategies/leaderboard pages. *Outcome: modern private web app.*
- **Phase 3 — Portfolio tracker (S2):** ledger + XIRR/PnL in D1, portfolio page. *Outcome: track real investments/returns.*
- **Phase 4 — Goal planner (S3):** target, gap analysis, reach-faster levers. *Outcome: goal-driven guidance.*
- **Phase 5 — Enhancements (P2):** on-demand backtests, Monte-Carlo, alerts, broker import.

**Dependencies:** S0 precedes all. S4 needs S0's API contract. S3 needs S2 + S1. S1 reuses the existing engine; lowest risk after S0.

---

*Next step: brainstorm Subsystem 0 (data + refresh + publish foundation) into a detailed design spec, then an implementation plan, then build via subagent-driven development. Each later subsystem repeats the spec → plan → build cycle.*
