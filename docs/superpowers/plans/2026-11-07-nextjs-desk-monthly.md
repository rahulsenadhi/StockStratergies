# Monthly stock rotation (Next.js desk) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the "Monthly stock rotation" page in the Next.js desk (`web/`, route `/monthly`). It has the same sections, order, text and numbers as Streamlit's `render_monthly`, in the approved v2 look.

**Architecture:** A new Python save-results script `precompute_ui_monthly.py` calls the same `master_dashboard.py` functions that `render_monthly` uses and writes `ui_monthly.json`. A server loader in `web/lib/desk/monthly.ts` reads that file and never throws. Pure mappers in the same file turn saved numbers into Streamlit's exact display strings. Desk components under `web/components/desk/monthly/` draw the page. The script joins every update path that already runs `precompute_ui_home.py` for Monthly, IPO and Momentum.

**Tech Stack:** Python 3 + pandas (existing `.venv`), Next.js 16.2.7 App Router, React, TypeScript, Vitest, `lightweight-charts` (already installed), Playwright MCP for the fit audit.

**Spec:** `docs/superpowers/specs/2026-11-07-nextjs-research-desk-design.md` (§7.3 row 2, §7.4, §7.5, §8). Content source: `master_dashboard.py` `render_monthly` and helpers (lines ~6289–6593). The recipe and rulings are in `MEMORY.md` → "Next.js desk notes".

## Global Constraints

- Branch `redesign/nextjs-desk`. Commit after every task (conventional commits, attribution line from the session).
- No new npm or pip packages. Charts use `lightweight-charts`.
- Every number is computed in Python. TypeScript only formats saved numbers, and never re-implements a formula, filter rule or rebasing.
- Display text is verbatim from `render_monthly` and its helpers. One exception: "Use “Refresh data → Monthly” in the sidebar" becomes "Use “Update one strategy → Monthly” in the sidebar", because that is the Next.js sidebar control.
- Python format strings map one to one: `{:+.1f}%`, `{:+.2f}%`, `{:.1f}%`, `₹{:,.2f}`, `₹{:,.0f}`; `change_pill` → `ChangePill`; `status_pill` → `StatusPill`.
- Do not edit protected functions or files (`.superpowers/baseline/verify_protected.py`). The only `master_dashboard.py` edit allowed is the `_PRECOMPUTE_FOR` dict (approved).
- If a Streamlit number looks wrong, stop and report it. Do not copy or fix it.
- Layout: design at 1280×600 first, then check 1280×560, 1024×700, 1920×1000 and 390×844. No horizontal page scroll. No inner scroll boxes. Tables show 15 rows plus "Show all N rows". Every table sorts. The detail rail stacks below the list under 1200px.
- Next 16: read `web/node_modules/next/dist/docs/` for page `searchParams` (it is a Promise) before writing the route. Client components must not import modules that use `node:fs`.
- Test commands. Python: `.venv/Scripts/python.exe -m pytest tests -q -p no:cacheprovider` (baseline 274 passed). Web, from `web/`: `PYTHON_BIN=../.venv/Scripts/python.exe npx vitest run --exclude tests/glossary.test.ts` (baseline 256 passed; `glossary.test.ts` already failed before this work). Typecheck: `npx tsc --noEmit`. Lint: `npm run lint`.

## Review Focus

1. **Rail taller than the screen at 1280×600.** The detail rail (about 800px) must not stick in a way that hides its bottom. Expectation: the rail is sticky only at `min-width:1200px and min-height:900px`, and otherwise scrolls with the page. Pinned by the fit-audit check in Task 6.
2. **`?ticker=` from Home.** Home sends `HAL`, `M&M` or `BAJAJ-AUTO` without `.NS`. An unknown ticker must not crash the page. Expectation: a match selects that row; anything else falls back to Streamlit's default, the first saved row. Pinned in Task 3 `resolveSelected` tests.
3. **Selected stock hidden by a filter** (for example "Lagging Nifty" while rank 1 is selected). Expectation: the detail rail keeps the selected stock, as Streamlit does, and only the table changes. Pinned in Task 3 `resolveSelected` tests: the function uses the full ranking, never the filtered list.
4. **Partial saved data.** Possible gaps: no `backtest_results.csv`, no `Benchmark_Value` column, a missing `data/{T}.csv`, no exit recommendation, an empty rebalance log, or a NaN in `Benchmark_Return_%`. Expectation: each section shows its own empty state or "—", and the rest of the page renders. Pinned in the Task 1 Python tests and the Task 3 loader tests.
5. **Phone row tap.** Below 1200px the detail panel sits under a 15-row list, so a tap seems to do nothing. Expectation: after a tap, the detail panel scrolls into view. Pinned by the 390px fit-audit check in Task 6.

