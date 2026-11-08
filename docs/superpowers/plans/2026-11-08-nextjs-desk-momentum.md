# Price strength (Momentum) on the Next.js desk: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the "Price strength (Momentum)" page in the Next.js desk (`web/`, route `/momentum`). It keeps the section flow and numbers of Streamlit's `render_momentum` and uses the approved mockup layout (`C:/Users/User/Documents/Stocks/.superpowers/mockups/momentum-v2.html`, screenshot `.superpowers/audit/mock-momentum-1280-full.png`).

**Architecture:** The Monthly recipe again. A new Python save-results script `precompute_ui_momentum.py` calls the same `master_dashboard.py` functions `render_momentum` uses and writes `ui_momentum.json`. A server loader in `web/lib/desk/momentum.ts` reads that file and never throws. Pure mappers in `web/lib/desk/momentum-text.ts` turn saved numbers into display strings. Components under `web/components/desk/momentum/` draw the page. The script joins the IPO and Momentum update paths.

**Tech Stack:** Python 3 + pandas (existing `.venv`), Next.js 16.2.7 App Router, React, TypeScript, Vitest, `lightweight-charts` (already installed), Playwright MCP for the fit audit.

**Spec:** `docs/superpowers/specs/2026-11-07-nextjs-research-desk-design.md` (§7.3–§7.5, §8), plus the approved mockup above. Content source: `master_dashboard.py` `render_momentum` (~6923–7560) and its helpers. Recipe and rulings: `MEMORY.md` → "Next.js desk notes". The Monthly plan (`docs/superpowers/plans/2026-11-07-nextjs-desk-monthly.md`) shows the pattern for every task below.

## Decisions taken for this page (user said "continue" to these defaults, 2026-11-08)

1. **"Run Backtest on {ticker}" stays in Streamlit.** No new job endpoint. The rail shows the link "Full indicator chart and single-stock test: open in the old app" (`STREAMLIT_URL`).
2. **One chart in the rail** replaces the 2-column chart grids in the Forming and Recent tabs, and the multi-panel "Drill into any signal" chart (RSI/MACD/ADX/OBV badges stay in Streamlit, reached by the same link).
3. **The breakout switch** ("52-week or all-time high" / "All-time high only") filters setups, past trades and the trade stats only. The CAGR, total return, worst fall and growth chart always use the saved equity file, which holds every trade. The page says so (`ATH_NOTE`).
4. **Rail lookup universe** = today's signals plus the recent (7-day) breakouts. Streamlit's picker also lists every stock that ever broke out (`_scan_all_breakouts`); that wide lookup stays in Streamlit.
5. **The growth chart has no 1Y/3Y/All selector.** Streamlit's Momentum chart shows the full period only. The mockup's selector is dropped, and the label is "Simulated account (₹10 lakh start)", because the Momentum equity file has no Nifty column.
6. **Tab counts come from Python's `_action_from_signal`.** "Watch Zone" maps to FORMING and "Near Breakout" maps to WATCH. The mockup showed "Watch 31 / Forming 0"; with today's data it is "Watch 0 / Forming 31".

## Global Constraints

