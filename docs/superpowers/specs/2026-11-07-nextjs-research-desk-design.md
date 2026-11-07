# NSE Strategy Hub in Next.js — "Research Desk" design

Date: 2026-11-07
Status: draft, awaiting approval (builder check done; questions answered)
Owner: the user (single user, personal research tool)

## 1. Intent and why

The NSE Strategy Hub is a personal research dashboard. It shows candidates from four
strategies (Monthly stock rotation, Newly listed stocks (IPO), Price strength (Momentum),
After earnings (PEAD)) and the historical evidence behind each, from saved backtest and
ranking files. It places no orders.

Today the UI is a Streamlit app (`master_dashboard.py`, ~9,800 lines, port 8500). The user
keeps hitting layout problems: content does not fit the screen, the page or sidebar does
not scroll, and the update button cannot be found. Each fix works at the sizes tested and
breaks at another, because Streamlit owns the layout. The app fights it with ~2,000 lines
of stacked CSS overrides that target Streamlit's internal markup.

The user wants a long-term fix. Move the UI to Next.js, in the existing `web/` app, and
keep **the same page flow** and **the same approved v2 "Research Desk" design**.

The user's real screen: a laptop at 1920×1080 with Windows scaling at 150%. The browser
sees **1280×720 CSS px**, which leaves about **1280×600** for the page once the browser's
tabs and address bar are counted. This size is the main design target. The user also opens
the app on a phone sometimes.

## 2. Goals

1. Rebuild all 10 Streamlit pages in `web/`, with the same nav order, the same
   plain-language labels and the same flow.
2. Apply the v2 Research Desk style to **all 10 pages**. Only Home and Monthly stock
   rotation are in v2 in Streamlit today. The other 8 are still in older styling: Price
   strength (Momentum), Newly listed stocks (IPO), After earnings (PEAD), Stocks to review,
   Understand past trades, Compare past results, Browse strategies and Create a strategy.
3. Make content fit properly. At 1280×600: no horizontal page scroll, nothing cut off, and
   the page and sidebar scroll with a mouse wheel and a touchpad. At 390px wide (phone):
   the page is usable; wide tables may scroll sideways inside their own box.
4. Show the same numbers as Streamlit, read from the same saved files.
5. Deliver one page at a time. Each page is usable as soon as it is done.

## 3. Non-goals

- No change to strategies, backtest engines, formulas, KPIs, data schemas or Python
  dependencies. The Python side is read-only, with three approved exceptions:
  - adding small scripts that save results the UI needs (see §7.5);
  - adding those scripts to the existing update step lists (see §7.6);
  - disabling Streamlit's update buttons once the Next.js ones work (see §7.6).
- No new strategy features, no order placing, no accounts or log-in.
- No hosting or deployment. It runs locally, like Streamlit does today.
- Keeping the current `web/` look. Its pages and visual style are replaced.

## 4. Anti-goals (a failure even if it technically works)

- It looks different from the approved v2 design (see `01-home.png`).
- It loses data density: airy cards, big whitespace and fewer rows on screen. An earlier
  airy card restyle was rejected for exactly this (`PRD-dashboard-ui-facelift.md`).
- Any number differs from what Streamlit shows for the same saved files.
- The plain-language nav labels are renamed or reworded.
- Content is cut off or needs sideways page scrolling at 1280×600.

## 5. Constraints

- **Location:** `Nifty Momentum Rotation Stratergy/web/`. It is Next.js 16.2.7 with React
  19.2, Tailwind 4, `@tanstack/react-table`, `lightweight-charts`, `lucide-react` and
  base-ui/shadcn. `web/AGENTS.md` warns that this Next.js version has breaking changes.
  Read `node_modules/next/dist/docs/` before writing code.
- **No new libraries** without the user's approval. Use what `web/package.json` already has.
- **Data:** reuse `web/lib/data/strategies.ts`, which already reads the project's CSV/JSON
  files (`DATA_DIR`, default `..`).