---

### Task 1: `precompute_ui_monthly.py` writes `ui_monthly.json`

**Files:**
- Create: `precompute_ui_monthly.py`
- Test: `tests/test_precompute_ui_monthly.py` (follow `tests/test_precompute_ui_home.py`: load `md` from `tests.test_modern_table`, put it in `sys.modules['master_dashboard']`, then import the script)

**Interfaces:**
- Consumes (all existing, from `master_dashboard`): `load_monthly()`, `_equity_metrics(eq, col, col)`, `_monthly_period_slice(eq, window)`, `chart_equity(eq, 'Portfolio_Value', S_MONTHLY, colour, 'Benchmark_Value')`, `_monthly_filter(ranks, choice)`, `_MONTHLY_FILTERS`, `_monthly_label(signal)`, `_monthly_tickers(value)`, `_monthly_close_history(ticker)`, `_pick_rec('monthly_rotation')`, `MONTHLY_CHECKS`, `ui.CHECK_STATUS`, `THEME[S_MONTHLY]['color']`. Reuse `_clean` and `write_snapshot` by importing them from `precompute_ui_home` (DRY).
- Produces: `build_ui_monthly(m: dict) -> dict`, `main() -> None`, and constants `OUT = BASE_DIR / 'ui_monthly.json'`, `MONTHLY_VERSION = 1`. JSON schema v1, consumed by Task 3:

```text
{ version: 1, generated_at: "YYYY-MM-DDTHH:MM:SS", colour: "#7c9cff",
  summary: null | { cagr, total_ret, max_dd, start, end,          # _equity_metrics(eq,'Portfolio_Value','Portfolio_Value')
                    bench_ret, bench_cagr,                          # _equity_metrics(eq,'Benchmark_Value','Benchmark_Value'); 0.0/0.0 when column absent (Streamlit default)
                    alpha,                                          # cagr - bench_cagr
                    n_months: int | null },                         # len(rebalance) or null
  chart: null | { "1Y"|"3Y"|"All": [ { name, colour, dash: bool, points: [["YYYY-MM-DD", pct], ...] } ] },  # traces of chart_equity(...) on the window slice
  ranking: [ { rank: int, ticker: "HAL.NS", symbol: "HAL", company, price, month_ret, bench_ret: number|null, rs, label } ],  # sorted by Rank (stable)
  filters: { "All 50"|"Top 5"|"Beating Nifty"|"Lagging Nifty": [symbol, ...] },   # _monthly_filter on the Rank-sorted frame
  default_symbol: string | null,                                    # symbol of ranks.iloc[0] (file order), Streamlit's default selection
  top5: [symbol, ...],                                              # ranks.sort_values('Rank').head(5)
  closes: { symbol: { saved_to: "06 Nov 2026", points: [["YYYY-MM-DD", close], ...] } },  # last 126 of _monthly_close_history; key absent when None/empty
  rebalances: { total: int, rows: [ { date: "YYYY-MM-DD", top5, bought, sold, value } ] },  # reb.tail(12).iloc[::-1]; ticker cells via _monthly_tickers
  checks: [ { title, label, tone, note } ],                         # MONTHLY_CHECKS + CHECK_STATUS
  exit_rec: null | { ...the dict _pick_rec returns, unchanged } }
```