- Branch `redesign/nextjs-desk`. Commit after every task (conventional commits, attribution line from the session).
- No new npm or pip packages. Charts use `lightweight-charts`.
- Every number, filter list and label is computed in Python. TypeScript only formats saved numbers and intersects saved id lists. It never re-implements a formula, filter rule or cutoff.
- Python must not copy formulas either, with these named exceptions, each copied verbatim with a comment naming its source line: the ATH filter (`render_momentum` ~6957–6961), the trade period cutoffs and the strict mask (~7442–7458). Everything else calls existing `master_dashboard` functions.
- `master_dashboard.py`: the only edit allowed is the `_PRECOMPUTE_FOR` dict (approved pattern). Do not edit protected functions or files (`.superpowers/baseline/verify_protected.py`).
- Wording: Streamlit's plain-language strings verbatim where they exist (page title, `rd-page__sub`, `section_help`, the exit expander text, the BUY NOW caption, the Hist caption, the funnel caption, the past-trades legend). Emojis are dropped. Labels new in the mockup replace Streamlit's jargon labels (listed in Task 4 as constants). Streamlit's "How This Strategy Works" box is **not** copied: it says "only buy when … all-time high" and lists a profit-target exit, which contradicts the engine (52-week fallback entries are taken; no target exit). The accurate exit expander text is used instead. The stale "DIACABS broke out 15 May" example is dropped from the Recent explanation. "Path to 100% success" becomes "Best historical combo".
- "Run `momentum_edge_downloader.py`" in the empty state becomes "Use “Update one strategy → Momentum” in the sidebar".
- Python format strings map one to one: `₹{:,.2f}`, `{:+.1f}%`, `{:+.2f}%`, `{:.2f}×`, `{:.0f}%`, `{:.1f}`.
- Layout: design at 1280×600 first, then check 1280×560, 1024×700, 1920×1000 and 390×844. No horizontal page scroll. No inner scroll boxes. Tables show 15 rows plus "Show all N rows". Every table sorts. The rail stacks below the table under 1200px and is sticky only at `min-width:1200px and min-height:900px` (existing `.desk-rail`).
- Test commands. Python: `.venv/Scripts/python.exe -m pytest tests -q -p no:cacheprovider` (baseline 290 passed). Web, from `web/`: `PYTHON_BIN=../.venv/Scripts/python.exe npx vitest run --exclude tests/glossary.test.ts` (baseline 288 passed). `npx tsc --noEmit` clean. `npm run lint`: 2 errors + 3 warnings already exist in untouched files; add none.

## Review Focus

1. **No signals today** (empty `momentum_edge_signals.csv`, or all filtered out by "All-time high only"). Expectation: the setups table shows its empty state, the rail shows "Pick a stock" text, and the funnel, summary and past trades still render. Pinned in Task 1 (`test_empty_signals`) and Task 4 (`resolveSelected` with an empty list).
2. **Selected stock hidden by the switch or a tab.** Expectation: the rail keeps the stock (as on Monthly); only the table changes. Pinned in Task 4: `resolveSelected` searches signals and recent breakouts, never a filtered list.
3. **Missing or short price file for one stock.** `_render_criteria_panel` then calls `st.info(...)` instead of drawing cards. Expectation: that stock's rail shows the info text as an empty state, and the rest of the page renders. Pinned in Task 1 (`test_criteria_missing_file_gives_note`).
4. **`?ticker=` from Home** for a recent-breakout stock, an unknown stock, or one with `.NS`. Expectation: a match selects it (switching the table tab to "Broke out last 7 days" when it is only there); anything else falls back to the first signal, then the first recent breakout. Pinned in Task 4 `resolveSelected` tests.
5. **Saved file too big or slow.** About 160 stocks × 90 sessions of two series. Expectation: `ui_momentum.json` stays under 1.5 MB and the script finishes in under 60 s. Pinned in Task 1 Step 4 (prints size and time; the step fails if over).

---

### Task 1: `precompute_ui_momentum.py` writes `ui_momentum.json`

**Files:**
- Create: `precompute_ui_momentum.py`
- Test: `tests/test_precompute_ui_momentum.py` (same `md` loading pattern as `tests/test_precompute_ui_monthly.py`)

**Interfaces:**
- Consumes (existing, from `master_dashboard`): `load_momentum()`, `_equity_metrics(eq,'Equity','Equity')`, `chart_equity(eq,'Equity',md.S_MOMENTUM,colour)`, `_strategy_health(trades, sigs)`, `_build_report(md.S_MOMENTUM)`, `core_scorer.enrich_signals(sigs, report, feature_map={'Entry Type':'Entry_Type','Recovery':'Recovery_Speed'})`, `_suggest_stop(px, atr=None, winner_mae_p95_pct=p95)`, `_action_from_signal(s, True)`, `_verify_past_trades(trades)`, `_summarize_filter_detail(d)`, `_render_criteria_panel(ticker)`, `_compute_full_indicators(path)`, `_regime_snapshot()`, `_pick_rec('momentum_edge')`, `THEME[S_MOMENTUM]['color']`. From `precompute_ui_home`: `_clean`, `write_snapshot`. Chart traces: move the trace-reading comprehension from `precompute_ui_monthly._chart` into a shared `_traces(fig) -> list[dict]` in `precompute_ui_home.py`, and use it from both scripts (Monthly tests must still pass).
- Produces: `build_ui_momentum(mo: dict) -> dict`, `main() -> None`, `OUT = BASE_DIR / 'ui_momentum.json'`, `MOMENTUM_VERSION = 1`, `CHART_SESSIONS = 90`. JSON schema v1, consumed by Task 4:

