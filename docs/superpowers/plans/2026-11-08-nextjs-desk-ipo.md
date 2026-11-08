# Newly listed stocks (IPO) on the Next.js desk: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the "Newly listed stocks (IPO)" page in the Next.js desk (`web/`, route `/ipo`). It keeps the section flow and numbers of Streamlit's `render_ipo` (master_dashboard.py ~6603–6760) in the v2 Research Desk look already used by `/monthly` and `/momentum`.

**Architecture:** The Momentum recipe (`docs/superpowers/plans/2026-11-08-nextjs-desk-momentum.md`), smaller. A new Python save-results script `precompute_ui_ipo.py` calls the same `master_dashboard.py` functions `render_ipo` uses and writes `ui_ipo.json`. A server loader `web/lib/desk/ipo.ts` reads it and never throws. Pure mappers in `web/lib/desk/ipo-text.ts` turn saved numbers into display strings. Components under `web/components/desk/ipo/` draw the page.

**Tech Stack:** Python 3 + pandas (existing `.venv`), Next.js 16.2.7 App Router, React, TypeScript, Vitest, `lightweight-charts` (already installed), Playwright MCP.

**Spec:** `docs/superpowers/specs/2026-11-07-nextjs-research-desk-design.md` (§7.3–§7.5, §8). No mockup: the user said on 2026-11-08 "no need mockup … do implementation direct". Follow the `/momentum` page's look (`C:/Users/User/Documents/Stocks/.superpowers/audit/next-momentum-1280-light.png`).

## Decisions (Claude's calls; the user may override)

1. **No detail rail.** Streamlit's IPO page has no per-stock detail, so the page is list-only: summary card, screener table, past trades table, exit research. Rows are not clickable.
2. **The screener is empty today; the page shows that and does not fix it.** `IPO_UNIVERSE` (master_dashboard.py:93) holds 15 hard-coded IPOs, the newest listed on 23 Jan 2025. `_compute_ipo_signals` drops any listing older than 365 days, so `load_ipo()['signals']` is empty. The page shows Streamlit's empty state, and the cause is reported to the user. The backtest trades (127) and the equity curve come from `ipo_edge_*.csv` and are unaffected.
3. **Growth chart:** strategy vs NiftyBees (`Benchmark_Value` exists in `ipo_edge_equity.csv`), full period, no 1Y/3Y/All selector (Streamlit shows the full period). Label: "Simulated account vs Nifty".
4. **The explain box text is kept.** It matches the engine: a base after listing, a breakout with volume, an exit below the 10-day average or at a hard stop, and a partial profit at +15%.
5. **Past trades:** all saved trades, newest exit first, with an "All columns" toggle like Momentum (extra columns hidden below 1600px in the compact view).

## Global Constraints

