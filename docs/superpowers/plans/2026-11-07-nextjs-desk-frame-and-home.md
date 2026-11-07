# Research Desk in Next.js — Frame + Home Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the first usable slice of the Next.js Research Desk: the frame (sidebar, nav, pinned update controls, v2 theme) and the Home page. It must match Streamlit's Home numbers and fit a 1280×600 laptop view.

**Architecture:** Python stays the only place numbers are computed. A new save-results script, `precompute_ui_home.py`, calls the same `master_dashboard.py` functions Streamlit uses and writes `ui_snapshot.json`. The Next.js app (`web/`) reads that file and file ages on the server, then renders v2 components. Updates run the same step lists as Streamlit, through a new streaming job route. Once that route works, Streamlit's own update buttons are disabled.

**Tech Stack:** Next.js 16.2.7 (App Router), React 19.2, Tailwind 4, `@tanstack/react-table`, `lightweight-charts`, `lucide-react`, vitest 4. Python 3.13 in `.venv` with pytest. No new libraries.

**Spec:** `docs/superpowers/specs/2026-11-07-nextjs-research-desk-design.md`

All paths below are relative to `Nifty Momentum Rotation Stratergy/` unless they start with `web/`.

## Global Constraints

- No new npm or pip dependencies. Use only what `web/package.json` and `.venv` already have.
- Next.js 16 has breaking changes: before writing Next code, read the matching guide in `web/node_modules/next/dist/docs/` (layouts, server components, route handlers, `next/font`).
- Strategies, backtests, formulas, KPIs and data schemas are read-only. Approved Python edits only: new `precompute_ui_home.py`; adding it to `_PRECOMPUTE_FOR` (`master_dashboard.py`), `run_all.py` and `refresh_data.bat`; disabling Streamlit's update buttons (Task 9).
- Nav labels, group names and order are verbatim: Home · STRATEGIES: Browse strategies, Create a strategy · FIND STOCKS: Monthly stock rotation, Newly listed stocks (IPO), Price strength (Momentum), After earnings (PEAD), Stocks to review · EVALUATE: Understand past trades, Compare past results.
- v2 tokens come from `core/ui_components.py` `COMPONENT_CSS`. Light: bg `#F7F6F3`, card `#FFFFFF`, sidebar `#F2F1EC`, line `#E7E4DD`, text `#1D1D1B` / `#45443F` / `#77756E`, gain `#12805C`, loss `#C2364B`, warn `#A86200`, info `#1F6F78`, with tints `#E4F3EC` / `#FBE8EB` / `#FBF0DF` / `#E3F0F1`. Dark values are under `[data-theme="dark"]` in the same file. Font Inter 400/500/600/700, tabular numbers. Type 11/12/13/14/16/22 px; spacing 4/8/12/16/24/32 px; radius 10px and 6px.
- Display formats copy Python exactly: `change_pill` (`↗ ` / `↘ ` prefix, absolute value, default `{:.2f}%`, `—` when missing); `freshness_label` (`no saved file`, `updated today`, `1 day old`, `N days old`); `freshness_tone` (≤7 days gain, ≤21 warn, else loss, missing muted); `LOW_SAMPLE_TRADES = 30`.
- Layout: design at 1280×600 first. No horizontal page scroll at 1280×600, 1024, 1920 and 390. No fixed-height or nested scroll boxes. Long tables show 15 rows plus "Show all N rows". The right rail stacks under the main column below 1200px.
- Never silently change a displayed number. If a Next.js number differs from Streamlit and Streamlit looks wrong, stop and report it to the user.
- Python commands use `.venv/Scripts/python.exe`. Web commands run in `web/`. `web/.env.local` sets `DATA_DIR`. Add `PYTHON_BIN=../.venv/Scripts/python.exe` there (Task 5).

## Review Focus

1. **`ui_snapshot.json` missing, half-written or from an older script version.** Home shows a clear empty state ("Saved results for this page are not ready. Run Update all data.") instead of crashing. The writer swaps in the file atomically. → tests in Task 1 and Task 3.
2. **An update is already running when the user clicks Update again**, from the same tab, another tab or after a reload. The route returns 409 and the panel says "An update is already running." It must not start a second job. → test in Task 5.
3. **One strategy's download fails, for example no internet.** The other strategies still run. The panel lists which strategy failed at which step, with the error tail. After it finishes, the page data and sidebar ages refresh. → test in Task 5.
4. **Very short window (1280×560) or phone (390px).** The pinned update controls stay visible. The nav scrolls on its own. On a phone the sidebar is a slide-over that closes after picking a page. → fit audit in Task 10.
5. **A candidate's strategy page is not built yet.** Clicking a row or a strategy opens the Streamlit app in a new tab with the "opens old app" hint. It never opens a 404. → test in Task 6.