```text
{ version: 1, generated_at, colour,
  summary: null | { cagr, total_ret, max_dd, start, end },              # _equity_metrics on the saved equity
  chart: null | [ { name, colour, dash, points: [["YYYY-MM-DD", pct], ...] } ],   # chart_equity traces
  views: { "all" | "ath": {
      health: { n_trades, win_rate, avg_pnl, median_pnl, median_hold, safe_20d_pct, universe,
                verdict_text, verdict_tone: "gain"|"warn"|"loss"|"muted", best_combo, top_lift },
      counts: { breakout, near, watch, ath, clean, fast },              # render_momentum's n_bk … n_fast
      signal_ids: [symbol], trade_ids: [int] } },
  signals: [ { symbol, company, signal, action, close, ath, dist_ath, entry_type, chart_qual,
               choppiness, recovery, ema220, high52, vs_high, vol_ratio, score,
               hist_win, hist_avg, hist_n, stop_price, stop_pct } ],     # file order (score order)
  tabs: { "All" | "BUY NOW" | "WATCH" | "FORMING": [symbol] },
  recent: [ { symbol, days_ago, bk_date, bk_price, close, off_bk, ema220, vol_ratio, stop } ],
  funnel: null | { is_bull: bool, total: int, steps: [ { key, count } ] },   # keys in _chart_me_funnel order
  details: { symbol: { conditions: null | [ { ok, label, sub, detail } ], note: string | null,
                       chart: null | { saved_to: "06 Nov 2026", close: [[d, v]], ema220: [[d, v]],
                                       level: null | { label, value } },
                       past_trades: int } },
  trades: [ { id, symbol, entry_date, entry_price, prior_high, bk_margin, exit_date, exit_price,
              pnl, hold_days, exit_reason, result, filters, entry_type, recovery } ],   # newest exit first
  trade_filters: { periods: { "Last 1Y" | "Last 3Y" | "All" | "<year>": [id] }, years: [int], strict: [id] },
  exit_rec: null | { …_pick_rec('momentum_edge') unchanged } }
```

Notes for the implementer:
- `signals` come from `load_momentum()['signals']` after `enrich_signals` and the stop columns, done exactly as `render_momentum` ~7114–7130 (wrap `_build_report` in the same `try/except` and fall back to `p95=None`).
- `views.ath` uses the copied ATH filter on both `trades` and `signals`. `health` is `_strategy_health(trades_view, sigs_view)` with the colour fields replaced by `verdict_tone` (`var(--success)`→gain, `var(--warning)`→warn, `var(--destructive)`→loss, else muted).
- `details` covers every symbol in `signals` ∪ `recent`. `conditions` and `note` come from running `md._render_criteria_panel(symbol)` with `md.st` swapped for a recorder (`markdown(html, **kw)` and `info(text)` append; `columns(n)` returns n `contextlib.nullcontext()` objects). Restore `md.st` in `finally`. Parse each `crit-ok`/`crit-fail` block into `ok`, the `crit-label` text, the grey sub `div` and the `crit-detail` text, all `html.unescape`d. Seven blocks in order (F1–F6, then the breakout trigger).
- `chart` uses `_compute_full_indicators` on the first existing path of `data/nse_bse/{T}.NS.csv`, `momentum_edge_data/{T}.NS.csv`, `data/nse_bse/{T}.csv` (`_render_me_detail` order), keeping the last `CHART_SESSIONS` rows of `Close` and `ema220`. `level` = `{label:"52-week high", value: signal['52W High']}` for a signal, else `{label:"Breakout price", value: recent['Bk Price (₹)']}`.
- `trades` are `_verify_past_trades(trades)` sorted by `Exit_Date` descending; `id` is the position in that sorted list. `entry_type` is `"All-time high"` / `"52W high"`, `recovery` is `"{speed} · {days}d"` or the speed alone (render_momentum ~7488–7497), and `filters` is `_summarize_filter_detail`.
- `funnel` is `None` unless `funnel['total'] > 0`; `is_bull` as render_momentum ~7306–7311.