- [ ] **Step 1: Write the failing tests** in `tests/test_precompute_ui_monthly.py` with a fixture `m`: 3 ranking rows (one with NaN `Benchmark_Return_%` and a `🟢 Strong BUY` signal), a 40-row month-end equity frame with `Portfolio_Value` and `Benchmark_Value`, and a 3-row rebalance frame.
  - `test_summary_uses_equity_metrics`: `out['summary']['cagr'] == md._equity_metrics(eq,'Portfolio_Value','Portfolio_Value')['cagr']`, and the same for `total_ret` and `max_dd`.
  - `test_benchmark_matches_render_monthly_inline_formula`: compute `b_ret` and `b_cagr` with `render_monthly`'s inline lines (copy them into the test, with a comment naming the source line) and assert `pytest.approx` equal to `bench_ret` and `bench_cagr`. Also assert `alpha == cagr - bench_cagr`.
  - `test_no_benchmark_column_gives_streamlit_zero`: drop `Benchmark_Value`; then `bench_ret == 0.0`, `bench_cagr == 0.0`, and each `chart[w]` list has 1 trace.
  - `test_no_equity`: `m` without `'equity'` gives `summary is None` and `chart is None`, and `ranking` is still filled.
  - `test_ranking_rows_and_filters`: assert `[r['symbol'] for r in out['ranking']]` is in rank order. Assert `label == 'Strong BUY'`, the NaN benchmark becomes `None` after `_clean`, and `out['filters'][f] == [t.replace('.NS','') for t in md._monthly_filter(sorted_ranks, f)['Ticker']]` for every `f` in `md._MONTHLY_FILTERS`.
  - `test_chart_traces_match_chart_equity`: for `'3Y'`, the trace names, colours and y values equal `md.chart_equity(md._monthly_period_slice(eq,'3Y'), ...)`'s `fig.data`. The benchmark trace has `dash is True`.
  - `test_closes_last_126_and_missing_file`: monkeypatch `md._monthly_close_history` to return a 200-point series for `AAA.NS` and `None` for the others. Then `len(closes['AAA']['points']) == 126`, `closes['AAA']['saved_to']` uses `%d %b %Y`, and `'BBB' not in closes`.
  - `test_rebalances_latest_12_newest_first`: with 14 rows, `total == 14`, `len(rows) == 12`, `rows[0]['date']` is the latest, and `rows[0]['top5'] == md._monthly_tickers(...)`.
  - `test_checks_and_exit_rec`: `[c['label'] for c in out['checks']]` equals the `CHECK_STATUS` labels for `MONTHLY_CHECKS`. With `md._pick_rec` monkeypatched to `None`, `exit_rec is None`.
  - `test_main_writes_atomic_json`: monkeypatch `OUT` to `tmp_path`, run `main()`, `json.loads` the file, and assert `version == 1` and that no `.json.tmp` file is left.

- [ ] **Step 2: Run, expect FAIL** (`ModuleNotFoundError: precompute_ui_monthly`)
  Run: `.venv/Scripts/python.exe -m pytest tests/test_precompute_ui_monthly.py -q -p no:cacheprovider`

- [ ] **Step 3: Implement `build_ui_monthly(m: dict) -> dict` and `main()`** in `precompute_ui_monthly.py`. Copy the docstring style of `precompute_ui_home.py` ("No formulas live here — this only collects and saves"). Read chart traces from the figure the same way `precompute_ui_home._growth` does (`trace.name`, `trace.line.color`, `trace.line.dash == 'dot'`, x→`%Y-%m-%d`). `main()` calls `build_ui_monthly(md.load_monthly())` and `write_snapshot(..., OUT)`, then prints `wrote ui_monthly.json: N ranked`.

- [ ] **Step 4: Run, expect PASS.** Then run the real script once: `.venv/Scripts/python.exe precompute_ui_monthly.py`. Expected: `wrote ui_monthly.json: 50 ranked`. Then check that `.gitignore` ignores `ui_monthly.json` (`git check-ignore ui_monthly.json`); if it does not, add the file next to the `ui_snapshot.json` entry.

- [ ] **Step 5: Commit** `feat(data): precompute_ui_monthly writes ui_monthly.json for the Next.js desk`

