# PRD — Stock Strategy Hub: Professional Upgrade

*(Facelift · Extensible Strategies + Backtesting · Faster Load)*

## 1. Summary

We are upgrading the existing Streamlit "Strategy Hub" (`master_dashboard.py`, port 8500)
on three fronts, without changing what the product *does*:
1. **Facelift** — make every screen look like a professional enterprise trading tool
   (Bloomberg/TradingView/Zerodha/Stripe), keeping density and all features.
2. **Add-on: more strategies with backtesting** — let the user add new strategies and
   backtest them through the existing wizard, end-to-end, like the built-in ones.
3. **Add-on: faster load** — cut page-load time so screens open near-instantly.

Existing features, data, logic, and navigation stay intact. We polish, extend, and speed up
— we do not redesign the product.

---

## 2. Contacts

| Name | Role | Comment |
|------|------|---------|
| Rahul (rahulsenadhi) | Owner / Product & Eng | Final sign-off per screen and per pillar. Approves the pilot before rollout. |
| Claude (Sr. Designer + Eng) | Design & implementation | Recreates screens 1:1, wires extensibility, lands speedups. |
| End users (self + future viewers) | Traders reading strategy output | Need fast, dense, trustworthy screens; must not have to relearn anything. |

---

## 3. Background

- **What this is:** The Hub runs four built-in strategies (Monthly Rotation, IPO Edge,
  Momentum Edge, PEAD) plus a working **custom-strategy wizard**, and shows signals,
  screeners, backtests, and charts. It already has a mature design system (OKLCH color
  tokens, light/dark, IBM Plex type, a custom `_modern_table`, Plotly charts, and reusable
  components).
- **Why now:**
  - The product is feature-complete and trusted. The presentation should now match the
    rigor of the analysis.
  - Extensibility is **~90% built** — a 7-step wizard, a generic backtest engine
    (`generic_backtest.py`), and a strategy registry (`strategies_index.json`) already
    exist. Only the last-mile wiring is missing, so finishing it is low-risk and high-value.
  - Load time is the main daily friction: some screens recompute heavy signals on every
    open. Recent precompute work fixed Momentum; the same pattern can fix the rest.
- **Hard lesson carried in:** A prior restyle that added airy "cards" and inflated
  whitespace was **rejected** for hurting density. A density-preserving fintech-SaaS polish
  was **accepted**. This PRD keeps density first.

---

## 4. Objective

**Objective:** Make the Hub look professional, let the user add and backtest new strategies
as first-class citizens, and make it load fast — all without changing existing behavior.

**Why it matters:** A polished, fast, extensible tool is trusted, used daily, and grows
with the user's ideas instead of needing code edits for every new strategy.

**Key Results (SMART):**

*Pillar 1 — Facelift*
1. **Zero functional regression** — 100% of features, flows, and nav work identically,
   verified screen-by-screen against the current build.
2. **Density preserved** — every restyled table shows ≥ today's rows/columns per screen;
   no card-bloat, no whitespace inflation.
3. **One token system** — color/type/spacing/border/table styling unified across 100% of
   screens, both light and dark; no one-off styles.

*Pillar 2 — Extensible strategies*
4. **End-to-end custom strategy** — a user can create a strategy in the wizard, run its
   backtest, see it in the Library and a results page, **and re-run it from a refresh
   button**, with no code changes and no hard-coded edits.
5. **Parity surfaces** — custom strategies appear in Library, "Last Updated", and (where
   applicable) Suggestions/Insights, the same as built-ins.

*Pillar 3 — Fast load*
6. **Cold page load ≤ ~3s** for every primary screen when precompute is current (today some
   screens take 20–52s); **no screen recomputes a full-universe scan on open**.
7. **No redundant recompute** on theme toggle or tab switch.

---

## 5. Market Segment(s)

We build for **the trader who reviews strategy output and must read dense numeric data
quickly, trust it, and occasionally test a new idea.**

- **Jobs to be done:**
  - "Scan signals/screeners/backtests fast and with confidence."
  - "Try a new strategy idea and see if it would have worked — without writing code."
- **Constraints:**
  - Users are not developers → plain-English language, glossary, tooltips must remain.
  - Data is dense → respect density, don't fight it.
  - Desktop-first, local (:8500); light + dark themes both supported.
  - Backtests run as local subprocesses on historical OHLCV (no live trading).

---

## 6. Value Proposition(s)

**Jobs/needs addressed:** read a lot at a glance; trust the output; keep every existing
capability; add and test new strategies without code; never wait 30–50s for a screen.

**Customer gains:**
- Calmer, more legible, consistent interface (clear hierarchy, aligned tabular numbers,
  consistent green/red/neutral meaning).
- New strategies become first-class — created, backtested, refreshed, and compared like the
  built-ins.
- Screens open fast.

**Pains avoided:** no relearning (nav/layouts unchanged); no density loss; no broken trust
(no logic/data changes); no code edits to add a strategy; no long waits.

**Where we win vs. alternatives (the current state):** same information and same logic, but
sharper, faster, and extensible. *Current Product → Professional Version, not → Different
Product.*

**Value Curve:** dial **down** whitespace, decoration, and per-load recompute; dial **up**
alignment, consistency, tabular precision, extensibility, and speed.

---

## 7. Solution

### 7.1 UX / Prototypes

- **Facelift:** screen-by-screen 1:1 recreation with the upgraded token system. Owner
  provides each screen; we rebuild it element-for-element in the same positions.
  **Pilot one screen → approve → roll out** in nav order.
- **Extensible strategies:** the wizard flow (Basics → Universe → Indicators → Entry → Exit
  → Risk → Save & Run) stays as-is; we make its output behave like a built-in everywhere
  (Library card refresh, sidebar/Last-Updated parity, results page).