- [ ] **Step 1: Write the failing tests** with a fixture `mo`: 3 signals (`Watch Zone` ATH, `Near Breakout` 52W, `Breakout Today` ATH), 2 recent breakouts, 6 trades over 3 years (mixed ATH / 52W, wins and losses), a 300-row equity frame and a funnel dict. Monkeypatch `md._build_report` to return `{}`, `md._regime_snapshot` to `{'status':'Bull'}`, and `md._loss_free_holding` to an empty frame.
  - `test_summary_and_chart_use_dashboard_functions`: `summary['cagr'] == md._equity_metrics(eq,'Equity','Equity')['cagr']` (also `total_ret`, `max_dd`); `chart[0]['name'] == md.chart_equity(...).data[0].name`, with the same y values.
  - `test_views_all_and_ath`: `views['all']['health']` equals `_strategy_health(trades, sigs)` minus the colour keys; `views['ath']['signal_ids']` holds only the two ATH symbols; `views['ath']['trade_ids']` holds only ATH trade ids.
  - `test_tabs_use_action_from_signal`: `tabs['FORMING'] == [the Watch Zone symbol]`, `tabs['WATCH'] == [the Near Breakout symbol]`, `tabs['BUY NOW'] == [the Breakout Today symbol]`.
  - `test_criteria_parsed_from_render_panel`: with a 400-row synthetic OHLCV CSV under a monkeypatched `md.BASE_DIR`, `details[s]['conditions']` has 7 items, `[c['label'][:2] for c in conds[:6]] == ['F1','F2','F3','F4','F5','F6']`, the last label contains `Breakout Trigger`, and every `ok` is a bool.
  - `test_criteria_missing_file_gives_note`: a symbol with no CSV gives `conditions is None` and `note == 'No OHLCV file for ZZZ — cannot render criteria.'`, and `md.st` is the real module afterwards.
  - `test_chart_last_90_and_level`: `len(chart['close']) == 90`; `level['label'] == '52-week high'` for a signal and `'Breakout price'` for a recent-only symbol.
  - `test_trade_filters`: `periods['All']` is every id; `periods['Last 1Y']` equals the ids whose exit is within 365 days of the latest exit; `years` is descending; `strict` equals the ids with `All_Filters_OK` and `Breakout_Margin_Pct >= 1.0`.
  - `test_empty_signals`: an empty signals frame gives `signals == []`, every tab `[]`, `details` only for recent symbols, and `summary` still set.
  - `test_main_writes_atomic_json`: as in the Monthly test (`version == 1`, no `.json.tmp` left).
- [ ] **Step 2: Run, expect FAIL** (`ModuleNotFoundError: precompute_ui_momentum`).
  Run: `.venv/Scripts/python.exe -m pytest tests/test_precompute_ui_momentum.py -q -p no:cacheprovider`
- [ ] **Step 3: Implement** `precompute_ui_momentum.py` (docstring style of `precompute_ui_monthly.py`, naming the copied rules) and the shared `_traces`. `main()` prints `wrote ui_momentum.json: N signals, M recent, K trades`.
- [ ] **Step 4: Run, expect PASS** (new tests and `tests/test_precompute_ui_monthly.py`). Run the real script with timing: `time .venv/Scripts/python.exe precompute_ui_momentum.py && ls -l ui_momentum.json`. Expected: about `31 signals, 125 recent, 144 trades`, under 60 s, under 1.5 MB. Check `git check-ignore ui_momentum.json`; if the file is not ignored, add it next to `ui_monthly.json` in `.gitignore`.
- [ ] **Step 5: Commit** `feat(data): precompute_ui_momentum writes ui_momentum.json for the Next.js desk`

### Task 2: Run the script in the IPO and Momentum update paths

**Files:**
- Modify: `master_dashboard.py` `_PRECOMPUTE_FOR` (~4858): append `'precompute_ui_momentum.py'` last in **IPO** and **Momentum** (both run `precompute_exit_recommendations.py`, which rewrites the momentum exit research). Add one line to the comment above the dict: `precompute_ui_momentum.py (last) saves the Momentum page's data.`
- Modify: `run_all.py` `PRECOMPUTE`: append after `precompute_ui_monthly.py` with `# ui_momentum.json (Next.js Momentum)`.
- Modify: `refresh_data.bat`: add a step after the Monthly page step, same pattern; renumber `[n/N]`.
- Modify: `web/lib/desk/update-steps.ts`: mirror the change.
- Test: `tests/test_streamlit_updates_moved.py::test_step_lists_still_defined_for_the_web_app`; `web/tests/desk-update.test.ts` (parity vs Python).

