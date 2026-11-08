# My portfolio + reliable sell monitoring (Momentum Edge): Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stages 2–3 of the user's 2026-11-08 request ("Improve the Momentum Edge / Price Strength strategy … I previously bought stocks … and still hold them. The app does not give me a sufficiently clear, persistent view of what I bought and when I should sell"). This plan:
- fixes the stale-signal bug;
- adds a persistent transaction ledger ("My portfolio");
- evaluates every open holding against the Momentum Edge exit rules whenever data is updated, with an auditable evaluation history, alerts, STALE / DATA UNAVAILABLE states and clearly labelled reconstructed history.

Stages 4–6 (dated DVM entry, volume and exit-rule research with walk-forward testing and costs) get their own plan after this one.

**Architecture:**
- **Python owns the numbers.**
  - `core/portfolio.py` does pure ledger accounting (FIFO lots).
  - `core/exit_monitor.py` evaluates one holding with the existing Momentum Edge exit rules, reusing `momentum_edge_backtest.compute_indicators` and `CFG`, so no formulas are copied.
  - `portfolio_monitor.py` evaluates all open holdings, appends to an audit log and writes `ui_portfolio.json`.
- **Node owns writes from the UI.** API routes append validated transactions to `portfolio/ledger.json` (atomic write + lock) and run the monitor as a job.
- **The desk page `/portfolio`** shows holdings, actions, history and forms.

**Tech Stack:** Python 3 stdlib + pandas (existing), Next.js 16.2.7, TypeScript, Vitest. No new packages.

**Spec / authority:** the user's message (this conversation, 2026-11-08) supersedes the earlier "UI-only, strategy read-only" rule *for this work*. The original Momentum Edge rules stay available unchanged as the baseline. PEAD is untouched.

## Facts established in Stage 1 (code inspection, 2026-11-08)

- "Price strength (Momentum)" is only the UI label of Momentum Edge (`momentum_edge_backtest.py` CFG; same output files).
- Baseline exit rules:
  - Hard stop: today's close < entry × (1 − 0.15) → exit at that close (`run_backtest` ~886-891).
  - Otherwise, close < today's EMA220 → exit queued for the next session's open (~894-896).
  - The hard stop wins when both fire. Signals use completed daily bars.
- No code tracks user holdings or checks exits outside the backtest. The live page is an entry scanner, so held stocks that leave it get no sell check.
- **Stale-signal bug.**
  - `_parquet_is_fresh` (master_dashboard.py:3983) probes only RELIANCE.NS. `_compute_momentum_signals_from_parquet` then trusts all 1,242 cache files.
  - About 279 of those files are older than their CSV, some by months, because the backtest skips tickers that fail its liquidity filters and never refreshes their cache.
  - Example: BHARATGEAR is shown at ₹134.25 "Watch Zone" from a cache ending 2026-07-03, while the CSV close on 2026-11-06 is ₹98.54.
- **User holdings**, verified in `data/universe/combined_universe.csv`, all with prices to 2026-11-06:
  - ANDHRSUGAR.NS — The Andhra Sugars Limited.
  - APLAPOLLO.NS — APL Apollo Tubes Limited.
  - BHARATGEAR.NS — Bharat Gears Limited. Fails `min_avg_volume` (100k), so it is outside the backtest universe.
  - MAHLOG.NS — Mahindra Logistics Limited.
  - PFOCUS.NS — Prime Focus Limited.
  - TMCV.NS — "Tata Motors Limited", ISIN INE1TAE01010, data from 2025-11-12. Identity awaiting user confirmation. Has fewer than `min_bars` (252), so it is outside the backtest universe.
  - JAYBARMARU.NS — Jay Bharat Maruti Limited. Awaiting user confirmation.
- No purchase records exist in the project.

## Decisions (Claude's calls; reversible)

1. **Storage: plain JSON files under `portfolio/`** in the project root. The folder is git-ignored, so user data never enters git. Daily rolling backups go to `portfolio/backups/` (keep 14).
   - `portfolio/ledger.json`: `{version:1, transactions:[…]}`, append-only. Corrections are `VOID` transactions referencing the original id; nothing is deleted.
   - `portfolio/evaluations.jsonl`: one JSON line per holding per evaluation run.
   - `portfolio/alerts.json`: the current alert per holding, plus acknowledgement records.
   - `portfolio/settings.json`: charge rates with an "as of" date, warning bands and monitor settings.

   The stdlib makes SQLite possible, but JSON matches the project's existing file-based pattern and is easy to inspect and back up.