---

### Task 0: Save today's Streamlit work and branch

**Files:**
- Commit: `master_dashboard.py`, `pead_dashboard.py`, `tests/test_modern_table.py`, `docs/superpowers/specs/2026-11-07-nextjs-research-desk-design.md`, this plan
- Leave uncommitted: the data files changed by today's refresh (`data/*.csv`, `backtest_results.csv`, etc.). Mention them to the user; do not commit or revert them.

- [ ] **Step 1: Confirm the branch is `redesign/research-desk` and the suites pass**

Run: `git rev-parse --abbrev-ref HEAD` → `redesign/research-desk`
Run: `.venv/Scripts/python.exe -m pytest tests -q -p no:cacheprovider` → `266 passed`
Run (in `web/`): `npm test` → all pass. Record the count as the web baseline.

- [ ] **Step 2: Commit the Streamlit fixes**

```bash
git add master_dashboard.py pead_dashboard.py tests/test_modern_table.py
git commit -m "fix(ui): Streamlit scroll, fit, sort and pinned refresh fixes"
```

- [ ] **Step 3: Branch and commit the docs**

```bash
git switch -c redesign/nextjs-desk
git add docs/superpowers/specs/2026-11-07-nextjs-research-desk-design.md docs/superpowers/plans/2026-11-07-nextjs-desk-frame-and-home.md
git commit -m "docs: Next.js Research Desk design and frame+Home plan"
```

---

### Task 1: `precompute_ui_home.py` writes `ui_snapshot.json`

**Files:**
- Create: `precompute_ui_home.py`
- Test: `tests/test_precompute_ui_home.py`

**Interfaces:**
- Consumes: `master_dashboard.load_monthly()`, `load_ipo()`, `load_momentum()`, `_home_candidates(m, i, mo)`, `_regime_snapshot()`, `_data_freshness()`, `_home_growth_figure(m, i, mo, window)`, `_load_strategies_index()`, `HOME_STRATEGIES`, `_SHORT`, `_STATUS_TONE`, `ui.LOW_SAMPLE_TRADES`. Import `master_dashboard` outside Streamlit (bare mode works, ~8 s; verified 2026-11-07).
- Produces: `build_ui_snapshot(m: dict, i: dict, mo: dict) -> dict` and `write_snapshot(snapshot: dict, path: Path) -> None`. `main()` writes `ui_snapshot.json` at the project root. JSON shape (`version: 1`):

```json
{
  "version": 1,
  "generated_at": "2026-11-07T09:40:00",
  "frame": {
    "regime": {"status": "Bear", "bars_since_flip": 169, "close": 25030.35, "sma50": 23264.12,
               "sma200": 24009.89, "high52": 26328.55, "pct_from_high": -4.93, "date": "2026-11-06"},
    "freshness": {"latest_bar": "06 Nov 2026", "file_mtime": "07 Nov 2026 09:16", "age_hours": 1.5,
                  "source_file": "data\\nse_bse\\RELIANCE.NS.csv"}
  },
  "home": {
    "candidates": [{"strategy": "Monthly Rotation", "short": "Monthly", "ticker": "BAJFINANCE",
                    "company": "Bajaj Finance", "status": "Top 5 · #1", "status_tone": "info",
                    "key_measure": "RS +7.7% vs Nifty", "change": 15.83, "data": "updated today"}],
    "pead_has_signals": false,
    "strategies": [{"id": "monthly_rotation", "title": "Monthly stock rotation", "status": "Live",
                    "num_trades": 36, "unit": "rebalances", "small_sample": false,
                    "max_dd_pct": -12.0, "cagr_pct": 20.9}],
    "growth": {"1Y": [{"id": "monthly_rotation", "title": "Monthly stock rotation", "colour": "#3B6FD8",
                       "start": "Nov 2023", "last_pct": 72.9, "points": [["2023-11-01", 0.0]]}],
               "3Y": [], "5Y": [], "Max": []}
  }
}
```

`status_tone` follows Streamlit's rule: `_STATUS_TONE.get(status, 'info')`. `change` keeps full precision; the UI rounds it. Growth `points` come from the rebased, downsampled series used by `_home_growth_figure`, with dates as `YYYY-MM-DD`. Extract the series values, not the Plotly figure. A small internal helper is fine; it must call the same rebasing and `_downsample_series`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_precompute_ui_home.py — load master_dashboard with the fake streamlit
# helper pattern already used in tests/test_modern_table.py, then import precompute_ui_home.
def test_snapshot_candidates_match_home_candidates(md_module, sample_inputs):
    snap = pre.build_ui_snapshot(*sample_inputs)
    expected = md_module._home_candidates(*sample_inputs)
    assert [c['ticker'] for c in snap['home']['candidates']] == list(expected['Ticker'])
    assert snap['home']['candidates'][0]['status_tone'] == 'info'      # 'Top 5 · #1' not in _STATUS_TONE
    assert snap['version'] == 1