- [ ] **Step 1: Failing test.** Add `assert md._PRECOMPUTE_FOR['Momentum'][-1] == 'precompute_ui_momentum.py'`, the same for `'IPO'`, and `assert 'precompute_ui_momentum.py' not in md._PRECOMPUTE_FOR['Monthly'] + md._PRECOMPUTE_FOR['PEAD']`.
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Edit the four files.**
- [ ] **Step 4: Verify.** The Python test and `PYTHON_BIN=../.venv/Scripts/python.exe npx vitest run tests/desk-update.test.ts` pass. `verify_protected.py` reports no new function drift, only the known KPI drift. If `run_all.py` is in `checksums.txt`, re-baseline it only after telling the user (approved last time for the same kind of edit).
- [ ] **Step 5: Commit** `feat: run precompute_ui_momentum in the IPO and Momentum update paths`

### Task 3: Share the exit research block between Monthly and Momentum

**Files:**
- Create: `web/lib/desk/exit-text.ts`: move `ExitTarget`, `ExitRec`, `exitTexts`, `EXIT_CAPTION`, `EXIT_LABELS` and `EXIT_EMPTY` out of `monthly-text.ts`. `monthly-text.ts` re-exports them, so existing imports keep working.
- Create: `web/components/desk/exit-research.tsx`: move `Metric`, `TargetRow`, `TARGET_COLUMNS` and `ExitResearch` out of `monthly/lower-tabs.tsx`. New signature: `ExitResearch({ rec, title }: { rec: ExitRec | null; title: string })`.
- Modify: `web/components/desk/monthly/lower-tabs.tsx`: import it and pass `title="Exit research: Monthly stock rotation"` (the current `EXIT_TITLE` text).
- Test: `web/tests/desk-monthly.test.ts` (existing exit tests keep passing), plus one new `renderToStaticMarkup` test in `web/tests/desk-primitives.test.ts`: `ExitResearch({rec:null,title:"x"})` renders the `EXIT_EMPTY` text, and with the sample rec it renders the given title.

- [ ] **Step 1: Failing test** (new import path). **Step 2: Run, expect FAIL.** **Step 3: Move the code.** **Step 4: Web tests, tsc and lint pass; the `/monthly` Exit research tab looks unchanged.** **Step 5: Commit** `refactor(web): share the exit research block between desk pages`

### Task 4: Loader and display mappers

**Files:**
- Create: `web/lib/desk/momentum.ts` (server loader only; uses the shared `versioned-json.ts` loader like `monthly.ts`)
- Create: `web/lib/desk/momentum-text.ts` (types, pure mappers, copy constants; no `node:fs`)
- Test: `web/tests/desk-momentum.test.ts`, `web/tests/parity/momentum_streamlit_text.py`