- **Scripts:** reuse the existing job routes (`app/api/backtest`, `app/api/recompute`,
  `app/api/rebuild-all`), with their job lock and live progress (`lib/job-stream.ts`,
  `lib/use-job-stream.ts`).
- **Git:** the work goes on its own branch, off `redesign/research-desk`. Commit page by
  page. Run the web tests (`npm test`, vitest) and the Python suite (`pytest`) before each
  commit.
- **Streamlit stays running** (port 8500) until every page has moved. It is the reference
  and the fallback.
- Today's uncommitted Streamlit fixes on `redesign/research-desk` (scrolling, fit, sorting,
  pinned refresh) are committed separately before this work starts, so Streamlit stays
  usable meanwhile.

## 6. What the user decided

| Decision | Choice |
|---|---|
| Framework | Next.js in the existing `web/` app, for the long term |
| Design | v2 Research Desk style on **all 10 pages** |
| Flow | Same as Streamlit: same nav, pages, order and labels |
| Rollout | Each page goes live as soon as it is done |
| First page | Home (after the frame) |
| Main screen | Laptop (1280×600 effective); phone second |
| Update step lists | May add the new save-results scripts to `_PRECOMPUTE_FOR` (`master_dashboard.py`), `run_all.py` and `refresh_data.bat` |
| Streamlit update buttons | Disable them once the Next.js update buttons work, so only one app can start an update |

## 7. The design

### 7.1 Visual system (copy from Streamlit v2, do not reinvent)

The source of truth is `core/ui_components.py` (`COMPONENT_CSS`) plus the reference
screenshots in `C:\Users\User\Documents\Stocks\.playwright-mcp\streamlit-ref\`:
`01-home.png` … `10-compare-past-results.png`, captured 2026-11-07 at 1440px wide.

Tokens (light theme, default):

| Token | Value | Use |
|---|---|---|
| `--rd-bg` | `#F7F6F3` | warm off-white page background |
| `--rd-card` | `#FFFFFF` | cards and tables |
| `--rd-sidebar` | `#F2F1EC` | sidebar |
| `--rd-line` | `#E7E4DD` | hairline borders |
| `--rd-hover` / `--rd-active` | `rgba(29,29,27,.04)` / `#E8E6E0` | row hover / selected row and nav item |
| `--rd-text` / `-2` / `-muted` | `#1D1D1B` / `#45443F` / `#77756E` | text levels |
| gain / loss / warn / info | `#12805C` / `#C2364B` / `#A86200` / `#1F6F78` | numbers and pills |
| matching `*-bg` tints | `#E4F3EC` / `#FBE8EB` / `#FBF0DF` / `#E3F0F1` | pill backgrounds |

Dark theme values are in the same file under `[data-theme="dark"]`. Font: Inter 400/500/
600/700, with tabular numbers for all figures. Type scale 11/12/13/14/16/22 px. Spacing
4/8/12/16/24/32 px. Radius 10px for cards and 6px for small items.

Components to rebuild as React components, one for each Streamlit helper:
`status_pill`, `change_pill` (tinted, with ↗/↘ arrow), `context_bar`, `kpi` / `kpi_row`,
`validation_checklist`, `empty_state`, `section_label`, `data_table` (two-line company
rows: name, plus ticker and strategy underneath, with a selected-row state), `headline`,
`stat_bar`, the `rd-list` right-rail list (title + value or pill per row), and the
`rd-page` title + subtitle block.

### 7.2 Frame (built first)

- **Sidebar**, about 260–272px, collapsible. From top to bottom: the brand block
  ("Strategy / BACKTESTER"), then the nav in the same groups, order, labels and icons as
  Streamlit:
  - Home
  - STRATEGIES: Browse strategies, Create a strategy
  - FIND STOCKS: Monthly stock rotation, Newly listed stocks (IPO), Price strength
    (Momentum), After earnings (PEAD), Stocks to review
  - EVALUATE: Understand past trades, Compare past results
