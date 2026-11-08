# Desk feedback round 1: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix four gaps the user reported on 2026-11-08 after seeing `/monthly` and `/momentum`:
1. Price strength lost Streamlit's multi-panel indicator chart (candles, volume, RSI, MACD, Bollinger, OBV, reading badges).
2. There is no update button on each page.
3. Monthly does not say plainly which 5 stocks the model picks this month.
4. The success rate, how long to hold and when to sell are hidden in a tab.

User's words: "in price strength, in stream lit we had graph which had volume indicator and rest of them which is not visible in present version, update button also is not present for each page and in montly rotation top 5 to buy is not mentioned, the success rate and with no loss how much time to retain and when to sell is not mentioned as we want no loss and 100 percent profit".

**Architecture:** Two shared desk components (`PageUpdateButton`, `HoldExitCard`) are used by every strategy page. A Monthly "top 5" card is built from the already-saved `ui_monthly.json`. For the indicator chart, a new Python script `precompute_ui_momentum_charts.py` runs Streamlit's own `_render_me_detail` with a recorder in place of `md.st` and `md._plot` (the same technique `precompute_ui_momentum.py` uses for `_render_criteria_panel`) and writes one JSON per stock. A read-only API route serves one stock's file, and a client component draws it with `lightweight-charts` v5 panes.

**Tech Stack:** Python 3 + pandas + plotly (existing), Next.js 16.2.7, React, TypeScript, Vitest, `lightweight-charts` 5.2.0 (installed; has panes), Playwright MCP.

**Spec:** `docs/superpowers/specs/2026-11-07-nextjs-research-desk-design.md`. Prior plan: `2026-11-08-nextjs-desk-momentum.md`, whose Decision 2 sent the indicator chart to the old app; this plan reverses that. No mockup (user, 2026-11-08).

## Decisions (Claude's calls)

1. **Honesty about "no loss and 100 percent profit".** No saved strategy is loss-free. The Hold and exit card shows the historical numbers with the sample size and the line `HONESTY_NOTE(lossPct)`: "Past results, not a promise. At the suggested hold, {lossPct}% of past trades still lost money." It never says "no loss", "guaranteed" or "100%".
2. **The Hold and exit card** sits near the top of each strategy page, after the context bar. It replaces the Exit research blocks inside the lower tabs: the Monthly "Exit research" tab goes, and the Momentum "How the model exits" tab keeps only the rules text. Its contents come from the saved `exit_rec` (`_pick_rec`):
   - suggested hold (`hold_days`)
   - success rate at that hold (`hold_win_rate`)
   - median return at that hold
   - profit targets T1–T3 (target %, % of position to sell, historical hit rate)
   - stop level
   - sample size, with a small-sample warning under 30 (as `ui.kpi`)
   - data quality
   - the return-by-days-held curve, in a disclosure

   Momentum also shows "Stayed above entry 20+ days" (`health.safe_20d_pct`) and "Trades in profit at exit" (`health.win_rate` of `n_trades`).
3. **Update button.** A `PageUpdateButton` in each strategy page header ("Update Monthly data", "Update Momentum data", "Update IPO data") runs the same `/api/update` job for that strategy as the sidebar "Update one strategy". It shows the same progress lines and result, and refreshes the page on success.
4. **Monthly top 5 card.** "Model's top 5 for this month" lists rank, company, price, month move and RS score from `ui_monthly.json` `top5` + `ranking`, placed above the summary card. Sub-line: "The stocks the model would hold this month. A model list, not an instruction." Clicking a row selects it in the ranking desk (same `?ticker=` behaviour).
5. **Indicator chart.** Full width, under the Today's setups table, for the selected stock.
   - Periods 1M/3M/6M/1Y/3Y, default 1Y as in Streamlit. "All" is not offered: files hold the last 3 years (756 sessions) to keep their size down.
   - Toggles: Bollinger, RSI(14), MACD, Volume + OBV, all on by default as in Streamlit.
   - Reading badges (RSI, MACD hist, ADX, ATR, OBV 20d + BB width) and the "Since all conditions met" line, all as Streamlit wrote them.
   - BUY / EXIT markers from past trades, and the breakout marker.
   - The rail's old-app link becomes "Single-stock backtest: open in the old app", because the backtest button still lives only in Streamlit.

## Global Constraints