### Task 2: Run the script in every update path

**Files:**
- Modify: `master_dashboard.py` `_PRECOMPUTE_FOR` (~line 4860): insert `'precompute_ui_monthly.py'` before `'precompute_ui_home.py'` in **Monthly, IPO and Momentum**. IPO and Momentum run `precompute_exit_recommendations.py`, which rewrites the monthly exit research. PEAD has no Monthly data.
- Modify: `run_all.py` `PRECOMPUTE` list: add the script before `precompute_ui_home.py` with the comment `# ui_monthly.json (Next.js Monthly)`.
- Modify: `refresh_data.bat`: add a step before the Home step in the same pattern (echo, run, `if errorlevel 1` with `!! precompute_ui_monthly.py FAILED`, else `ok ui_monthly.json done`). Renumber the `[n/N]` labels.
- Modify: `web/lib/desk/update-steps.ts` `UPDATE_STEPS` to mirror the change.
- Test: `tests/test_streamlit_updates_moved.py::test_step_lists_still_defined_for_the_web_app`, and the existing web parity test `web/tests/desk-update.test.ts`.

**Interfaces:** Consumes Task 1's script name. Produces nothing new.

- [ ] **Step 1: Failing test.** Extend `test_step_lists_still_defined_for_the_web_app`:
  `assert all(v.index('precompute_ui_monthly.py') == v.index('precompute_ui_home.py') - 1 for k, v in md._PRECOMPUTE_FOR.items() if k != 'PEAD')` and `assert 'precompute_ui_monthly.py' not in md._PRECOMPUTE_FOR['PEAD']`.
- [ ] **Step 2: Run, expect FAIL** (`ValueError: 'precompute_ui_monthly.py' is not in list`).
- [ ] **Step 3: Edit the four files** as listed above.
- [ ] **Step 4: Verify.** The Python test passes. `PYTHON_BIN=../.venv/Scripts/python.exe npx vitest run tests/desk-update.test.ts` passes, because the parity test compares against Python. `verify_protected.py` reports no new function drift; the known KPI drift from today's data refresh is expected.
- [ ] **Step 5: Commit** `feat: run precompute_ui_monthly in every Monthly/IPO/Momentum update path`

### Task 3: Loader and display mappers (`web/lib/desk/monthly.ts`)

**Files:**
- Create: `web/lib/desk/monthly.ts` (server loader + pure mappers + copy constants; the loader is the only `node:fs` user — if a client component needs mappers, split pure parts into `web/lib/desk/monthly-text.ts` with no `node:fs` import)
- Modify: `web/lib/desk/format.ts` — add `formatSigned(value: number, decimals: number): string` (Python `f"{v:+.{d}f}"`, no `%`) and `formatRupees(value: number, decimals: number): string` (`₹` + `formatNumber`)
- Test: `web/tests/desk-monthly.test.ts`, `web/tests/parity/monthly_streamlit_text.py` (Python harness, run with cwd = project root)