- **Fast load:** invisible to the user except that screens open faster; no UX/flow change.
- **Navigation:** unchanged across all three pillars.

### 7.2 Key Work Items

**Pillar 1 — Facelift (visual only):**
1. Consolidate design tokens (color/type/spacing/radius/border/shadow) into one source of
   truth; verify light + dark parity. *(Anchor: CSS block `master_dashboard.py:168–2131`.)*
2. Typography hierarchy + tabular-mono numerals everywhere numeric.
3. Dense table polish via `_modern_table` (sticky headers, hover, right-aligned numbers,
   status pills) — keep current density. *(Anchor: `2099–2128`, `4788–4856`.)*
4. KPI/metric strips, sidebar shell, charts (Plotly theme), controls, and empty/loading/
   error states unified. *(Anchors: pills `4382–4388`; chart theme `49–57`, `111–119`.)*

**Pillar 2 — Extensible strategies + backtesting (additive wiring; no feature removal):**
5. **Registry-driven refresh** — replace hard-coded strategy lists with iteration over
   `strategies_index.json` so custom strategies get a refresh button and "Update ALL"
   includes them. *(Gap anchors: `master_dashboard.py:4699`, `4629–4665`, `5741–5751`.)*
6. **Generic results loader** — a single "load any strategy's equity/trades/KPIs" path
   reading `strategies/{id}_*.csv`, so custom strategies render in Library + results pages
   like built-ins. *(Gap anchors: hard-coded paths `2329`, `3283`, `2870`.)*
7. **Last-Updated + Library parity** — show custom strategies' freshness and a per-card
   re-run. *(Gap anchors: `5760–5763`, `8313–8401`.)*
8. **More indicators in the wizard/DSL** — expand beyond the current 5 (`rsi_14`, `atr_14`,
   `sma_50`, `sma_200`, `volume_z`) toward the deferred set (`sue`, `piotroski`, `pb`,
   `mcap_cr`, etc.) as feasible. *(Anchors: wizard `8503–8520`; engine `generic_backtest.py:46–91`.)*
9. **(Optional) DSL upgrades** — lookback windows / helper functions, if the owner wants
   richer entries. Flagged as stretch.

**Pillar 3 — Faster load (behavior-preserving optimizations):**
10. **Precompute IPO signals** (mirror the momentum precompute) so `load_ipo()` reads a
    CSV instead of running `_compute_ipo_signals()` live (~20–30s today).
    *(Anchors: `load_ipo` `2324`/`2348`; pattern: `precompute_momentum_signals.py`.)*
11. **Lazy per-page data load** — only load the data the selected page needs, instead of
    loading Monthly+IPO+Momentum on every view. *(Anchor: `main()` `9001–9004`.)*
12. **Cache shared reads** — benchmark and strategy index loaded once/cached.
    *(Anchors: `_benchmark_first` `4164/7553/2521`; index `5798`.)*
13. **Cheaper freshness check** — `_parquet_is_fresh` should compare metadata/mtime, not
    read full files. *(Anchor: `3833–3857`.)*
14. **(Optional) DuckDB breakout scan** — replace per-ticker loop in `_scan_recent_breakouts`
    (~36s) with one aggregate query. Stretch. *(Anchor: `4056–4131`.)*

### 7.3 Technology

- **Target:** Streamlit `master_dashboard.py` (:8500) and its existing `core/` modules
  (`data_io`, `store`, `kpis`, `leaderboard`, `ranking`), `generic_backtest.py`, and the
  `strategies/` + `strategies_index.json` registry.
- **Out of scope:** the separate local Next.js app in `web/` (future/parallel effort).
- No major new dependencies expected. DuckDB and parquet are already in use.

### 7.4 Assumptions (to validate)

- **A1:** Target is the Streamlit `:8500` app, not Next.js `web/`.
- **A2:** "Professional enterprise" = dense fintech-terminal aesthetic (the previously
  accepted direction), not airy marketing cards.
- **A3:** Light + dark themes both stay supported after the facelift.
- **A4:** Screen-by-screen, owner sign-off per screen; pilot before rollout.
- **A5:** "Add more strategies" means **finishing the existing wizard/engine wiring** so
  custom strategies reach parity — not building a new strategy framework.
- **A6:** Faster load is achieved by precompute + caching + lazy loading, preserving exact
  outputs (numbers identical to today).

---

## 8. Release

Relative timeframes; no fixed dates. Pillars can run in parallel but each ships in stages.

- **Stage 0 — Confirm scope:** lock A1 (Streamlit target) and A5 (extensibility = finish
  wiring). Pick the pilot screen.
- **Stage 1 — Facelift pilot:** restyle one screen end-to-end (likely Dashboard or Momentum
  screener); owner approves look + density + zero-regression. Then roll the token system
  across remaining screens in nav order, each verified vs. its current counterpart.
- **Stage 2 — Fast-load quick wins:** precompute IPO signals, cache benchmark/index, cheap
  `_parquet_is_fresh`, lazy per-page load. Measure cold load before/after.
- **Stage 3 — Extensible strategies:** registry-driven refresh + generic results loader +
  Library/Last-Updated parity; verify a brand-new custom strategy goes create → backtest →
  refresh → compare with no code edits.
- **Stage 4 — Stretch:** expand indicators/DSL; DuckDB breakout scan; consistency pass
  (token drift, theme parity, states). Confirm all Key Results.
- **Future / not committed:** mirror the facelift onto the Next.js `web/` app if brought in
  scope.

---

### Open questions for the owner
1. **A1** — confirm the Streamlit `:8500` app is the target (not Next.js `web/`).
2. **A5** — confirm "add more strategies" means finishing the existing wizard wiring (vs. a
   new framework).
3. Pillar order — do all three together, or facelift first, then speed, then extensibility?