- Branch `redesign/nextjs-desk`. Commit after every task (conventional commits, ending with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`).
- No new npm or pip packages.
- Numbers come from Python only. The chart script must not compute indicators itself; it captures what `_render_me_detail` draws (plotly traces, hlines, vlines, markers, badges, caption) via the recorder. TS only maps saved series to chart series and slices by period.
- `master_dashboard.py`: only `_PRECOMPUTE_FOR` (+ its comment) may change. The protected-files rule applies as before; `run_all.py` drift is reported, not re-baselined.
- API route: GET only. `symbol` must match `^[A-Z0-9&.\-]{1,20}$`. The file path is built from a fixed folder (`DATA_DIR/ui_momentum_charts/`), with no path traversal. Missing files return 404 JSON. Responses carry `Cache-Control: no-store`.
- Layout: 1280×600 first, then 1280×560, 1024×700, 1920×1000 and 390×844. No horizontal page scroll; no inner scroll boxes in default views.
- Tests: Python baseline 315; web baseline 327 (after IPO Task 3). `tsc` clean; lint adds nothing to the existing 2 errors + 3 warnings.

## Review Focus

1. **Stock with no chart file** (or a file from an older run). Expectation: the chart area shows an empty state and the rest of the page works. Pinned in Task 4.
2. **Symbol with `&` or `-`** (M&M, BAJAJ-AUTO) and a malicious symbol (`../x`). Expectation: served or rejected correctly. Pinned in the Task 4 route tests.
3. **Update already running** (409 from `/api/update`). Expectation: the page button shows the same "busy" message as the sidebar, and both buttons are disabled while one job runs. Pinned in Task 1.
4. **No exit_rec saved.** Expectation: the Hold and exit card shows Streamlit's empty text ("Exit Playbook: insufficient trade history to recommend a hold/exit plan yet."). Pinned in Task 2.
5. **Theme switch** while the indicator chart is open. Expectation: colours follow light/dark. Checked in the Task 5 screenshots.

---

### Task 1: Shared page update button

**Files:**
- Create `web/lib/desk/use-strategy-update.ts`: a client hook extracted from `web/components/desk/update-panel.tsx`, `useStrategyUpdate(): { running, lines, results, error, start(strategy: "all" | UpdateStrategy) }`. It shares one module-level "running" flag, so the sidebar and page buttons disable each other.
- Create `web/components/desk/page-update-button.tsx`: `PageUpdateButton({ strategy, label })`, a button plus a compact progress/result block under the page header, reusing `errorHeadline` and the result wording of `UpdatePanel`.
- Modify `update-panel.tsx` to use the hook (no visible change).
- Add the button to the `PageHeader` right side on `/monthly` and `/momentum`.

Tests: `web/tests/desk-update-button.test.ts` covers the hook's start/409/result paths with a mocked `runJobStream`, plus a render test that the button label and disabled state follow `running`.

Commit `feat(web): update button on each strategy page`.

### Task 2: Hold and exit card + Monthly top 5 card

**Files:**
- Create `web/components/desk/hold-exit-card.tsx`: `HoldExitCard({ rec, title, extra?: {label, value, sub?}[] })`.
- Add text helpers to `web/lib/desk/exit-text.ts`: `holdExitRows(rec)`, `HONESTY_NOTE(lossPct)`, `SMALL_SAMPLE_NOTE`. Reuse `exitTexts`, `ExitCurveChart` (move it to `web/components/desk/exit-curve-chart.tsx`) and `DeskTable` for the targets.
- Create `web/components/desk/monthly/top5-card.tsx`: `Top5Card({ ranking, top5, onSelect })`.

Placement:
- `/monthly`: Top5Card, then HoldExitCard ("Hold and exit plan: Monthly stock rotation"), then the summary card. Remove the Exit research tab from Monthly's lower tabs.
- `/momentum`: HoldExitCard after the switch row, with `extra` = Trades in profit at exit (`health.win_rate` of `n_trades`, current view) and Stayed above entry 20+ days (`health.safe_20d_pct`). The "How the model exits" tab keeps `EXIT_RULES` + `BUY_NOW_NOTE` only.

Exact rows, in order:
- Suggested hold: `${hold_days} days`
- Success rate at that hold: `${hold_win_rate*100:.0f}%`
- Median return at that hold: `{:+.1f}%`
- Sell plan: targets table with Tier, Sell at `+{pct:.1f}%`, Sell this much `${book_pct}%`, Hit before (hist.) `{hit_rate*100:.0f}%`
- Stop level: `{stop_pct:.1f}%`
- Based on `${sample_size} past trades`, plus the small-sample warning under 30
- `HONESTY_NOTE(round((1-hold_win_rate)*100))`

Tests:
- Unit tests for `holdExitRows` against the Momentum saved rec, using its exact saved values (`65 days`, `81%`, …).
- Unit test for `HONESTY_NOTE(19)`.
- Render tests: HoldExitCard with a null rec shows Streamlit's empty text; Top5Card shows 5 rows in rank order.
- Update `desk-monthly-page.test.ts` and the Momentum render tests for the removed tab content.

Commit `feat(web): hold and exit plan card and Monthly top 5 card`.

### Task 3: `precompute_ui_momentum_charts.py`

**Files:**
- Create `precompute_ui_momentum_charts.py` and the test `tests/test_precompute_ui_momentum_charts.py`.
- `.gitignore` adds `ui_momentum_charts/`.
- Update paths: append the script last in `_PRECOMPUTE_FOR['Momentum']`, in `run_all.py` (after `precompute_ui_ipo.py`), in `refresh_data.bat` (new step, renumber) and in `web/lib/desk/update-steps.ts`, and extend `tests/test_streamlit_updates_moved.py`.

Behaviour:
- For each symbol in `ui_momentum.json` `details` (signals ∪ recent breakouts), call `md._render_me_detail(symbol, trades)` with:
  - `md.st` replaced by a recorder: `columns(spec)` → nullcontexts; `radio(label, options, index, ...)` → `'3Y'`; `checkbox(..., value)` → `True`; `markdown`, `caption`, `info` and `metric` recorded.
  - `md._plot` replaced by a capturer.
  - Both restored in `finally`.
- Convert the captured plotly figure:
  - Each trace becomes `{name, type: candlestick|line|bar|markers, row, colour, dash, points}`, with candles as `[date, o, h, l, c]`.
  - Each shape becomes `{kind: hline|vline, row, value, colour, dash, label}`.
  - Badges are parsed from the `_indicator_badge` markdown (`label, value, sub`).
  - The "Since all conditions met" line is kept as text.
  - When there is no figure, the `st.info` text becomes `note`.
- Write `ui_momentum_charts/{SYMBOL}.json` atomically, as `{version:1, symbol, generated_at, rows: ["price","rsi","macd","volume"], traces, shapes, badges, since_line, note}`.
- Write `ui_momentum_charts/index.json` (`{version:1, symbols:[...]}`), and delete stale files for symbols no longer listed.
- Print `wrote N chart files (X MB)`. Target: under 25 MB total and under 120 s.

Tests:
- A synthetic 800-row OHLCV under a monkeypatched `md.BASE_DIR` gives 4 rows, a candlestick trace with ≤ 756 points, RSI hlines at 70/30/50, and 5 badges.
- A missing file gives `note` set and no traces.
- `md.st` and `md._plot` are restored after an exception.
- The index lists the written symbols, and a stale file is removed.

Commit `feat(data): save Streamlit's Momentum indicator chart per stock for the desk`.

### Task 4: Chart API route + indicator chart component

**Files:**
- `web/app/api/desk/momentum-chart/route.ts`: GET `?symbol=`, validated per Global Constraints. It reads through a small loader in `web/lib/desk/momentum-chart.ts` built on `versioned-json.ts`.
- `web/components/desk/momentum/indicator-chart.tsx`: a client component. It fetches on selection change and aborts the previous fetch. It uses `lightweight-charts` v5 panes:
  - price pane: candles, SMA50, SMA150, EMA220, Bollinger lines, 52W hi/lo price lines with labels, and BUY/EXIT/Breakout markers
  - RSI pane: 70/30/50 lines
  - MACD pane: histogram + lines + 0 line
  - Volume pane: histogram + OBV line

  It also has a period `Segmented` (1M/3M/6M/1Y/3Y, default 1Y) that slices the last 21/63/126/252/756 sessions (Streamlit `_PERIOD_BARS`), the four toggles, the badges row, the since-line, and an empty state from `note` or a 404.
- Place it full width under the setups table in `setups-desk.tsx`, with `SectionHead("Price chart and indicators", "{symbol} · candles, averages, volume, RSI, MACD")`.
- Change the rail link text to "Single-stock backtest: open in the old app".

Tests:
- Route tests: a valid symbol including `M&M`, invalid `../x` → 400, missing → 404, and the no-store header.
- Pure mapper tests for period slicing and trace→series mapping.
- A render test of the empty state.

Commit `feat(web): Streamlit indicator chart on the Momentum page`.

### Task 5: Fit audit, screenshots, handoff

- Fit audit ALL PASS for `/`, `/monthly` and `/momentum` at the 5 viewports. The indicator chart must not cause horizontal scroll.
- Screenshots: `C:/Users/User/Documents/Stocks/.superpowers/audit/next-feedback1-{monthly,momentum}-1280-{light,dark}.png` and `-390-light.png`.
- Full verification: pytest, vitest with PYTHON_BIN, tsc, lint, and verify_protected (only `run_all.py` drift expected).
- Update `MEMORY.md` (git-ignored, on disk): feedback round 1 done, its commits, and that IPO Tasks 4–5 resume next using `PageUpdateButton` and `HoldExitCard`.
- Commit `test(web): fit audit after desk feedback round 1`.