**Interfaces:**
- Consumes: `ui_monthly.json` (Task 1 schema), `formatNumber`, `formatChange`, `freshnessLabel`, `freshnessTone`, `Tone` from `format.ts`.
- Produces (used by Tasks 4–5):
  - Types `UiMonthly`, `MonthlySummary`, `ChartTrace`, `RankRow`, `CloseSeries`, `RebalanceRow`, `CheckRow`, `ExitRec` (fields exactly as the Task 1 schema; `ChartWindow = "1Y" | "3Y" | "All"`; `MonthlyFilter = "All 50" | "Top 5" | "Beating Nifty" | "Lagging Nifty"`, `MONTHLY_FILTERS` in that order).
  - `loadMonthly(dataDir?: string): Promise<{ ok: true; data: UiMonthly } | { ok: false; reason: "missing" | "invalid" | "version" }>`, with the same contract as `loadSnapshot`.
  - `resolveSelected(ranking: RankRow[], defaultSymbol: string | null, requested?: string | null): string | null`. It strips a trailing `.NS`, matches `symbol` exactly, and falls back to `defaultSymbol`, then to `ranking[0]?.symbol`, then to `null`. It searches the full ranking, never a filtered list.
  - `summaryStats(s: MonthlySummary): { label: string; value: string; tone: Tone }[]`, which returns `_render_monthly_summary`'s five `stat_bar` rows in order. The "Sample" row shows `${n} monthly rebalances` or `—`.
  - `cagrText(s) -> string` (`formatSigned(cagr,1)+"%"`), `cagrTone(s) -> Tone`, `benchSub(s) -> string` (`vs Nifty ${formatSigned(bench_cagr,1)}% per year, same period`), `bigValueParts(text) -> { head: string; dec: string | null }` (Python `big_value` split at the first `.`).
  - `rankSub(r) -> string` (`HAL · top 5 candidate` when rank ≤ 5, otherwise `HAL`), `rankStatus(r, total) -> { label; tone }`.
  - `rankingAge(ageDays: number | null) -> { label; tone }`, which returns `"Ranking " + freshnessLabel` with `freshnessTone`.
  - `exitTexts(rec: ExitRec)`, which returns `{ hold, median, winRate, targets: {tier, target, book, hit}[], caption }` with `_exit_playbook_card`'s strings.
  - Copy constants: `MONTHLY_TITLE`, `MONTHLY_SUB`, `CHART_NOTE`, `RANKING_NOTE`, `REBALANCE_NOTE(total)`, `HOW_IT_WORKS`, `HOW_TO_READ_TITLE`, `HOW_TO_READ`, `FOOTER_CAPTION`, `EXIT_CAPTION`, and the empty-state titles and reasons, all verbatim from `render_monthly`'s helpers (see Global Constraints for the one rewording). `HOW_IT_WORKS` keeps its `<b>` parts as structured segments (`{ text, bold }[]`), not HTML strings.

- [ ] **Step 1: Failing unit tests** in `web/tests/desk-monthly.test.ts`:
  - `formatSigned(20.94, 1) === "+20.9"`, `formatSigned(-4.93, 2) === "-4.93"`, `formatRupees(1087.75, 2) === "₹1,087.75"`, `formatRupees(91013.4, 0) === "₹91,013"`.
  - `resolveSelected`: `(rows, "BAJFINANCE", "HAL") === "HAL"`; `"HAL.NS"` gives `"HAL"`; `"M&M"` and `"BAJAJ-AUTO"` match; `"ZZZ"`, `""` and `null` give `"BAJFINANCE"`; `([], null, "HAL") === null`.
  - `summaryStats` for `{cagr:20.94,total_ret:79.8,max_dd:-12.34,bench_ret:26.1,bench_cagr:8.0,alpha:12.94,n_months:36}` deep-equals `[["Extra vs Nifty","+12.9% / yr","gain"],["Total return","+79.8%","info"],["Nifty total","+26.1%","muted"],["Worst fall from a peak","-12.3%","loss"],["Sample","36 monthly rebalances","muted"]]` (as objects). With `n_months: null` the Sample value is `"—"`. A negative alpha gives tone `"loss"`.
  - `bigValueParts("+20.9%")` gives `{head:"+20", dec:".9%"}`; `bigValueParts("—")` gives `{head:"—", dec:null}`.
  - `rankSub` / `rankStatus` for rank 3 and rank 12 of 50: `"Top-5 candidate"/"info"` and `"Rank 12 of 50"/"muted"`.
  - `exitTexts` on the sample `{hold_days:2, hold_median_return:0.44, hold_win_rate:0.56, targets:[{pct:7.6,book_pct:40,hit_rate:0.6}], stop_pct:-12.8, sample_size:152, data_quality:"close"}`: `hold "2 days"`, `median "0.4%"`, `winRate "56%"`, `targets[0]` = `{tier:"T1", target:"+7.6%", book:"40%", hit:"60%"}`, and `caption` contains `"-12.8%"`, `"152 trades"` and `"close-only (approx.)"`.
  - `loadMonthly` on a temp dir: a missing file gives `missing`; `"{"` gives `invalid`; `{"version":2}` gives `version`; a minimal valid v1 file with `summary:null, chart:null, exit_rec:null, closes:{}` gives `ok`.