- **Pinned to the sidebar bottom** (always visible, even on a short screen): the
  "Research only…" note, the data-age line ("All saved data updated today" or "Oldest saved
  data: PEAD, 65 days old"), an **Update all data** button and an **Update one strategy**
  menu (Monthly, IPO, Momentum, PEAD, plus a "Last updated" list). Updates run the same
  steps as Streamlit's `_PIPELINES` + `_PRECOMPUTE_FOR` in `master_dashboard.py`, through
  the existing job routes, and show live progress.
- The nav scrolls on its own when the screen is short. The page area scrolls separately.
  No nested scroll boxes inside a page.
- **Not-yet-built pages:** their nav item opens the Streamlit app at
  `http://localhost:8500`, marked with a small "opens old app" hint. Streamlit has no
  per-page URLs, so the link lands on Streamlit's Home.
- The top-of-page "Market context and price-data status" expander, and the research
  notice shown on strategy pages, become shared frame pieces.
- Light/dark theme follows the system, with a manual toggle.
- Phone: the sidebar becomes a slide-over menu.

### 7.3 Pages and order

Each page keeps its Streamlit sections and order, restyled to v2. Use the Streamlit
function as the content spec and the screenshot as the layout reference.

| # | Page (nav label) | Streamlit source | Reference |
|---|---|---|---|
| 1 | Home | `render_home` | `01-home.png` |
| 2 | Monthly stock rotation | `render_monthly` | `04-…` |
| 3 | Price strength (Momentum) | `render_momentum` | `06-…` |
| 4 | Newly listed stocks (IPO) | `render_ipo` | `05-…` |
| 5 | After earnings (PEAD) | `pead_dashboard.py` (called from `main`) | `07-…` |
| 6 | Stocks to review | `render_suggestions` | `08-…` |
| 7 | Understand past trades | `render_insights` | `09-…` |
| 8 | Compare past results | `render_history` | `10-…` |
| 9 | Browse strategies | `render_strategy_library` | `02-…` |
| 10 | Create a strategy | `render_add_strategy` (6-step wizard) | `03-…` |

Home is first (the user's choice). Pages 2–10 follow in this order; this order is my
suggestion and the user may reorder it.

Home, as an example of the level of fidelity required:
- Title "Overview" with a subline ("14 candidates in saved files · research only, nothing
  here places orders") and, on the right, a trend-filter pill and "Prices up to … ·
  updated …".
- Left (about 2/3): a **Candidates** table with an All / Monthly / IPO / Momentum filter.
  Two-line company rows; Status pill; Key measure; Move pill. Clicking a row opens that
  company on its strategy page. Below it: "Growth of each strategy" with a 1Y/3Y/5Y/Max
  switch and a line chart, then the per-strategy change list.
- Right rail (about 1/3): Market (trend filter, Nifty close, 50-day and 200-day averages,
  from 52-week high, in this state), Strategies (clickable list with per-year return),
  Saved data (age per strategy).
- Below 1200px wide, the right rail stacks under the main column.

### 7.4 Layout rules (the reason for this project)

- Design every page at **1280×600** first, then check 390px (phone), 1024px and 1920px.
- Tables: full width of their column; headers wrap at spaces; numbers do not wrap. Too
  many columns for the width → hide low-priority columns at narrower widths. Each table
  definition lists column priorities. A table may scroll sideways inside itself only on a
  phone.
- Long tables show the first 15 rows plus a "Show all N rows" toggle, never an inner
  scroll box. Column sort works on every data table, with an ▲/▼ indicator.
- The list + detail panel layout (Monthly, Momentum, IPO): the detail panel stays in view
  (sticky) while the list scrolls with the page, and stacks below the list under 1200px.
- No fixed-height containers that trap the mouse wheel.

### 7.5 Data

- **Saved files:** read through `web/lib/data/strategies.ts`, extended where a page needs a
  file it does not read yet, server-side, in React Server Components or route handlers.
  Numbers are formatted exactly as Streamlit formats them (same decimals, ₹ and % style).
- **Results Streamlit computes live in Python** while drawing a page:
  `_scan_all_breakouts`, `_scan_recent_breakouts`, `_verify_past_trades`,
  `_loss_free_holding`, `_build_report` (insights), `_regime_snapshot`,
  `_monthly_close_history`, `_compute_full_indicators`. These stay in Python. They are
  either:
  - **saved after each data update** by a small new script (like the existing
    `precompute_*.py`) that calls the same Python functions and writes JSON for the UI,
    which is the default for anything shown on page load; or
  - **run on demand** through a job route, for interactive actions (single-stock
    backtest, "drill into any signal" price chart for one ticker).
  No formula is re-implemented in TypeScript. If a page needs a small derived value that
  already exists in `web/lib` (for example `indicators.ts`), check that it matches
  Python's output on the same input before using it.
- **Parity check:** for each page, a test compares the key numbers the Next.js page shows
  with the Streamlit/Python values for the same files, such as KPIs, candidate lists, CAGR
  and win rate. *My call:* a small Python harness imports the same functions the
  Streamlit page uses (or the new save-results scripts, which call those same functions),
  writes their values for the current files, and the web test compares against that
  output. Where Streamlit computes a number inline inside page code, the harness calls the
  nearest Python function and the gap is listed in the test. No frozen snapshot files.
- **If a Streamlit number looks wrong:** do not copy it and do not silently fix it. Report
  the cause to the user and wait for confirmation before changing any displayed number.
  This is the user's standing rule from the redesign.

### 7.6 Updates ("Update all data" and "Update one strategy")

- They run the **same full step lists as Streamlit**: `_PIPELINES` (downloads → parquet
  sync → backtest) plus `_PRECOMPUTE_FOR`, downloads included, per strategy. One strategy
  failing does not stop the others. The failed step and its error tail are shown, as
  Streamlit does. Time limits must allow long downloads; the builder picks them.
- The new save-results scripts (§7.5) are added to `_PRECOMPUTE_FOR`, `run_all.py` and
  `refresh_data.bat` (approved), so results stay fresh whichever app or the nightly job
  runs the update.
- Once the Next.js update buttons work (the frame milestone), Streamlit's update buttons
  are disabled (approved). They are replaced by a note saying updates run from the new
  app. That way only one app starts updates and two jobs cannot write the same files at
  once. The nightly `refresh_data.bat` job stays as it is.

## 8. Testing and "done" for each page

Before building, each of the 8 pages not yet in v2 gets a **mockup approved by the user
first**, following the user's rule that a design direction is approved before code. Home
and Monthly already have an approved v2 look, so they need no mockup.

A page is done when:
1. It matches its reference screenshot's content and section order in v2 style (for the
   8 pages, its approved mockup), and the user approves it.
2. At 1280×600, 1024, 1920 and 390: no horizontal page scroll; nothing outside the
   viewport; mouse-wheel scrolling reaches the bottom of the page and the sidebar; no
   trapped scroll. This is checked with Playwright, like the Streamlit audit done on
   2026-11-07.
3. The parity test passes. `npm test` and `pytest` pass.
4. Its nav item points to the new page instead of Streamlit.

## 9. Left to the builder

- Component file structure, naming, and Server vs Client components.
- Whether to keep, adapt or delete each existing `web/` page and component. Keep its data
  and job plumbing; drop its visual layer.
- Chart implementation, using `lightweight-charts` (already installed) for price and
  equity lines.
- Exact column priorities for hiding at narrow widths, per table.
- Port number for the Next.js dev server (default 3000).

## 10. Open items

- PEAD currently has 0 candidates after today's refresh. The page needs a clear empty
  state.
- Header-click sorting was broken in Streamlit until today and was fixed there. In
  Next.js it is built in from the start.