2. **Transaction schema.**
   - Fields: `{id (uuid4), type: "BUY"|"SELL"|"VOID", symbol: "APLAPOLLO.NS", exchange: "NSE"|"BSE", trade_date: "YYYY-MM-DD", price, quantity (int > 0), charges (≥ 0, as paid), strategy: "momentum_edge"|"other", strategy_version (CFG hash from momentum_edge_backtest._cfg_hash(CFG)), signal_ref: string|null, notes, voids: id|null, created_at (ISO, local), source: "manual"|"signal"|"import"}`.
   - Validation:
     - the symbol must exist in `combined_universe.csv` with a matching exchange;
     - a SELL cannot exceed the open quantity on its date;
     - future dates are rejected.
   - A generated signal never creates a transaction. "I bought this" only pre-fills the form.
3. **Accounting: FIFO lots.**
   - Average price = cost of open lots ÷ open quantity, including buy charges in cost. It is shown both with and without charges.
   - Realised P&L per SELL comes from the FIFO-matched lots, net of that sell's charges.
   - Unrealised P&L = (last close − FIFO lot price) × qty − allocated buy charges.
   - Holding duration counts from the oldest open lot.
   - Estimated exit costs come from `settings.charges`. They are shown separately and never mixed into the incurred charges.
4. **Charge estimate defaults** (Indian equity delivery; the user can edit them in `settings.json`; labelled "as of 2026-11-08, verify with your broker" and shown as estimates):
   - brokerage 0;
   - STT 0.1% on buy and sell;
   - exchange transaction charge NSE 0.00297%, BSE 0.00375%;
   - SEBI fee 0.0001%;
   - stamp duty 0.015% on buy;
   - GST 18% on (brokerage + exchange + SEBI);
   - DP charge ₹15.93 per scrip per sell day.