- [ ] **Step 2: Run, expect FAIL** (module not found). From `web/`: `npx vitest run tests/desk-monthly.test.ts`.
- [ ] **Step 3: Implement** `format.ts` additions and `monthly.ts`.
- [ ] **Step 4: Parity test (`describe.skipIf(!PYTHON_BIN)`)** in the same file. Pattern: `tests/desk-home.test.ts`. Run `precompute_ui_monthly.py`, then `web/tests/parity/monthly_streamlit_text.py`. The harness prints JSON with Streamlit's own strings for the current files: per ranking row `[rank, company, sub, price, move-pill text, rs text, label]` exactly as `_render_monthly_ranking` builds them (HTML stripped). It also prints `big_value` text, the five `stat_bar` values, and per rebalance row `[date, top5, bought, sold, value text]`. The benchmark values use `render_monthly`'s inline formula; this is the gap the spec asks to list, so name it in a comment. Assert that the TS mappers applied to the loaded `ui_monthly.json` produce equal arrays.
- [ ] **Step 5: Run all web tests + `npx tsc --noEmit`, expect PASS. Commit** `feat(web): Monthly loader and display text with Streamlit parity test`

### Task 4: Shared v2 pieces the Monthly page needs

**Files:**
- Modify: `web/app/desk.css`. Copy from `core/ui_components.py` `COMPONENT_CSS`, without changing values: `.rd-ctx*` (lines ~307–314, plus the 379–381 small-screen rules), `.rd-checks/.rd-check*` (~330–335), `.rd-big*`, `.rd-bar*`, `.rd-stat-label`, `.rd-stat-sub` (~499–500), and the tab look (~434–438) as `.desk-tabs`. Add `.explain-box` from `master_dashboard.py` ~499–508, mapped to `--rd-*` tokens. Add `.desk-rail` with `@media (min-width:1200px) and (min-height:900px) { .desk-rail { position: sticky; top: 16px; } }`.
- Modify: `web/components/desk/primitives.tsx`. Add `ContextBar({ items: [string,string][], basis?: string })`, `BigValue({ text, tone? })` (uses `bigValueParts`; move that function to `format.ts` if a client file imports it), `StatBar({ label, value, tone })`, and `Checklist({ checks: CheckRow[] })`. They produce the same markup and class names as the Python builders.
- Create: `web/components/desk/tabs.tsx`, a client component: `Tabs({ tabs: { id: string; label: string; content: ReactNode }[] })`. It uses `role="tablist"`/`tab`/`tabpanel`, Left and Right arrow keys, and `aria-selected`.
- Create: `web/components/desk/glossary.tsx`, `GlossaryDisclosure()`, moved from `web/app/page.tsx`'s glossary `<details>`. Home uses it unchanged.
- Test: `web/tests/desk-primitives.test.tsx` (render with `react-dom/server` `renderToStaticMarkup`, as other component tests do; if none exist, assert markup strings)

**Interfaces:**
- Consumes: `CheckRow`, `bigValueParts` (Task 3).
- Produces: `ContextBar`, `BigValue`, `StatBar`, `Checklist`, `Tabs`, `GlossaryDisclosure`, and the CSS classes `.desk-rail`, `.desk-tabs`, `.explain-box`.

- [ ] **Step 1: Failing tests.** `ContextBar` markup equals `ui.context_bar([('Universe','Nifty 50 (current list)')], basis='Gross · before costs and slippage')`; hard-code the Python output string in the test. `BigValue("+20.9%","gain")` gives `<span class="rd-big rd-big--gain">+20<span class="rd-big__dec">.9%</span></span>`. `Checklist` renders one `li.rd-check` per row, with the pill label. `Tabs`: the first tab is selected and only its panel renders.
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement** the CSS and components. Swap Home's glossary for `<GlossaryDisclosure />`.
- [ ] **Step 4: Run web tests + tsc + lint, expect PASS. Open `/` in the browser: Home looks unchanged.**
- [ ] **Step 5: Commit** `feat(web): context bar, stat bars, checklist, tabs and glossary for desk pages`

