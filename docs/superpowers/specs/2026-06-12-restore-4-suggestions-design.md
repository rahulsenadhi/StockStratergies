# Restore Slice 4 — Suggestions / "Buy These Now" (design)

Date: 2026-06-12. Restore-program slice 4 (buying-priority). Port the Streamlit
Suggestions page (`master_dashboard.py:render_suggestions` + `_build_*_suggestions`
+ `_edge_buckets` + `_regime_snapshot`) into the Next.js app **additively**, in the
existing dense SaaS layout.

## What it does (faithful port)
Live signals re-ranked by **historical edge**, **regime-gated**, each pick wrapped
with entry / stop / target / R:R / confidence / max-position-size / plain-English
rationale.

- **Step 1 — Edge buckets.** Group closed trades by setup (Momentum: Entry_Type ×
  Recovery_Speed; IPO: Setup_Type), keep buckets with positive expectancy
  (`edge_score = expectancy × √n`, `min_n` gate). Port of `_edge_buckets`.
- **Step 2 — Filter today's signals** to approved buckets only.
- **Step 3 — Regime gate.** Nifty 3-condition regime (`core.regime.build_series`).
  Bull → entries allowed; Bear → position sizes halved, IPO picks suspended.
- **Step 4 — Risk wrap.** Per-pick stop/target/R:R/position_pct/rationale,
  matching each builder's constants verbatim.

## Architecture (precompute pattern — same as slices 2 & 3)
Heavy compute (regime build, edge buckets, per-strategy filtering) runs in **Python
precompute → `suggestions.json`** at repo root; the Next.js side is a thin loader +
RSC page. Mirrors `precompute_exit_recommendations.py` → `exit_recommendations.json`.

- **`precompute_suggestions.py`** (repo root) — pure testable functions
  (`edge_buckets`, `build_monthly_suggestions`, `build_momentum_suggestions`,
  `build_ipo_suggestions`, `compute_regime`, `assemble`) + I/O `build_all` + `main`.
  Writes `suggestions.json`.
- JSON shape: `{ regime:{status,barsSinceFlip,close,sma50,sma200,high52,pctFromHigh,date},
  summary:{picks,avgConfidence,totalAllocation,cashReserve}, picks:[{rank,ticker,
  company,strategy,strategyId,signal,close,stop,target,rr,confidence,avgPnl,nHist,
  positionPct,edgeScore,rationale}] }`. Picks sorted by `edgeScore` desc, re-ranked 1..N.
- **`getSuggestions(dataDir?)`** in `web/lib/data/strategies.ts` — reads
  `suggestions.json` (repo root via DATA_DIR), camelCased already, `null` on any error.
- **`/suggestions`** RSC page: regime banner + 4-tile KPI strip (Picks/Avg-Conf/
  Allocation/Cash) + dense pick cards (rank · strategy · ticker · confidence% ·
  signal/entry/stop/target/R:R row · avg-hist-PnL + max-position row · rationale).
  Per-strategy filter tabs deferred (single ranked list first — dense, all picks).
- Nav: "Buy Now" link (app-shell sidebar).

## Faithful constants (do NOT reinvent)
- Monthly: stop ×0.92, target ×1.10, pos 20/10 bull/bear, Strong-BUY filter, top-5.
- Momentum: stop = max(close×0.85, 220EMA), target ×1.25, pos 12/6, clean-chart +
  approved (Entry_Type×Recovery) bucket filter, fallback unfiltered if no match.
- IPO: stop ×0.92, target ×1.20, pos 8/4, Breakout/Near + best Setup_Type;
  **bull-only**. (No IPO signals CSV today → IPO pool empty; faithful degradation.)
- Confidence = bucket historical win-rate. edge_score = win_rate + Score.

## Out of scope (separate slices)
Confidence verdict card (5-criteria, detail page) · Position Sizer (client calc) ·
data-staleness/Update · PEAD screener · Insights. Rationale HTML `<b>` stripped to
plain text. Refresh = manual `python precompute_suggestions.py` (wire into pipeline later).

## Security
Read-only; no request input; precompute reads local CSVs only. Page is RSC over a
static JSON file. No new write endpoints.