def test_snapshot_growth_windows_present(sample_inputs):
    snap = pre.build_ui_snapshot(*sample_inputs)
    assert set(snap['home']['growth']) == {'1Y', '3Y', '5Y', 'Max'}
    first = snap['home']['growth']['Max'][0]
    assert first['points'][0][1] == 0.0                                 # rebased to 0% at window start

def test_write_snapshot_is_atomic(tmp_path):
    out = tmp_path / 'ui_snapshot.json'
    pre.write_snapshot({'version': 1}, out)
    assert json.loads(out.read_text(encoding='utf-8')) == {'version': 1}
    assert not list(tmp_path.glob('*.tmp'))                             # temp file replaced, not left behind
```

`sample_inputs`: small monthly, IPO and momentum dicts with 2–3 rows each and a short equity series, built inline.

- [ ] **Step 2: Run and confirm they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_precompute_ui_home.py -q` → FAIL (`ModuleNotFoundError: precompute_ui_home`)

- [ ] **Step 3: Implement `build_ui_snapshot`, `write_snapshot` and `main` in `precompute_ui_home.py`**

`write_snapshot`: write `path.with_suffix('.json.tmp')` in UTF-8, then `os.replace`. NaN becomes `null`. Use the `_num` approach from `precompute_insights.py`.

- [ ] **Step 4: Run the tests, then the real script**

Run: `.venv/Scripts/python.exe -m pytest tests/test_precompute_ui_home.py -q` → PASS
Run: `.venv/Scripts/python.exe precompute_ui_home.py` → writes `ui_snapshot.json`, whose candidate count equals `len(_home_candidates(...))` for the current files.

- [ ] **Step 5: Add the script to the update step lists**

- `master_dashboard.py` `_PRECOMPUTE_FOR`: append `'precompute_ui_home.py'` last for each of `Monthly`, `IPO`, `Momentum` and `PEAD`.
- `run_all.py`: append `'precompute_ui_home.py'` after `'precompute_insights.py'` in its precompute list.
- `refresh_data.bat`: add a `precompute_ui_home.py` step after the last existing precompute step, in the same echo/errorlevel style.

Run: full pytest → baseline + 3 passing.

- [ ] **Step 6: Commit**

```bash
git add precompute_ui_home.py tests/test_precompute_ui_home.py master_dashboard.py run_all.py refresh_data.bat
git commit -m "feat(data): precompute_ui_home writes ui_snapshot.json for the Next.js desk"
```

---

### Task 2: v2 theme and base display components

**Files:**
- Modify: `web/app/globals.css`, replacing the theme tokens with the v2 `--rd-*` tokens (light default, `[data-theme="dark"]` override). Keep the shadcn variable names (`--background`, `--card`, `--border`, `--foreground`, `--muted-foreground`) mapped onto the v2 values, so untouched old pages still render.
- Modify: `web/app/layout.tsx`: Inter via `next/font/google` (weights 400/500/600/700) as `--font-sans`; `<html data-theme>`; no hard-coded `className="dark"`.
- Create: `web/lib/desk/format.ts`
- Create: `web/components/desk/pill.tsx`, `web/components/desk/rail-list.tsx`, `web/components/desk/page-header.tsx`, `web/components/desk/section-head.tsx`, `web/components/desk/segmented.tsx`
- Test: `web/tests/desk-format.test.ts`