### Task 5: The `/monthly` page

**Files:**
- Create: `web/app/monthly/page.tsx` (server component, `export const dynamic = "force-dynamic"`)
- Create: `web/components/desk/monthly/summary-card.tsx` (client: CAGR block + stat bars on the left, the "Simulated account vs Nifty" chart with `1Y/3Y/All` `Segmented` (default `All`) on the right, at a 1 : 2.3 ratio that stacks below 1024px)
- Create: `web/components/desk/monthly/ranking-desk.tsx` (client: the filter, the ranking `DeskTable` and the detail rail, which share selection state)
- Create: `web/components/desk/monthly/price-chart.tsx`, `web/components/desk/monthly/equity-chart.tsx` (client, `lightweight-charts`, following `GrowthChart` in `home-cards.tsx`)
- Create: `web/components/desk/monthly/lower-tabs.tsx` (Rebalance log / Rules and checks / Exit research)
- Modify: `web/lib/desk/nav.ts`: set the Monthly item `href: "/monthly"`
- Test: `web/tests/desk-nav.test.ts`: `strategyPageHref("Monthly","HAL")` equals `{ href: "/monthly?ticker=HAL", external: false }`

**Interfaces:**
- Consumes: Task 3 (`loadMonthly`, mappers, constants, types), Task 4 (primitives, `Tabs`, `GlossaryDisclosure`, `.desk-rail`), the existing `PageHeader`, `StatusPill`, `ChangePill`, `RailList`, `EmptyState`, `SectionHead`, `Segmented`, `DeskTable`, `NameCell`, `ResearchNotice`, and `savedDataAges()` (its `"Monthly"` entry gives the ranking age).
- Produces: route `/monthly?ticker=SYMBOL`.

Page order (as `render_monthly`):
1. `PageHeader` with `MONTHLY_TITLE` / `MONTHLY_SUB`; right side: `StatusPill("Live","info")` + `rankingAge` pill. If `loadMonthly` fails: the header plus the same "not ready" `EmptyState` pattern as Home's `NOT_READY`, naming `ui_monthly.json`.
2. If `summary === null`: the `EmptyState` "No monthly simulation is saved" plus the ranking desk only (Streamlit returns early).
3. `ContextBar`: Universe "Nifty 50 (current list)", Test period `` `${start} → ${end}` ``, Rule "Top 5 by RS score, monthly", basis "Gross · before costs and slippage".
4. `SummaryCard`: the chart draws the saved traces of the chosen window as is (strategy = area with 7% fill, benchmark = dotted line, plus a dashed 0% price line), with a small legend row (dot + trace name) and the `CHART_NOTE`.
5. `div.desk-split`: main = `SectionHead("Saved ranking", "Nifty 50 by RS score · click a row")` + `Segmented(MONTHLY_FILTERS)` + `DeskTable` + `RANKING_NOTE`; rail = `div.desk-rail`. The rail holds the detail `RailList` (company title + `rankStatus` pill in the head; `"{symbol} · NSE"`; Price, Month move, Nifty benchmark, RS score and Model label rows, with the subs from `_render_monthly_detail`), then the price card (`rd-stat-label` "Closing price · last N sessions (saved to …)" + chart, or `EmptyState("No saved price history", "data/{ticker}.csv is missing or unreadable.")`), then the "Model top 5" `RailList` with `ChangePill(rs)`.
   - Ranking columns: `#` (num, p1, sort rank), Company (name, p1, title company / sub `rankSub`), Price (num, p2), Month move (num pill, p1, sort `month_ret`), RS score (num, p1, sort `rs`, `formatSigned(rs,2)+"%"`), Model label (pill, p2; tone `info` for rank ≤ 5, else `muted`). The rows are `ranking` filtered by `filters[pick]` and keep rank order. The empty text is `` `No stocks match “${pick}” in the saved ranking.` ``. An empty ranking shows the "No saved ranking" `EmptyState`.
   - Selection: the initial value is `resolveSelected(ranking, default_symbol, searchParams.ticker)`. A row click sets state and calls `history.replaceState` with `?ticker=`. When `window.innerWidth < 1200`, it also calls `scrollIntoView({ block: "start" })` on the rail.