5. **Exit evaluation per open holding (strategy `momentum_edge`).**
   - **Data:** load bars from the same CSV folders the scanner uses (`data/nse_bse`, `momentum_edge_data`, `data`). Indicators come from `momentum_edge_backtest.compute_indicators(df, CFG)`; only `close` and `ema220` are used, so the formulas are shared, not copied.
   - **Completed-bar rule:** a bar dated today counts only after 15:45 IST. Before that, the latest completed bar is the previous one; the incomplete bar is ignored and labelled.
   - **Entry price for the stop:** the position's FIFO average buy price (excluding charges), the same basis as the backtest's entry_price.
   - **Priority on the latest completed bar:**
     1. **DATA UNAVAILABLE:** no file, or fewer than 220 bars to form the EMA (labelled "insufficient history"). TMCV has 250 bars, so its EMA is formed but immature.
     2. **STALE:** the last bar is 1 or more sessions older than the last completed session, taken from the `^NSEI` file's last date.
     3. **EXIT (hard stop):** close < avg × 0.85. Text: "Exit rule triggered at today's close; earliest action is the next session. A stop is a trigger, not a guaranteed price; gaps can fill worse."
     4. **EXIT (220 EMA break):** close < EMA220. Text: "The model exits at the next session's open."
     5. **REVIEW:** close within 3% above the EMA220, or within 3% above the hard-stop level. Bands come from `settings`; advisory, labelled "not a model exit".
     6. **HOLD.**
   - **REDUCE** is reserved for an *experimental* profit-taking rule (exit-research targets). It is off by default, labelled experimental when on, and never a baseline action.
   - **Reported levels:**
     - hard-stop price;
     - EMA220 value and distance %;
     - highest close since the first buy, and the drawdown from it;
     - last close and date;
     - 20-day volume ratio (today's volume ÷ the trailing 20-day average excluding today);
     - data freshness.
   - **Reconstruction:** walk the completed bars after the first buy date. The first bar where rule 3 or 4 would have fired is recorded as `reconstructed_first_exit {date, rule, close, level}`, labelled "Reconstructed from saved prices — no alert existed at the time". Alerts the monitor actually raised are stored separately.
   - **Other strategies:** "No automated exit rules for this strategy" (status REVIEW, labelled). Never silently HOLD.
6. **Alerts:** an alert is created only when a holding's action changes (dedupe key = symbol + action + rule + trigger bar date). Acknowledging records `{alert_id, acknowledged_at}` and never records a sale.
7. **When monitoring runs:**
   - `portfolio_monitor.py` is appended last to every strategy's update path, plus `run_all.py` and `refresh_data.bat`.
   - A "Check holdings now" button runs it on its own.
   - **There is no background scheduler in this app.** The page says so: "Checks run when data is updated or when you press Check now. Nothing runs while the app is closed." It also shows the last successful evaluation time.
8. **Stale-signal fix.**
   - In `_compute_momentum_signals_from_parquet`, skip any cached ticker whose last date is more than 1 day older than its CSV.
   - Those tickers are computed from CSV through the existing CSV path for that ticker list. If that is not cleanly possible, they are excluded and counted in a new funnel key `stale_cache`.
   - Signals also carry the bar date used (`Data as of`).
   - This edits protected master_dashboard.py functions, which the user's request authorises. The baseline checksums are re-recorded **after** the diff is reported to the user, with a note in `.superpowers/baseline/`.
   - The backtest engine's trading rules are not changed.

## Global Constraints

- Branch `redesign/nextjs-desk`. Commit after every task (conventional commits, ending with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`).
- No new packages. No broker orders. Do not invent purchase data. Never display "guaranteed", "no loss" or "100%".
- The baseline Momentum Edge rules (CFG, `run_backtest`) are unchanged. PEAD is untouched.
- User data (`portfolio/`) is git-ignored and never deleted by code (VOID only).
- Every write is atomic (`.tmp` + `os.replace` / `fs.rename`). Node writes hold a file lock (reuse `web/lib/job-lock.ts` or a sibling lock for the ledger).
- **API input validation on the server:**
  - types and ranges;
  - symbol in the universe;
  - ISO dates, no future dates;
  - quantity an integer > 0;
  - SELL ≤ open quantity;
  - string lengths ≤ 500.

  CSRF protection: JSON content type plus a same-origin check, as `/api/update` does.
- **Tests:**
  - Python baseline 319.
  - Web baseline 344 (`PYTHON_BIN=../.venv/Scripts/python.exe PYTHONUTF8=1 npx vitest run --exclude tests/glossary.test.ts`).
  - `tsc` clean; lint adds nothing to the existing 2 errors + 3 warnings.

## Review Focus

1. **A holding absent from the scanner** (BHARATGEAR, TMCV) is still evaluated and gets a status. Pinned in Task 3.
2. **Partial sells and multiple buys:** FIFO realised/unrealised P&L and the open quantity are exact, and a SELL beyond the open quantity is rejected. Pinned in Tasks 2 and 5.
3. **Stale, missing or short history:** the status is STALE or DATA UNAVAILABLE, never an old HOLD. Pinned in Task 3.
4. **Persistence across restarts:** a ledger written by the API is read by a fresh Python process and a fresh server start. A corrupt file is never overwritten; it is copied to `backups/` and the UI shows an error. Pinned in Tasks 2 and 5.
5. **Signal timing:** today's incomplete bar is ignored, reconstructed exits use only bars after the buy date, and the hard stop beats the EMA on the same bar. Pinned in Task 3.

---

### Task 1: Stale-signal fix (per-ticker cache freshness)

**Files:** `master_dashboard.py` (`_compute_momentum_signals_from_parquet` and/or its caller ~4366-4372; `_parquet_is_fresh` kept for compatibility); test `tests/test_momentum_cache_freshness.py`.

- [ ] Failing test: a temp cache dir with two tickers, one up to date and one ending 120 days before its CSV. The stale ticker is not built from the cache, its signal row (if any) has the CSV's last date, and `funnel['stale_cache']` counts it.
- [ ] Implement per Decision 8. Add a `Data as of` column (bar date) to the signals DataFrame, and check that `precompute_momentum_signals.py` writes it to `momentum_edge_signals.csv` (an additive column).
- [ ] Re-run `precompute_momentum_signals.py`. BHARATGEAR's row must reflect the 2026-11-06 data or be absent. Record the before/after signal counts in the report.
- [ ] Run the full pytest. `verify_protected.py` will show master_dashboard function drift: record the exact function names in the report, and do NOT update checksums (the controller reports to the user first).
- [ ] Commit `fix(momentum): ignore stale per-ticker indicator cache in the live scanner`.

### Task 2: `core/portfolio.py` — ledger, validation, FIFO accounting

**Files:** `core/portfolio.py`, `tests/test_portfolio_ledger.py`; `.gitignore` adds `portfolio/`.

**Produces:**
- `load_ledger(path) -> list[dict]`: raises `LedgerCorrupt` on bad JSON or a bad version.
- `append_transaction(path, tx) -> dict`: validates, assigns id/created_at, writes atomically and takes the daily backup.
- `validate_transaction(tx, ledger, universe) -> list[str]`.
- `positions(ledger) -> dict[symbol, Position]`, where `Position(symbol, exchange, open_qty, lots[{buy_id, date, price, qty, charges_alloc}], avg_price, avg_price_incl_charges, realised_pnl, realised_charges, first_buy_date, closed: bool)`.
- `estimated_exit_costs(symbol, exchange, qty, price, settings) -> dict` (itemised).
- `load_settings(path)`, with the defaults of Decision 4.
- `universe_index() -> dict[symbol, {name, exchange, isin}]` from `combined_universe.csv`.

- [ ] Tests:
  - two buys + a partial sell: FIFO realised exact to the paisa, plus open qty and avg;
  - full close: closed=True, realised kept;
  - VOID of a buy: the position is recomputed;
  - SELL > open is rejected;
  - an unknown symbol is rejected;
  - a future date is rejected;
  - restart: write, then a fresh `load_ledger`, gives an equal result;
  - corrupt file: `LedgerCorrupt`, with the file untouched;
  - the backup is created once per day;
  - charge estimate itemisation for a ₹1,00,000 NSE sell.
- [ ] Implement. Commit `feat(portfolio): transaction ledger with FIFO accounting`.

### Task 3: `core/exit_monitor.py` + `portfolio_monitor.py`

**Files:** `core/exit_monitor.py`, `portfolio_monitor.py`, `tests/test_exit_monitor.py`, `tests/test_portfolio_monitor.py`. Update paths: append `portfolio_monitor.py` last to every `_PRECOMPUTE_FOR` list, `run_all.py`, `refresh_data.bat` and `web/lib/desk/update-steps.ts`; extend `tests/test_streamlit_updates_moved.py`.

**Produces:**
- `evaluate_holding(position, bars_df, nifty_last_date, now, settings) -> Evaluation`, with the Decision 5 fields: `action, rule, explanation, levels{…}, last_close, last_bar_date, data_status: "OK"|"STALE"|"DATA UNAVAILABLE", incomplete_bar_ignored: bool, reconstructed_first_exit|null, volume_ratio20, drawdown_from_peak, held_days`.
- `portfolio_monitor.main()`:
  - evaluates all open positions;
  - appends to `evaluations.jsonl`;
  - updates `alerts.json` with dedupe;
  - writes `ui_portfolio.json`: `{version:1, generated_at, monitor:{last_run, ok, errors[]}, positions:[…with evaluation…], closed:[…], alerts:[…], settings_summary, scheduler: "none"}`;
  - exits 0 with errors listed per holding, and non-zero only if the ledger is corrupt.

- [ ] Tests, on synthetic bars:
  - a hard stop on bar T gives EXIT (hard stop);
  - close < EMA220 gives EXIT (EMA);
  - when both fire, the hard stop wins;
  - within 3% of the EMA gives REVIEW;
  - normal gives HOLD;
  - a last bar 3 sessions behind Nifty gives STALE;
  - no file or < 220 bars gives DATA UNAVAILABLE;
  - a bar dated today at 11:00 IST is ignored (the previous bar is used and flagged);
  - reconstruction finds the first trigger after the buy date and ignores bars on or before the buy date;
  - a holding not in `momentum_edge_signals.csv` is still evaluated;
  - alert dedupe: two runs in the same state give one alert, and an action change gives a new alert;
  - acknowledgement does not change positions;
  - strategy "other" gives a labelled REVIEW.
- [ ] Implement. Real run with an empty ledger: writes `ui_portfolio.json` with 0 positions. Commit `feat(portfolio): exit monitor for every open holding with audit log and alerts`.

### Task 4: Portfolio API routes

**Files:**
- `web/lib/desk/portfolio.ts`: server loader for `ui_portfolio.json`, ledger read/write helpers mirroring the Python validation, and a lock.
- `web/app/api/portfolio/transactions/route.ts`: GET list; POST add (BUY/SELL/VOID).
- `web/app/api/portfolio/alerts/ack/route.ts`: POST.
- `web/app/api/portfolio/check/route.ts`: POST; runs `portfolio_monitor.py` through the existing job runner; 409 when busy.
- `web/app/api/portfolio/universe/route.ts`: GET search `?q=`, returning ≤ 20 matches of symbol/name/exchange.
- Tests: `web/tests/portfolio-api.test.ts`.

Python's validation is authoritative. The Node POST writes the transaction, then runs `portfolio_monitor.py --validate-only <tmp>` before committing the write. If Python rejects it, the request returns 400 with Python's messages. This keeps one validation source.

- [ ] Tests:
  - POST of a valid BUY gives 201 and the file contains it;
  - SELL > open gives 400;
  - bad JSON gives 400, and a cross-site request gives 403;
  - concurrent POSTs serialise (lock);
  - ack writes alerts only;
  - a universe search for "jay bharat" returns JAYBARMARU.NS.
- [ ] Commit `feat(web): portfolio API for transactions, alerts and checks`.

### Task 5: `/portfolio` page

**Files:**
- `web/app/portfolio/page.tsx`.
- `web/components/desk/portfolio/*`: `holdings-table.tsx`, `holding-rail.tsx`, `transaction-form.tsx`, `alerts-list.tsx`, `monitor-status.tsx`.
- `web/lib/desk/portfolio-text.ts`: formatters, tones and copy.
- Nav item "My portfolio" (icon `Briefcase`) at the top of FIND STOCKS.
- A Momentum rail button "I bought this" linking to `/portfolio?add=SYMBOL&signal=…`.
- Tests: `web/tests/desk-portfolio.test.ts`, covering the mappers plus render tests for an empty ledger, a STALE row, an EXIT row with its rule text, and the reconstructed label.

Page sections, in order:
1. **Header:** "My portfolio". Sub: "What you bought, and what the model's exit rules say now."
2. **Monitor status:** the last successful check time, a "Check holdings now" button and the scheduler notice (Decision 7).
3. **Alerts:** unacknowledged action changes, each with an Acknowledge button.
4. **Holdings table**, with columns:
   - Company / symbol · exchange
   - Qty
   - Avg price
   - Last close (date)
   - Unrealised P&L (₹ and %)
   - Realised P&L
   - Held (days)
   - Drawdown from peak
   - Action pill: HOLD gain, REVIEW warn, REDUCE info, EXIT loss, STALE / DATA UNAVAILABLE muted
   - Rule
5. **Rail for the selected holding:**
   - a plain-language explanation and the exact rule;
   - levels: hard stop ₹, EMA220 ₹ and distance %, highest close since buy, drawdown;
   - volume ratio;
   - data as of;
   - estimated exit costs (itemised, labelled as an estimate);
   - charges paid;
   - lots;
   - transaction history, with a "Void" action behind a confirm dialog;
   - evaluation history (last 20);
   - the reconstructed first exit (labelled);
   - a "DVM scores: not recorded" placeholder (Stage 4).
6. **Forms.** Each shows server validation errors.
   - Add purchase: universe search, exchange, date, price, quantity, charges, strategy (default Momentum Edge), notes. Pre-filled from `?add=`.
   - Record sale: holding, date, price, quantity ≤ open, charges.
7. **Closed positions** table.
8. **Holdings pending your details:** while the ledger is empty, a card lists the 7 user-named holdings with their verified symbols, with TMCV and JAYBARMARU flagged "please confirm", and an "Add purchase" button for each. **The page does not create any transaction for them.**

- [ ] Implement, then check in the browser at 1280×600. Check free memory first, and stop only a dev server you started.
  - Add a test BUY for a fake date, then VOID it, so the ledger ends with net zero positions and the VOID is visible in history.
  - Check now runs.
  - There are no console errors.

  Save screenshots to `C:/Users/User/Documents/Stocks/.superpowers/audit/portfolio-*.png`. The fit audit adds `/portfolio`.
- [ ] Commit `feat(web): My portfolio page with holdings, sell actions and alerts`.

### Task 6: Verification and handoff

- Run the full pytest, vitest (PYTHON_BIN, PYTHONUTF8), tsc and lint.
- Run verify_protected and list the drift (run_all.py + the Task 1 functions).
- Run the fit audit for `/`, `/monthly`, `/momentum` and `/portfolio`.
- Update `MEMORY.md` (git-ignored, on disk) with the portfolio location, how monitoring runs, the stale-cache fix, and the open user dependencies (purchase details, TMCV/JAYBARMARU confirmation).
- Commit `test: portfolio monitoring verification`.