**Interfaces:**
- Consumes: `ui_momentum.json` (Task 1); `formatSigned`, `formatRupees`, `formatNumber`, `Tone`, `freshnessLabel`, `freshnessTone` from `format.ts`; `ExitRec` from `exit-text.ts`.
- Produces (used by Task 5):
  - Types `UiMomentum`, `MomentumSummary`, `MomentumView`, `Health`, `SignalRow`, `RecentRow`, `FunnelData`, `StockDetail`, `Condition`, `TradeRow`, `TradeFilters`; `ViewKey = "all" | "ath"`; `SetupTab = "All" | "BUY NOW" | "WATCH" | "FORMING" | "Recent"`; `TradePeriod = "Last 1Y" | "Last 3Y" | "All" | "Pick year"`.
  - `loadMomentum(dataDir?: string): Promise<{ ok: true; data: UiMomentum } | { ok: false; reason: "missing" | "invalid" | "version" }>`.
  - `resolveSelected(data: Pick<UiMomentum,"signals"|"recent">, requested?: string | null): { symbol: string | null; tab: SetupTab }`. It strips `.NS`. A signal match gives tab `"All"`; a recent-only match gives `"Recent"`; otherwise the first signal (`"All"`), then the first recent (`"Recent"`), then `{symbol:null, tab:"All"}`.
  - `tabRows(data, view: ViewKey, tab: Exclude<SetupTab,"Recent">): SignalRow[]`: the signals whose symbol is in both `views[view].signal_ids` and `tabs[tab]`, in saved order.
  - `tabLabels(data, view): { id: SetupTab; label: string }[]`: `All N`, `Buy now N`, `Watch N`, `Forming N`, `Broke out last 7 days N`.
  - `visibleTrades(data, view, period: TradePeriod, year: number | null, strict: boolean): { rows: TradeRow[]; hidden: number }`: the intersection of `views[view].trade_ids`, `periods[period]` (or `periods[String(year)]` for "Pick year") and, when `strict`, the `strict` ids. `hidden` = the count removed by strict alone.
  - `tradesCaption(shown, total, firstExit, lastExit, strict, hidden): string`: the render_momentum ~7460–7466 wording without `**` and emoji.
  - `healthStats(h: Health, s: MomentumSummary | null): { label; value; sub?; tone }[]`, rows in order: Total return `{:+.1f}%` (gain/loss), Worst fall from a peak `{:.1f}%` (loss), Trades that made money `${win:.0f}% of ${n}` (gain ≥ 50, else warn), Average per trade `{:+.2f}%` with sub `median {:+.2f}%`, Typical hold `${n} days` (muted), Loss-free 20+ days `{:.0f}%` (gain ≥ 40, else warn). The two summary rows show `—` when `s` is null.
  - `signalCells(r)`, `recentCells(r)`, `tradeCells(r)`: the Streamlit `_render_subset` and trades formats (Global Constraints).
  - `conditionTitle(label: string): string`: `F1`→"Long-term trend up", `F2`→"Price above 50-day average", `F3`→"Averages stacked in order", `F4`→"Well above yearly low", `F5`→"Recent dip below 220-day line", `F6`→"Clean chart", a label containing `Breakout Trigger`→"Breakout with volume", anything else→the label. The Streamlit label and detail show underneath.
  - `FUNNEL_LABELS: Record<string,string>`: total "Universe", sufficient_data "Has 1 year of prices", f1 "Long-term trend up", f2 "Above 50-day average", f3 "Averages stacked", f4 "Above yearly low", f5 "Dip recovered", f6 "Clean chart", vol_bk "Breakout + volume".
  - Copy constants: `MOMENTUM_TITLE` "Price strength (Momentum)", `MOMENTUM_SUB` (Streamlit `rd-page__sub`), `HOW_TO_READ` (`section_help`), `BUY_NOW_NOTE`, `EXIT_RULES` (the expander text), `ATH_SWITCH_LABEL` "Which breakouts count", `ATH_OPTIONS` ["52-week or all-time high", "All-time high only"], `ATH_NOTE` ("Yearly return, total return, worst fall and the growth chart always include every saved trade. The switch changes the setups, past trades and trade stats."), `CHART_LABEL` "Simulated account (₹10 lakh start)", `CHART_NOTE` (Streamlit equity note), `SETUPS_TITLE` "Today's setups", `SETUPS_META` "Sorted by score · evaluated on yesterday's close", `RECENT_NOTE`, `HIST_NOTE`, `FUNNEL_TITLE(total)` "How {total} stocks narrow to today's list", `FUNNEL_NOTE`, `TRADES_LEGEND`, `COLUMN_GUIDE` (`[column, meaning][]` from the Streamlit expander table), `OLD_APP_LINK`, `EMPTY_NO_SIGNALS`, `CONTEXT_UNIVERSE(total)` "NSE + BSE, {total} stocks", `CONTEXT_RULE` "New high above 220-day line · exit −15% or close below it". Reuse Monthly's `CONTEXT_BASIS`.