6. `Tabs`: Rebalance log = `DeskTable` (Date text p1 sort date; Top 5 held text p1; Bought p2; Sold p2; Account value num p1 sort value `formatRupees(v,0)`; no row click) + `REBALANCE_NOTE(total)`, or the "No rebalance log saved" empty state. Rules and checks = `.explain-box` `HOW_IT_WORKS` + bold `HOW_TO_READ_TITLE` + `HOW_TO_READ` + `SectionHead("Validation status","what has and has not been checked")` + `Checklist`. Exit research = heading `Exit research: Monthly stock rotation`, `EXIT_CAPTION`, three metric cells, the targets `DeskTable`, the caption, and the curve chart (median solid, p25/p75 dotted, vertical marker at `hold_days`). With no rec, the text is "Exit Playbook: insufficient trade history to recommend a hold/exit plan yet."
7. `ResearchNotice`, `FOOTER_CAPTION`, `GlossaryDisclosure`.

- [ ] **Step 1: Failing nav test** (above). Run it and expect FAIL (`external: true`).
- [ ] **Step 2: Implement** the page and components. Flip the nav href.
- [ ] **Step 3: Verify.** Web tests, `npx tsc --noEmit` and `npm run lint` pass. With `npm run dev`, `/monthly` and `/monthly?ticker=HAL` render with no console errors (check with Playwright `browser_console_messages`). Clicking a Home Monthly candidate opens `/monthly?ticker=…` with that row selected.
- [ ] **Step 4: Number check against Streamlit.** At 1280 wide, take a screenshot of `/monthly` and of Streamlit's Monthly page (port 8500). The CAGR, the five stat values, rank 1–5 rows, and the latest rebalance row match. Save both screenshots to `C:/Users/User/Documents/Stocks/.superpowers/audit/next-monthly-*.png`.
- [ ] **Step 5: Commit** `feat(web): Monthly stock rotation page in the Research Desk style`

### Task 6: Fit audit, visual QA, handoff

**Files:**
- Modify: `web/tests/fit/fit-audit.js`: set `PAGES = ["/", "/monthly"]`. Add two Monthly-only checks:
  - (a) At every viewport, scroll the page to the end and assert that the rail's last child (`.desk-rail > :last-child`) has `getBoundingClientRect().bottom <= innerHeight` at some scroll position. Also assert that `getComputedStyle(rail).position` is `static` when `innerHeight < 900`.
  - (b) At 390×844, click the third ranking row, wait 500ms, and assert that the rail's top is inside the viewport.
- Modify: `MEMORY.md` (project): mark Monthly as built, list the commits, and set the next page (Price strength (Momentum), which needs a mockup first).

- [ ] **Step 1: Run the audit** through the Playwright MCP tool (as in `web/tests/fit/README.md`) against `npm run dev`. Expected: `ALL PASS` for `/` and `/monthly` at the 5 viewports. Fix layout in CSS only, then rerun until it passes.
- [ ] **Step 2: Visual QA** at 1280×600 and 390×844, light and dark (`emulateMedia`). Save the screenshots to `C:/Users/User/Documents/Stocks/.superpowers/audit/next-monthly-{1280,390}-{light,dark}.png` and compare them to `C:/Users/User/Documents/Stocks/.playwright-mcp/streamlit-ref/04-*.png` for section order.
- [ ] **Step 3: Full verification.** Python suite (expect 274 + Task 1/2 additions, all passing; capture the real exit code), web suite with `PYTHON_BIN`, `npx tsc --noEmit`, `npm run lint`, and `verify_protected.py` (no function or file drift beyond the known KPI drift from the 2026-11-07 data refresh).
- [ ] **Step 4: Commit** `test(web): fit audit covers the Monthly page` and the `MEMORY.md` update. Show the screenshots to the user for approval (spec §8.1).