**Interfaces:**
- Produces (`web/lib/desk/format.ts`):
  - `type Tone = "gain" | "loss" | "warn" | "info" | "muted"`
  - `formatChange(value: number | null | undefined, decimals = 2): { text: string; direction: "up" | "down" | "flat" }`
  - `freshnessLabel(ageDays: number | null): string`
  - `freshnessTone(ageDays: number | null): Tone`
  - `formatNumber(value: number, decimals = 2): string` (en-IN grouping is **not** used; Python's `{:,.2f}` gives `25,030.35`, so use `en-US` grouping)
- Produces (components): `<StatusPill label tone />`, `<ChangePill value decimals? />`, `<RailList title meta? items={{title, sub?, value: ReactNode}[]} />`, `<PageHeader title sub right? />`, `<SectionHead title meta? right? />`, `<Segmented options value onChange ariaLabel />`.

- [ ] **Step 1: Write the failing tests**

```ts
test("formatChange copies Python change_pill", () => {
  expect(formatChange(15.828988)).toEqual({ text: "↗ 15.83%", direction: "up" });
  expect(formatChange(-4.93)).toEqual({ text: "↘ 4.93%", direction: "down" });
  expect(formatChange(0)).toEqual({ text: "0.00%", direction: "flat" });
  expect(formatChange(null)).toEqual({ text: "—", direction: "flat" });
  expect(formatChange(72.94, 1).text).toBe("↗ 72.9%");
});
test("freshness label and tone copy Python", () => {
  expect([null, 0, 1, 7, 8, 21, 22].map(freshnessLabel)).toEqual(
    ["no saved file", "updated today", "1 day old", "7 days old", "8 days old", "21 days old", "22 days old"]);
  expect([null, 0, 7, 8, 21, 22].map(freshnessTone)).toEqual(["muted", "gain", "gain", "warn", "warn", "loss"]);
});
test("formatNumber matches Python {:,.2f}", () => {
  expect(formatNumber(25030.35)).toBe("25,030.35");
});
```

- [ ] **Step 2: Run and confirm they fail** — `npm test -- desk-format` → FAIL (module not found)
- [ ] **Step 3: Implement `format.ts` and the components.** Component styles follow the `rd-pill`, `rd-chg`, `rd-li`, `rd-list__head`, `rd-page`, `rd-sec` rules in `core/ui_components.py`. Pills keep their tinted backgrounds; numbers use `tabular-nums`.
- [ ] **Step 4: Run** — `npm test` → all pass; `npm run build` → succeeds.
- [ ] **Step 5: Commit** — `git commit -m "feat(web): v2 Research Desk tokens, Inter and base components"`

---

### Task 3: Server data loaders

**Files:**
- Create: `web/lib/desk/snapshot.ts`, `web/lib/desk/saved-ages.ts`
- Test: `web/tests/desk-snapshot.test.ts`, `web/tests/desk-saved-ages.test.ts` (fixtures in `web/tests/fixtures/desk/`)

**Interfaces:**
- Produces:
  - `type UiSnapshot` (mirrors the Task 1 JSON exactly; `version: 1`)
  - `loadSnapshot(dataDir?: string): Promise<{ ok: true; snapshot: UiSnapshot } | { ok: false; reason: "missing" | "invalid" | "version" }>`. It validates the top-level keys and `version === 1`, and never throws.
  - `savedDataAges(dataDir?: string, now?: Date): Promise<{ name: "Monthly" | "IPO Edge" | "Momentum" | "PEAD"; ageDays: number | null }[]>`. It reads mtimes of `live_rankings.csv`, `ipo_edge_equity.csv`, `momentum_edge_equity.csv` and `pead_data/live_signals.csv`, in that order, mirroring `_saved_data_ages` / `_file_age_days` (whole days, floor).
  - `oldestAge(ages): { name: string; ageDays: number } | null`

- [ ] **Step 1: Write the failing tests**
  - `loadSnapshot` on a valid fixture → `ok: true` with 2 candidates. On a missing dir → `{ok:false, reason:"missing"}`. On a truncated JSON fixture → `"invalid"`. On a `version: 2` fixture → `"version"`.
  - `savedDataAges` on a temp dir where files have mtimes of now, now−1 d and now−30 d, with one file missing → `[0, 1, 30, null]` in the fixed order. `oldestAge` → `{name: "Momentum", ageDays: 30}`.
- [ ] **Step 2: Run and confirm they fail.**
- [ ] **Step 3: Implement** with `node:fs/promises`, using the `DEFAULT_DATA_DIR` convention from `web/lib/data/strategies.ts`.
- [ ] **Step 4: Run** — `npm test` → pass.
- [ ] **Step 5: Commit** — `git commit -m "feat(web): desk snapshot and saved-data-age loaders"`

---

### Task 4: Desk data table

**Files:**
- Create: `web/lib/desk/table.ts` (pure helpers), `web/components/desk/desk-table.tsx` (client, TanStack)
- Test: `web/tests/desk-table.test.ts`

**Interfaces:**
- Produces:
  - `type DeskColumn<R> = { key: string; label: string; kind: "name" | "num" | "text" | "pill"; priority: 1 | 2 | 3; sortValue?: (r: R) => number | string | null; render: (r: R) => ReactNode }`. Priority 1 always shows. Priority 2 hides below 640px. Priority 3 hides below 1024px.
  - `sortRows<R>(rows: R[], col: DeskColumn<R>, dir: "asc" | "desc"): R[]`. Nulls always go last. Numbers compare numerically and strings with `localeCompare`. The sort is stable.
  - `previewRows<R>(rows: R[], expanded: boolean, limit = 15): R[]`
  - `<DeskTable rows columns getRowId selectedId? onRowClick? empty previewLimit? />`. Header click toggles asc/desc with ▲/▼. Headers are buttons, so keyboard Enter/Space works. "Show all N rows" / "Show first 15 rows" toggle. Two-line name cell (title + sub). No fixed height, no inner vertical scroll. The table may scroll sideways inside its wrapper only below 640px.

- [ ] **Step 1: Write the failing tests**

```ts
test("sortRows puts nulls last both ways", () => {
  const rows = [{ v: 2 }, { v: null }, { v: -1 }];
  const col = { key: "v", sortValue: (r: any) => r.v } as any;
  expect(sortRows(rows, col, "asc").map(r => r.v)).toEqual([-1, 2, null]);
  expect(sortRows(rows, col, "desc").map(r => r.v)).toEqual([2, -1, null]);
});
test("previewRows shows 15 until expanded", () => {
  const rows = Array.from({ length: 20 }, (_, i) => i);
  expect(previewRows(rows, false)).toHaveLength(15);
  expect(previewRows(rows, true)).toHaveLength(20);
  expect(previewRows(rows.slice(0, 10), false)).toHaveLength(10);
});
```

- [ ] **Step 2: Run and confirm they fail.**
- [ ] **Step 3: Implement** the helpers and the component. Row styling follows `rd-table`, `rd-tr`, `rd-tr--sel` and `rd-name` in `core/ui_components.py`.
- [ ] **Step 4: Run** — `npm test` → pass.
- [ ] **Step 5: Commit** — `git commit -m "feat(web): desk table with sort, preview and column priorities"`

---

### Task 5: Update runner and `/api/update` route

**Files:**
- Create: `web/lib/desk/update-steps.ts`, `web/lib/desk/run-update.ts`, `web/app/api/update/route.ts`
- Modify: `web/.env.local` (add `PYTHON_BIN=../.venv/Scripts/python.exe`)
- Test: `web/tests/desk-run-update.test.ts`, `web/tests/desk-update-steps-parity.test.ts`

**Interfaces:**
- Consumes: `runRecompute` / `SpawnFn` from `web/lib/recompute.ts`; `tryAcquire` / `release` from `web/lib/job-lock.ts`; `streamJob` from `web/lib/job-stream.ts`.
- Produces:
  - `type UpdateStrategy = "Monthly" | "IPO" | "Momentum" | "PEAD"`
  - `UPDATE_STEPS: Record<UpdateStrategy, string[][]>`. Each entry is the strategy's `_PIPELINES` steps followed by its `_PRECOMPUTE_FOR` scripts as single-item steps, exactly as `master_dashboard._run_refresh_steps` builds them, including `precompute_ui_home.py` from Task 1.
  - `runUpdate(spawnFn: SpawnFn, opts: { strategies: UpdateStrategy[]; cwd: string; pythonBin: string; stepTimeoutMs: number; onLine?: (l: string) => void }): Promise<{ status: number; body: UpdateBody }>`
  - `type UpdateBody = { ok: boolean; results: { strategy: UpdateStrategy; ok: boolean; failedStep?: string; errorTail?: string }[] }`. Per strategy it stops at the first failing step, then continues with the next strategy, like `_refresh_all`. `errorTail` holds the last 800 characters of stderr (or stdout if stderr is empty).
  - `POST /api/update` with body `{ strategy: "all" | UpdateStrategy }`. Anything else returns 400. If the lock is held it returns 409 `{ ok:false, error:"An update is already running." }`. Otherwise it streams SSE via `streamJob`. Step timeout is 30 min (`1_800_000` ms; downloads are long). The lock is released in `finally`.

- [ ] **Step 1: Write the failing tests**
  - Fake spawn where `IPO` step 1 exits 1 with stderr `"boom"`. Run `runUpdate` with all four strategies → `results` holds 4 entries. `IPO` is `{ok:false, failedStep:"ipo_edge_downloader.py", errorTail:"boom"}`. Monthly, Momentum and PEAD are `ok:true`. `body.ok` is `false`. Spawn call order matches `UPDATE_STEPS` in sequence, with IPO stopping after its first step.
  - Route: with the lock held, `POST {strategy:"all"}` → 409 and the exact message above. `POST {strategy:"rm -rf"}` → 400.
  - Step-list parity (integration, skipped when `PYTHON_BIN` is not set): spawn `PYTHON_BIN -c "import json,master_dashboard as m; print(json.dumps({k: m._PIPELINES[k] + [[s] for s in m._PRECOMPUTE_FOR.get(k, [])] for k in m._PIPELINES}))"` with `cwd = DATA_DIR`. Parse the last stdout line and assert it equals `UPDATE_STEPS`.
- [ ] **Step 2: Run and confirm they fail.**
- [ ] **Step 3: Implement.** Commands run `[pythonBin, ...step]` with `PYTHONIOENCODING=utf-8` and `PYTHONUNBUFFERED=1`. Script names come only from `UPDATE_STEPS`, never from the request.
- [ ] **Step 4: Run** — `npm test` → pass, with the parity test passing when `PYTHON_BIN` is set.
- [ ] **Step 5: Commit** — `git commit -m "feat(web): /api/update runs Streamlit's full update steps with live progress"`

---

### Task 6: Frame — sidebar, nav, pinned update panel, shared notices

**Files:**
- Create: `web/lib/desk/nav.ts`, `web/components/desk/sidebar.tsx` (client), `web/components/desk/update-panel.tsx` (client), `web/components/desk/market-context.tsx`, `web/components/desk/research-notice.tsx`, `web/components/desk/theme-toggle.tsx` (client), `web/components/desk/desk-shell.tsx`
- Modify: `web/app/layout.tsx` (use `DeskShell`; load `savedDataAges` and the snapshot's `frame` on the server and pass them down)
- Test: `web/tests/desk-nav.test.ts`

**Interfaces:**
- Produces (`web/lib/desk/nav.ts`):
  - `STREAMLIT_URL = process.env.NEXT_PUBLIC_STREAMLIT_URL ?? "http://localhost:8500"`
  - `NAV: { group: "" | "STRATEGIES" | "FIND STOCKS" | "EVALUATE"; items: { label: string; icon: LucideName; href: string | null }[] }[]`. `href: null` means not built yet. In this plan only Home (`/`) is built.
  - `navHref(item): { href: string; external: boolean }`. A `null` href returns `STREAMLIT_URL` with `external: true`.
  - `strategyPageHref(strategyShortOrId: string, ticker?: string): { href: string; external: boolean }`. It maps Monthly, IPO, Momentum, PEAD or a strategies-index id to its nav item. For an unbuilt page it falls back to Streamlit.
- Icons are lucide equivalents of Streamlit's `NAV_ICONS`: `LayoutDashboard`, `FolderOpen`, `CirclePlus`, `RefreshCw`, `Rocket`, `TrendingUp`, `CalendarDays`, `ListChecks`, `Activity`, `ArrowLeftRight`.

Behaviour (copy text exactly from the Streamlit sources named):
- Sidebar is 272px wide, with the brand block "Strategy / BACKTESTER". Nav groups follow Global Constraints. An item with an external fallback shows a small "opens old app" hint and opens in a new tab.
- The nav area scrolls on its own (`overflow-y:auto`, `min-height:0`). A bottom block stays pinned and holds:
  - the research note from `_render_sidebar_refresh`'s caption;
  - the age line: "All saved data updated today", or "Oldest saved data: {name}, {freshnessLabel}";
  - an **Update all data** primary button;
  - an **Update one strategy** menu with Monthly, IPO, Momentum and PEAD plus a "Last updated" list of pills.
- The update panel uses `runJobStream("/api/update", {strategy})` from `web/lib/use-job-stream.ts`. It shows progress lines while running and the per-strategy result list when done (the failed step and error tail for failures). It calls `router.refresh()` after completion. A 409 shows "An update is already running."
- Collapse: a chevron collapses the sidebar to 0 width, with no leftover blank column.
- Below 768px the sidebar is a slide-over opened by a menu button, and it closes when a nav item is picked.
- `MarketContext` is a collapsed disclosure at the top of the page, "Market context and price-data status". Its content mirrors `_render_regime_banner` (`master_dashboard.py:8317`) and the freshness line, from `snapshot.frame`.
- `ResearchNotice` uses the exact text of `research_notice()` in `core/workflow_ui.py`.
- `ThemeToggle` follows the system theme by default and sets `data-theme` on `<html>`. The choice is stored in `localStorage` inside try/catch.

- [ ] **Step 1: Write the failing tests**

```ts
test("nav labels, groups and order are verbatim", () => {
  expect(NAV.map(g => [g.group, g.items.map(i => i.label)])).toEqual([
    ["", ["Home"]],
    ["STRATEGIES", ["Browse strategies", "Create a strategy"]],
    ["FIND STOCKS", ["Monthly stock rotation", "Newly listed stocks (IPO)", "Price strength (Momentum)",
                     "After earnings (PEAD)", "Stocks to review"]],
    ["EVALUATE", ["Understand past trades", "Compare past results"]],
  ]);
});
test("unbuilt pages fall back to Streamlit", () => {
  expect(strategyPageHref("Monthly", "BAJFINANCE")).toEqual({ href: "http://localhost:8500", external: true });
  expect(navHref(NAV[0].items[0])).toEqual({ href: "/", external: false });
});
```

- [ ] **Step 2: Run and confirm they fail.**
- [ ] **Step 3: Implement** `nav.ts` and the components.
- [ ] **Step 4: Run** — `npm test` → pass; `npm run build` → succeeds. Start the app (`npm run dev`) and check by eye at 1280×600 that the sidebar matches `01-home.png`.
- [ ] **Step 5: Commit** — `git commit -m "feat(web): Research Desk frame with pinned update panel"`

---

### Task 7: Home page

**Files:**
- Create: `web/lib/desk/home.ts` (pure mappers), `web/components/desk/home/candidates-card.tsx` (client), `web/components/desk/home/growth-card.tsx` (client, `lightweight-charts`), `web/components/desk/home/home-rail.tsx`
- Modify: `web/app/page.tsx` (server: `loadSnapshot` → Home, or an empty state)
- Test: `web/tests/desk-home.test.ts`

**Interfaces:**
- Consumes: `UiSnapshot` (Task 3), `DeskTable` / `DeskColumn` (Task 4), the pills and lists (Task 2), `strategyPageHref` (Task 6).
- Produces:
  - `filterCandidates(c: UiSnapshot["home"]["candidates"], pick: "All" | "Monthly" | "IPO" | "Momentum")`
  - `candidateNote(pickHasPead: boolean): string`. It returns Streamlit's exact note text from `_render_home_candidates`, adding the PEAD sentence when `pead_has_signals` is false.
  - `strategySub(s): string`. It returns `"{status} · {n:,} {unit}{' · small sample' if small} · worst fall {max_dd_pct:.1f}%"`, as in `_render_home_strategies`.
  - `marketRows(regime): {title, sub?, value}[]`. It follows `_render_home_market`: the trend pill shows On (gain), Off (warn) or Unknown (muted), and rows appear only when present.
  - `headerTrend(status): {label, tone}`. It returns "Trend filter on" (gain), "Trend filter off" (warn) or "Trend unknown" (muted).

Layout (reference `01-home.png`):
- Header row: "Overview" with "{n} candidates in saved files · research only, nothing here places orders". On the right: the trend pill and "Prices up to {latest_bar} · {freshnessLabel(floor(age_hours/24))}".
- Main column (2.2 fr): the Candidates section head ("from saved rankings and signals") with the segmented filter, then a `DeskTable`. Columns:
  - Company (name; title = company or ticker, sub = "{ticker} · {short}"; priority 1)
  - Status (pill; priority 1)
  - Key measure (text; priority 3)
  - Move (`ChangePill`; priority 1)

  Row click → `strategyPageHref(short, ticker)`. The note goes under the table. Then "Growth of each strategy" ("saved backtests · gross") with a 1Y/3Y/5Y/Max segmented switch, defaulting to Max. The line chart uses each series' `colour` and a 0% dotted baseline. Under the chart sits the legend list ("change since {start}" with `ChangePill(last_pct, 1)`), then the note text from `_render_home_growth`.
- Rail (1 fr): Market (`RailList`, "Nifty"), then Strategies (`DeskTable` with Strategy and Per year columns, row click → `strategyPageHref(id)`, then the note "Gross results over different test periods; not a ranking of future performance."), then Saved data (`RailList` of `freshnessLabel` pills, meta "Refresh data in the sidebar").
- Footer: `ResearchNotice`, a "How to read these figures" disclosure (exact text from `render_home`, using `LOW_SAMPLE_TRADES = 30`), then the glossary disclosure, reusing `web/lib/glossary.ts`.
- Below 1200px the rail stacks under the main column.
- Empty state when `loadSnapshot` fails: "Saved results for this page are not ready. Run Update all data." plus the reason.

- [ ] **Step 1: Write the failing tests**
  - `filterCandidates` with a fixture holding 2 Monthly, 1 IPO and 3 Momentum candidates → All 6, Monthly 2, IPO 1, Momentum 3.
  - `strategySub({status:"Paper", num_trades:4, unit:"trades", small_sample:true, max_dd_pct:-3.1})` → `"Paper · 4 trades · small sample · worst fall -3.1%"`.
  - `headerTrend("Bear")` → `{label:"Trend filter off", tone:"warn"}`.
  - `marketRows` with the regime from the Task 1 JSON example → titles `["Trend filter","Nifty close","50-day average","200-day average","From 52-week high","In this state"]`, and the Nifty close value text `"25,030.35"`.
  - **Parity (integration, skipped without `PYTHON_BIN`):** run `precompute_ui_home.py` against the real files. Then spawn Python to print `[(ticker, status, key_measure, change_pill_text)]` for `_home_candidates(...)`. `change_pill_text` is `ui.change_pill(v)` with the HTML tags stripped. Assert it equals the TS mapping of the snapshot through `formatChange`, row by row.
- [ ] **Step 2: Run and confirm they fail.**
- [ ] **Step 3: Implement** the mappers, components and page.
- [ ] **Step 4: Run** — `npm test` → pass; `npm run build` → succeeds.
- [ ] **Step 5: Side-by-side check.** With Streamlit on :8500 and Next on :3000, open both Home pages through the Playwright browser tool. The candidate list, statuses, moves, market values and strategy CAGRs must match. If Streamlit's cached data is older than `ui_snapshot.json`, restart Streamlit first. Record any difference and stop if one exists (Global Constraints).
- [ ] **Step 6: Commit** — `git commit -m "feat(web): Home page in the Research Desk style"`

---

### Task 8: Retire the old `web/` home and nav

**Files:**
- Modify or delete: `web/components/app-shell.tsx` (replaced by `DeskShell`; delete it once no import remains), `web/components/data-freshness.tsx` (delete if unused)
- Keep: the old routes `/leaderboard`, `/screener`, `/suggestions`, `/insights`, `/glossary` and `/strategy/*`. They are no longer in the nav and get replaced page by page in later plans. Leave them as they are, apart from inheriting the new tokens.

- [ ] **Step 1:** `npm run build` and `npm test` → pass, with no import of the deleted files left.
- [ ] **Step 2: Commit** — `git commit -m "refactor(web): remove old shell replaced by the desk frame"`

---

### Task 9: Disable Streamlit's update buttons

**Files:**
- Modify: `master_dashboard.py` (`_render_sidebar_refresh`), `core/refresh_ui.py` (`render_staleness_banner`'s Update button)
- Test: `tests/test_streamlit_updates_moved.py`

**Interfaces:**
- Produces: `UPDATES_MOVED_NOTE = "Updates now run from the new app: http://localhost:3000 (Update all data in its sidebar)."`. It goes in `core/workflow_ui.py`, and both places show it with `st.caption` instead of a button. `render_staleness_banner` keeps its freshness message and drops only the button. `_PIPELINES` and `_PRECOMPUTE_FOR` stay, because `/api/update` and its parity test use them.

- [ ] **Step 1: Write the failing test.** Load `master_dashboard` with the fake-streamlit helper. Make `st.button` record its calls. Call `_render_sidebar_refresh()` and `render_staleness_banner("nse_bse", "data/nse_bse")` → assert no button calls, and that `st.caption` received `UPDATES_MOVED_NOTE`.
- [ ] **Step 2: Run and confirm it fails.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** — full pytest → baseline plus the new tests pass.
- [ ] **Step 5: Commit** — `git commit -m "feat(ui): Streamlit points updates to the Next.js app"`

Only do this task after Task 5's route has been run end-to-end once, with "Update one strategy → PEAD" from the Next.js sidebar succeeding.

---

### Task 10: Fit and scroll audit, then hand-off

**Files:**
- Create: `web/tests/fit/fit-audit.js`, a Playwright code snippet (`async (page) => {...}`) for the Playwright browser tool, plus `web/tests/fit/README.md` (one paragraph on how to run it). No new dependency.

The audit visits `/` at viewports 1280×600, 1280×560, 1024×700, 1920×1000 and 390×844. For each it reports:
- horizontal page overflow (`document.scrollingElement.scrollWidth - clientWidth`), which must be 0;
- the number of visible elements whose right edge passes the viewport, outside an element that scrolls sideways, which must be 0;
- whether mouse-wheel scrolling over the main area reaches the page bottom with no stalls;
- whether mouse-wheel scrolling over the sidebar nav reaches its end;
- whether "Update all data" is inside the viewport, which it must be at every size;
- on 390: the slide-over opens and closes, and tables are the only elements that scroll sideways.

- [ ] **Step 1:** Write the snippet. Run it against `http://localhost:3000` → every check passes. Fix and re-run until it does.
- [ ] **Step 2:** Screenshot `/` at 1280×600 in light and dark. Show the user next to `01-home.png` for approval (spec §8 "done").
- [ ] **Step 3: Commit** — `git commit -m "test(web): fit and scroll audit for the desk"`
- [ ] **Step 4:** Run the full suites one last time: `pytest` and `npm test`. Report the counts.

---

## Out of scope for this plan (next plans)

The remaining nine pages, in the spec's order (Monthly first), each with its own save-results additions. The eight non-v2 pages each get a mockup approved before coding. Moving the Python helpers out of `master_dashboard.py` once Streamlit is retired.