- [ ] **Step 1: Failing unit tests** in `web/tests/desk-momentum.test.ts`: `resolveSelected` (signal, recent-only, `"TITAN.NS"`, unknown, both lists empty); `tabRows` with a view that hides the selected stock; `visibleTrades` intersection and `hidden`; `healthStats` for `{win_rate:31.9,n_trades:144,avg_pnl:4.74,median_pnl:-6.1,median_hold:111,safe_20d_pct:22}` with summary `{total_ret:116.79,max_dd:-31.53}` deep-equals the expected rows; `conditionTitle` for each prefix; `signalCells` for the TITAN row gives `₹5,000.00`, `-3.1%`, `6.28×` and `68.3`; `loadMomentum` gives missing / invalid / version / ok (as Monthly).
- [ ] **Step 2: Run, expect FAIL.** `npx vitest run tests/desk-momentum.test.ts`
- [ ] **Step 3: Implement** both files.
- [ ] **Step 4: Parity test (`describe.skipIf(!PYTHON_BIN)`).** Run `precompute_ui_momentum.py`, then `web/tests/parity/momentum_streamlit_text.py`. The harness prints Streamlit's own cell strings: `_render_subset`'s formatted frame for the "All" tab (essential columns), the first 15 rows of the formatted trades table for "All", and the health numbers. Assert that the TS mappers on the loaded JSON give equal arrays.
- [ ] **Step 5: Web tests and tsc pass. Commit** `feat(web): Momentum loader and display text with Streamlit parity test`

### Task 5: The `/momentum` page

**Files:**
- Create: `web/app/momentum/page.tsx` (server, `dynamic = "force-dynamic"`, Promise `searchParams` as in `app/monthly/page.tsx`)
- Create under `web/components/desk/momentum/`: `momentum-desk.tsx` (client; owns the switch state `view` and renders the summary card, setups and past trades, so all three follow the switch), `summary-card.tsx`, `setups-desk.tsx` (tabs, table, rail), `stock-rail.tsx`, `rail-chart.tsx` (`lightweight-charts`: close line, dotted EMA220, dashed level line with its label), `funnel.tsx` (CSS bars in the `rd-bar` style), `past-trades.tsx`, `lower-tabs.tsx`
- Modify: `web/lib/desk/nav.ts`: Momentum `href: "/momentum"`
- Test: `web/tests/desk-nav.test.ts`: `strategyPageHref("Momentum","TITAN")` equals `{ href: "/momentum?ticker=TITAN", external: false }`

**Interfaces:** Consumes Tasks 3–4 and the existing `PageHeader`, `StatusPill`, `ChangePill`, `ContextBar`, `BigValue`, `StatBar`, `SectionHead`, `Segmented`, `DeskTable`, `NameCell`, `RailList`, `EmptyState`, `Tabs`, `ResearchNotice`, `GlossaryDisclosure`, `savedDataAges()` ("Momentum" entry). Produces route `/momentum?ticker=SYMBOL`.