- Branch `redesign/nextjs-desk`. Commit after every task (conventional commits, ending with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`).
- No new npm or pip packages.
- Every number, count and label is computed in Python. TypeScript only formats saved numbers. Python calls existing `master_dashboard` functions. The only copied rules are the win-rate fallback (render_ipo ~6633–6640), the stage counts (~6643–6650) and the trade extra-column rule "keep only columns with more than one distinct value" (~6735–6737), each with a comment naming its source line.
- `master_dashboard.py`: only the `_PRECOMPUTE_FOR` dict and its comment may change. Do not edit protected functions or files (`.superpowers/baseline/verify_protected.py`). `run_all.py` is protected: edit it, do not touch `checksums.txt`, and report the drift.
- Wording: Streamlit's plain-language strings verbatim (title, `rd-page__sub`, explain box, `section_help`, signal guide, Hist caption), with emojis and markdown dropped. "run **ipo_edge_downloader.py** first" becomes "Use “Update one strategy → IPO” in the sidebar". Pill labels use plain words: "Avg yearly return (CAGR)", "Worst fall from a peak", "Ready to break out", "Currently in trade", "Trades that made money".
- Python format strings map one to one: `₹{:,.2f}`, `{:+.1f}%`, `{:+.2f}%`, `{:.2f}×`, `₹{:.1f} Cr`, `{:.0f}%`.
- Layout: design at 1280×600, then check 1280×560, 1024×700, 1920×1000 and 390×844. No horizontal page scroll. No inner scroll boxes in default views. Tables show 15 rows plus "Show all N rows". Every column sorts.
- Tests. Python: `.venv/Scripts/python.exe -m pytest tests -q -p no:cacheprovider` (baseline 307). Web, from `web/`: `PYTHON_BIN=../.venv/Scripts/python.exe npx vitest run --exclude tests/glossary.test.ts` (baseline 314). `npx tsc --noEmit` clean. `npm run lint`: 2 errors + 3 warnings pre-exist; add none.

## Review Focus

1. **Empty screener (today's real state).** Expectation: the screener section shows the empty state; the summary, chart, trades and exit research render; the stage counts show 0. Pinned in Task 1 (`test_empty_signals_still_saves_trades`) and Task 4 (empty render test).
2. **Open trades** (Result "Open", no exit price or date). Expectation: the exit cells show `—`, the Result pill is a muted "Open", and the win rate uses Streamlit's rule (Result=='Win' over all rows). Pinned in Task 1 and Task 3 tests.
3. **No `Benchmark_Value` column, or no equity file.** Expectation: the chart has one trace, or the summary shows its empty state; nothing crashes. Pinned in Task 1.
4. **`Partial_Booked` as bool or "True"/"False" strings; `Entry_Stage` like "Stage 3 — Breakout".** Expectation: "Yes"/"No"/"—" and "Breakout", as in Streamlit. Pinned in Task 1.
5. **NaN in saved numbers** (e.g. `Listing PE` "—", a missing `Hist Win%`). Expectation: `—`, never "NaN". Pinned in Task 3.

---

### Task 1: `precompute_ui_ipo.py` writes `ui_ipo.json`

**Files:** Create `precompute_ui_ipo.py`; test `tests/test_precompute_ui_ipo.py` (pattern: `tests/test_precompute_ui_momentum.py`).

**Interfaces:**
- Consumes: `md.load_ipo()`, `md._equity_metrics(eq,'Portfolio_Value','Portfolio_Value')`, `md.chart_equity(eq, eq_col, md.S_IPO, colour, bench)` with `eq_col`/`bench` chosen as in render_ipo ~6676–6677, `md._build_report(md.S_IPO)` + `core_scorer.enrich_signals(sigs, report, feature_map={})` inside the same `try/except` as render_ipo ~6697–6704, `md._pick_rec('ipo_edge')`, `md.THEME[md.S_IPO]['color']`; `_clean`, `write_snapshot` and `_traces` from `precompute_ui_home`.
- Produces: `build_ui_ipo(i: dict) -> dict`, `main()`, `OUT = BASE_DIR / 'ui_ipo.json'`, `IPO_VERSION = 1`. Schema v1:

```text
{ version: 1, generated_at, colour,
  summary: null | { cagr, total_ret, max_dd, start, end },
  chart: null | [ { name, colour, dash, points: [["YYYY-MM-DD", pct], ...] } ],
  counts: { live_breakout, watch_zone, stage3, stage2, stage1, in_trade, trades, win_rate: number | null },
  signals: [ { symbol, company, signal, stage, setup, close, bk_level, vs_bk, vol_ratio, ipo_day_val,
               liquidity, promoter, listing_pe, age_days, score, hist_win, hist_avg } ],   # saved order
  trades: [ { id, symbol, entry_date, entry_price, exit_date, exit_price, pnl, hold_days, exit_reason,
              result, extras: { <column label>: string } } ],   # newest exit first; Open trades have null exit fields
  extra_columns: [label],     # the extras kept by the nunique > 1 rule, in Streamlit's order, with display labels
  exit_rec: null | { …_pick_rec('ipo_edge') unchanged } }
```

Notes: `win_rate` is the number behind Streamlit's `wr_str` (the Result branch, else the PnL>0 branch over Closed rows), or `None` where Streamlit shows `—`. `extras` values are already display strings (`Partial_Booked` → Yes/No/—; `Entry_Stage` → the text after "—"). Trade order: sort by `Exit_Date` descending with NaT last (Streamlit shows file order; record this as a ruling in the commit body). Signals keep the `_compute_ipo_signals` order.

- [ ] **Step 1: Failing tests** with fixture `i`: 2 signals including a NaN `Listing PE`; 5 trades including 1 Open with a NaN exit; string "True"/"False" `Partial_Booked`; an `Entry_Stage` of "Stage 3 — Breakout"; a constant column `Liquidity_Status`; equity with and without `Benchmark_Value`. Monkeypatch `md._build_report` → `{}`.
  - `test_summary_and_chart_use_dashboard_functions`: values equal `_equity_metrics`; chart trace names and y values equal `chart_equity(...).data`; 2 traces with the benchmark, 1 without.
  - `test_counts_match_render_ipo`: stage and signal counts; win_rate from Result.
  - `test_trades_display_rules`: Open trade exit fields are None; Partial_Booked gives Yes/No; Entry_Stage gives "Breakout"; the constant column is not in `extra_columns`.
  - `test_empty_signals_still_saves_trades`: `signals == []`, counts are zero, trades and summary are present.
  - `test_no_equity`: `summary is None`, `chart is None`.
  - `test_main_writes_atomic_json`: `version == 1`, no `.json.tmp` left.
- [ ] **Step 2: Run, expect FAIL.** `.venv/Scripts/python.exe -m pytest tests/test_precompute_ui_ipo.py -q -p no:cacheprovider`
- [ ] **Step 3: Implement.** `main()` prints `wrote ui_ipo.json: N signals, M trades`. Add `ui_ipo.json` and `ui_ipo.json.tmp` to `.gitignore` next to `ui_momentum.json`.
- [ ] **Step 4: Run, expect PASS; then run the real script** (expect `0 signals, 127 trades`).
- [ ] **Step 5: Commit** `feat(data): precompute_ui_ipo writes ui_ipo.json for the Next.js desk`

### Task 2: Run the script in the IPO and Momentum update paths

Same pattern as commit a5cbbd0. Append `'precompute_ui_ipo.py'` last in `_PRECOMPUTE_FOR['IPO']` and `['Momentum']` (Momentum runs `precompute_exit_recommendations.py`, which rewrites the IPO exit research). Also add it to `run_all.py` (after `precompute_ui_momentum.py`), `refresh_data.bat` (a new step after the Momentum page step; renumber) and `web/lib/desk/update-steps.ts`. Extend `tests/test_streamlit_updates_moved.py`: the last item of IPO and Momentum is `precompute_ui_ipo.py`, and it is absent from Monthly and PEAD. Verify with pytest and `npx vitest run tests/desk-update.test.ts`. Commit `feat: run precompute_ui_ipo in the IPO and Momentum update paths`.

### Task 3: Loader and display mappers

**Files:** Create `web/lib/desk/ipo.ts` (loader on `versioned-json.ts`, like `momentum.ts`) and `web/lib/desk/ipo-text.ts` (types, mappers, constants; no `node:fs`). Tests: `web/tests/desk-ipo.test.ts`, `web/tests/parity/ipo_streamlit_text.py`.

**Produces:**
- Types `UiIpo`, `IpoSummary`, `IpoCounts`, `IpoSignal`, `IpoTrade`.
- `loadIpo(dataDir?)` (missing / invalid / version / ok).
- `summaryStats(s, c)`, rows in order: Total return `{:+.1f}%`; Worst fall from a peak `{:.1f}%`; Trades that made money `${win:.0f}%` with sub `${trades} trades`; Ready to break out `${stage3}` with sub `Recovering: ${stage2} · Building: ${stage1}`; Currently in trade `${in_trade}` with sub `Live breakout signals: ${live_breakout}`.
- `signalCells(r)` (Streamlit formats; `—` for null) and `tradeCells(r)`.
- `signalTone(signal)` (Live Breakout gain, Watch Zone warn, Forming Base info, Avoid loss, else muted) and `resultTone(result)` (Win gain, Loss loss, Open muted).
- Constants: `IPO_TITLE`, `IPO_SUB`, `HOW_IT_WORKS` (segments with bold parts, as Monthly's), `HOW_TO_READ`, `SIGNAL_GUIDE` (`[label, meaning][]`), `STAGE_GUIDE`, `HIST_NOTE`, `EMPTY_NO_SIGNALS` (title "No IPO setups to show", with a reason naming the sidebar update), `CHART_LABEL`, `CONTEXT_UNIVERSE` "Newly listed NSE stocks (last 12 months)", `CONTEXT_RULE` "Breakout above the post-listing base with volume". Reuse `CONTEXT_BASIS`.

- [ ] Unit tests: formats including `₹539.2 Cr`, nulls → `—`, tones, exact summaryStats rows, loader states. Parity test (`describe.skipIf(!PYTHON_BIN)`): the harness prints Streamlit's formatted trade rows for the first 15 trades, using render_ipo's lambdas, and the five pill values; assert they are equal. Commit `feat(web): IPO loader and display text with Streamlit parity test`.

### Task 4: The `/ipo` page

**Files:**
- `web/app/ipo/page.tsx` (server, `dynamic = "force-dynamic"`).
- `web/components/desk/ipo/ipo-desk.tsx`, `summary-card.tsx`, `screener.tsx`, `past-trades.tsx`. The summary card reuses the Momentum summary-card structure: BigValue + StatBars on the left, the chart on the right. Reuse `web/components/desk/monthly/equity-chart.tsx` if it accepts saved traces, otherwise the Momentum chart.
- Nav href `"/ipo"`, with the test `strategyPageHref("IPO","WAAREEENER")` → `/ipo?ticker=WAAREEENER`. The ticker param is accepted and ignored, except to highlight the row if present.

Page order (as render_ipo):
1. Header (+ age pill from `savedDataAges()` "IPO Edge").
2. ContextBar.
3. Explain box (`HOW_IT_WORKS`) + `HOW_TO_READ` disclosure.
4. Summary card.
5. `SectionHead("Live screener", "IPOs listed in the last 12 months")`, the signal/stage guide line, and the screener `DeskTable` + `HIST_NOTE`, or `EMPTY_NO_SIGNALS`. The compact screener shows Company, Signal, Stage, Close, vs Bk%, Vol ratio and Score; "All columns" adds Setup, Bk level, IPO day value, Liquidity, Promoter, Listing PE, Age, Hist Win% and Hist Avg%.
6. `Tabs`: "Past trades (N)" (compact: Stock, Bought, At, Sold, At, Result pill, Held, Why sold; "All columns" adds `extra_columns`) and "How the model exits" (`ExitResearch({rec, title:"Exit research: Newly listed stocks (IPO)"})`).
7. `ResearchNotice`, `GlossaryDisclosure`.

Every column sorts. `.desk-compact` hides p3 below 1600px, as on Momentum.

- [ ] Failing nav test → implement → render test with empty signals and a null summary (no NaN/null/undefined in the markup) → web tests, tsc, lint → dev server (check free memory > 1572864 KB first) and a browser check at 1280×600 with no console errors and numbers equal to `ui_ipo.json` → commit `feat(web): Newly listed stocks (IPO) page in the Research Desk style`.

### Task 5: Fit audit, screenshots, handoff

- Add `"/ipo"` to `PAGES` in `web/tests/fit/fit-audit.js` and run the audit (ALL PASS, 4 pages × 5 viewports).
- Screenshots: `C:/Users/User/Documents/Stocks/.superpowers/audit/next-ipo-{1280,390}-{light,dark}.png`.
- Full verification: pytest, vitest, tsc, lint, and verify_protected (only `run_all.py` drift expected).
- Update `MEMORY.md` (git-ignored; on disk only): IPO built, its commits, the `IPO_UNIVERSE` oddity, and the next page, After earnings (PEAD).
- Commit `test(web): fit audit covers the IPO page`.