Page order (the mockup order, which follows Streamlit's flow):
1. `PageHeader` (`MOMENTUM_TITLE`, `MOMENTUM_SUB`); right side: the signals-age pill + `StatusPill("“Buy now” is a model label","muted")`. On load failure: Home's "not ready" pattern naming `ui_momentum.json`.
2. `ContextBar`: Universe `CONTEXT_UNIVERSE(funnel.total)` (or "NSE + BSE" with no funnel), Test period `start → end`, Rule, basis.
3. Switch row: `ATH_SWITCH_LABEL` + `Segmented(ATH_OPTIONS)` (default the first), with `ATH_NOTE` under it as `rd-note`.
4. `SummaryCard`: left = label "Avg yearly return (CAGR)", `BigValue(cagr)`, the verdict `StatusPill(verdict_text, verdict_tone)`, `healthStats` as `StatBar`s, then `Best historical combo: {best_combo} ({top_lift})` and `health.universe` as `rd-note`. Right = the chart (`CHART_LABEL`, `CHART_NOTE`). With `summary === null`: `EmptyState("No momentum simulation is saved", "momentum_edge_equity.csv is missing or unreadable.")` replaces the big value and the chart; the trade stats still show.
5. `SectionHead(SETUPS_TITLE, SETUPS_META)` + `Segmented(tabLabels)` + an "All columns" toggle. Then `div.desk-split`: the table, and `div.desk-rail` with `StockRail`.
   - Compact columns: Company (name, p1: title company, sub `"{symbol} · NSE"`, or `"NSE"` when company equals symbol), Signal (pill, p1, tone gain/warn/info/muted for Breakout Today/Near Breakout/Watch Zone/other), Price (num, p2), From high (num `ChangePill(dist_ath)`, p1), Stop (num, p2, `stop_pct`), Breaks (text, p3, entry type), Volume (num, p2, `vol_ratio`), Score (num, p1, default sort descending). "All columns" adds Action, ATH (₹), Chart quality, Choppiness, Recovery, 220 EMA, 52W High, vs High%, Stop (₹), Hist Win% and Hist Avg%.
   - Recent tab: columns Stock, Days ago, Breakout date, Breakout price, Close, % off breakout, 220 EMA, Volume, Stop, with `RECENT_NOTE` above.
   - `HIST_NOTE` under the table. With no signals: `EMPTY_NO_SIGNALS`.
   - Rail: `"{symbol} · NSE"`, company, price + signal pill, `RailChart` + "Closing price · last 90 sessions (saved to …)", `SectionHead("Why it is on the list", "{passed} of 7 pass")`, then the conditions as a check list (title from `conditionTitle`, sub = Streamlit label · detail) or `EmptyState(note)`. Then the rows Suggested stop / Earlier trades like this (`won {hist_win} · avg {hist_avg}`, or `—`) / Past model trades in {symbol}, then `OLD_APP_LINK` (opens `STREAMLIT_URL` in a new tab). Selection works as on Monthly (`replaceState ?ticker=`, scroll the rail into view under 1200px).
6. `SectionHead(FUNNEL_TITLE(total), FUNNEL_NOTE)` + `Funnel` (bar width = count / total; the final step uses the gain tone if `is_bull`, else loss, as `_chart_me_funnel`). Hidden when `funnel` is null.
7. `Tabs`. "Past trades (N)" = `Segmented(["Last 1Y","Last 3Y","All","Pick year"])` + a year `select` (only for Pick year) + a "Clean signals only" toggle + `tradesCaption` + `DeskTable` (Stock p1 [sub entry type], Bought p1, At p2, Prior 52W high p3, BK margin p3, Sold p1, At p2, Result pill p1, Held p2, Why sold p1, Filters p3, Recovery p3) + `TRADES_LEGEND`. "How the model exits" = `EXIT_RULES` + `BUY_NOW_NOTE` + `ExitResearch({rec, title:"Exit research: Price strength (Momentum)"})`. "What each column means" = `HOW_TO_READ` + the `COLUMN_GUIDE` table.
8. `ResearchNotice`, `GlossaryDisclosure`.

- [ ] **Step 1: Failing nav test.** Run it, expect FAIL (`external: true`).
- [ ] **Step 2: Implement** the page and components, and flip the nav href.
- [ ] **Step 3: Verify.** Web tests, `npx tsc --noEmit` and `npm run lint` (no new problems). With `npm run dev` (check free memory first), `/momentum`, `/momentum?ticker=TITAN` and `/momentum?ticker=ADANIPORTS` (recent-only) render with no console errors. Switching to "All-time high only" changes the setups count, the trade stats and the past trades, and leaves the CAGR and chart unchanged.
- [ ] **Step 4: Number check against Streamlit** (port 8500, only if the user agrees to start it). The CAGR, worst drawdown, win rate, trade count, first 5 setup rows and newest 5 trades match. Save `C:/Users/User/Documents/Stocks/.superpowers/audit/next-momentum-step4-{next,streamlit}.png`.
- [ ] **Step 5: Commit** `feat(web): Price strength (Momentum) page in the Research Desk style`

### Task 6: Fit audit, visual QA, handoff

**Files:**
- Modify: `web/tests/fit/fit-audit.js`: `PAGES = ["/", "/monthly", "/momentum"]`; apply the two Monthly rail checks (the rail bottom is reachable; a row tap at 390×844 brings the rail into view) to `/momentum` too.
- Modify: `MEMORY.md` (project): Momentum built, its commits, and the next page (IPO, mockup first).

- [ ] **Step 1: Run the audit** via Playwright MCP against `npm run dev`. Expected: `ALL PASS` for all three pages at the 5 viewports. Fix layout in CSS only, then rerun.
- [ ] **Step 2: Visual QA** at 1280×600 and 390×844, light and dark. Save `C:/Users/User/Documents/Stocks/.superpowers/audit/next-momentum-{1280,390}-{light,dark}.png` and compare with the mockup screenshot.
- [ ] **Step 3: Full verification.** Python suite (290 + new, all passing; real exit code), web suite with `PYTHON_BIN`, `tsc`, lint, and `verify_protected.py` (no function or file drift beyond the known KPI drift).
- [ ] **Step 4: Commit** `test(web): fit audit covers the Momentum page` and the `MEMORY.md` update. Show the screenshots to the user for approval.
