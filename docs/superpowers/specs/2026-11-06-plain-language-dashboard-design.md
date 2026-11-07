# Plain-language Strategy Hub and PEAD redesign

Status: approved by the user with “ok implement” on 2026-11-06, including the public Mobbin reference fallback.

## Intent

The user wants the UX/UI redesigned using Mobbin MCP, especially PEAD, so a
person without finance or technical knowledge can understand every section.
The current Streamlit app at localhost:8500 remains the implementation target.

Success: a first-time reader can explain what a page is for, where its information
comes from, what each important number means, and what action is available next.

## Reference access

Mobbin MCP is not exposed in this session; a plugin search returned no matches.
Do not claim MCP access or inspection of authenticated Mobbin screens.
Public reference inspected:
https://mobbin.com/blog/what-good-dashboard-design-looks-like

Apply its broad patterns: a clear starting point, interpretation next to data,
and secondary detail revealed when requested. Exact layout decisions below are
our proposals, not findings from Mobbin or previously approved user preferences.
Implementation may use public references if the user accepts this fallback;
otherwise authenticated Mobbin research waits for the connection.

## Approaches

1. Keep the current layout and add explanations. Small change, but the user still
   has to work out the sequence and distinguish several kinds of saved output.
2. Guided overview with detailed views on demand. Clear starting point and plain
   explanations, with existing tables, filters and exports still accessible.
   Recommended and used for this proposed design.

Retain compact desktop layouts; avoid large decorative cards, repeated banners,
or a long tutorial before the user can inspect a company.

## Scope

- Shared navigation, page introductions, refresh feedback and theme consistency.
- Home: explain the available strategies and provide clear routes to review them.
- Suggestions: explain the source, proposed amounts and historical evidence.
- PEAD: redesign all existing sections and their explanatory copy as specified below.
- Other existing strategy, history and analytics pages: apply the shared vocabulary,
  section-purpose introductions and help pattern without changing their workflows.
- Preserve calculations, eligibility thresholds, screening defaults, ranking,
  data sources, CSV exports and underlying saved results.
- No new trades, watchlist persistence, broker connection, research results,
  data refresh or backtest runs as part of visual implementation/verification.
- Keep raw developer diagnostics accessible in a collapsed details area. Do not
  place shell commands or raw JSON in the normal reading path.

## Shared experience

Keep the current destinations and internal routing. Use plain primary labels
with existing strategy names as secondary identifiers, for example
“After earnings (PEAD)” and “Stocks to review (Suggestions).” Do not remove features.

Each page starts with its purpose, information date/status, and a useful next
action. A concise explanation accompanies each major section and chart:
“What this shows” and “How to read it.” Full formulas and raw data live in
“Calculation details,” while material uncertainty stays next to the affected result.

Use words as well as color for Meets rule / Does not meet rule / Information missing.
Use consistent typography, restrained borders, readable contrast, aligned numeric
columns and comfortable controls. Keep ordinary tables compact and scrollable.
Native widgets, dropdowns, data tables and charts must work with light/dark themes;
fix the present mismatch between the custom CSS toggle and native dark surfaces.
Choose a supported theme approach during implementation; avoid private frontend APIs.

Market context should explain the current rule result without implying that every
strategy uses the same entry restrictions. Preserve strategy-specific behavior.
The same distinction applies to saved research, simulated positions and actual
holdings: this app currently does not record broker holdings or place orders.

## PEAD first screen

Title: “After earnings: find companies to research”
Secondary label: “PEAD — Post-Earnings-Announcement Drift”

Intro: “This strategy looks for unusually strong company earnings, then checks
financial strength and price compared with book value. It studies whether prices
continue to move after results. A match is a starting point for research.”

Visible navigation:

    Overview | Find companies | Saved signals | Past performance | Results calendar

Overview is selected first. Show a three-step guide with working navigation:

    1. Find a company → 2. Understand its results → 3. Review the evidence

Place the clear data status above the guide. For the current saved failure:
“The last update failed. You can still explore previously saved results.”
Show last attempted update and saved results date range separately. Offer
“Update earnings data,” with error details below an expander if needed.
Never turn missing status fields into zero counts or treat an attempt as success.

An earnings event means one company's reported result; it is not a unique company.
Label event counts “Company results,” and only show company counts if explicitly
computed from unique tickers. Missing coverage is described, not silently excluded.

## Find companies and company detail

Keep the existing filter defaults: SUE -3, Piotroski 5, P/B 10, no sector restriction.
Use clear labels with technical aliases and nearby help. Put detailed filter
controls in an expandable area, with their active values summarized above results.

| Existing term | Primary label and explanation |
| --- | --- |
| EPS | Profit per share: company profit allocated to each share; negative means a loss per share. |
| SUE | Earnings strength versus recent history: compares the latest profit per share with the previous four periods, allowing for how variable they were. Not a percentage or a comparison with analyst forecasts. |
| Piotroski | Financial strength checks: how many of nine accounting checks passed. This strategy requires at least seven. It does not establish that a stock is safe. |
| P/B | Price compared with book value: market price divided by accounting value per share. The strategy compares it with the middle value among industry peers. Lower alone does not mean a good investment. |
| Decile 10 | Top earnings group: highest of ten ranked groups in the saved comparison set. |
| qualifies_long | Marked eligible in the saved run: a stored flag, distinct from passing today's exploratory filters. |

Rename visible table columns; keep the original column names in downloaded data.
Use company names only where a reliable existing local mapping exists; retain the
ticker and never guess names. A result row opens the corresponding earnings event
or is chosen through a clearly labeled event selector if native table selection
cannot preserve the existing behavior reliably.

Company detail follows this order:

1. Company/ticker, result date, reporting period and source/date limitations.
2. One-sentence summary computed from saved values, with separate missing inputs.
   Example using currently saved ONGC evidence: “Profit per share was 5.29,
   below the previous-four-period average of 6.50. It meets 1 of the 3 displayed
   strategy checks.” Render the actual values; this is not hardcoded stock copy.
3. Three explained rule rows: earnings rank, financial strength and relative book
   valuation. Each row shows its value, requirement, result and plain explanation.
4. Latest and prior earnings comparison. Show units only if supported by the source;
   keep unavailable fiscal-quarter labels and accounting basis explicitly unknown.
5. Extra checks from Trendlyne. Explain Durability, Valuation and Momentum. When
   data is absent, show one clear missing-data message, with the full 23-item
   checklist available on expansion. Never present missing evidence as a failed check.
6. “What to review next”: refresh old information, inspect missing evidence, and
   consider risks. Do not offer a nonfunctional Buy/Save button or imply a position exists.

Preserve the raw event table and calculation details behind expanders. Avoid
duplicating the full definition of every term throughout a single screen.

## Saved signals

Purpose: “Companies the strategy marked as candidates in a previous run.”
Make the run/date coverage visible. No saved rows means “No saved candidates
available,” with a reason when known; it does not mean no opportunities today.

The second section is “Positions in the simulation”: explain that these belong
to the model and are not purchases recorded in a brokerage account.
Retain CSV export and detailed rows, with friendly column labels and dates.

## Past performance

Purpose: “What happened when the rules were applied to saved historical data.”
Explain that this is a simulation; available reports have not verified costs,
historical data availability or performance on unseen periods.

| Current display | Proposed presentation |
| --- | --- |
| Equity chart | Simulated account value over time; describe axes and initial amount only when known from the saved data. |
| CAGR | Annualized growth: the constant yearly rate that would produce the same start-to-end change. |
| Max DD | Largest fall from a previous peak; explain as the worst saved decline before recovery, without implying an eventual recovery occurred. |
| Sharpe | Return relative to variability (Sharpe); secondary detail explaining that a higher value alone does not prove safety or future success. |
| Win Rate | Profitable trades: share of completed simulated trades that made money; not the chance the next trade wins. |
| SUE decile performance | Returns after results, by earnings-strength group; explain groups 1–10 and the saved 60-trading-day measurement. |
| Trades | Simulated trade history; explain entry, exit, time held and gain/loss. |

Show missing metrics as “Information unavailable,” never zero. Explain small samples
when counts are available. Do not calculate or invent new strategy performance.
Hide experimental holding-period recommendations under research details, with
their limitations adjacent to the number. Do not recommend a best holding period.

## Results calendar and industry view

“Saved company result dates” displays the dates actually available. The current
title claims “next 30 days” without filtering; remove that claim unless a genuine
date filter and date-coverage explanation are implemented.

“Earnings strength by industry” explains rows (industries), columns (calendar
quarters of result dates), values (average stored earnings-strength score), and
color (higher/lower versus recent history, not investment quality). Preserve
numbers and accessible text alongside color. Do not claim the last eight quarters
unless the displayed data is actually restricted to eight quarters.

## Home, suggestions and remaining sections

Home leads with “Choose what you want to research,” a one-sentence explanation of
each strategy, date coverage and a link to its screen. Historical performance
summaries remain available with clear simulation labels.

Suggestions becomes a review list: why each stock appears, proposed entry/stop/
target/allocation, what each term means, historical sample and missing evidence.
Explain a stop as a proposed exit level whose execution price is not guaranteed.
Explain allocation as a suggested portion of hypothetical capital, not deployed money.

Other strategy and analytics sections receive short purpose/readout explanations
and expandable technical detail; do not rename a calculation in a way that changes
its meaning. Replace unsupported “proof,” “safe,” or certainty language in touched
sections with an accurate description of the saved evidence.

## Builder decisions and verification

The builder chooses native Streamlit layout primitives, minimal reusable helpers,
exact spacing and responsive breakpoints. Do not migrate to Next.js or publish a site.
Use existing tests and local browser/CDP capabilities; do not refresh external data.

Verify filtering, event selection, empty feeds, malformed refresh status, a saved
failed refresh, missing checks, invalid dates and incomplete results. Preserve
numeric outputs and export schemas. Tests should find elements by semantic labels
rather than rely on metric position as the layout changes.

Inspect dark/light desktop and narrow layouts in a real browser: first screen,
company details, help, filters, tables, dropdowns, historical results and navigation.
Confirm working links/buttons, no page exceptions and no clipped controls.
Acceptance requires plain explanations beside every PEAD section; a glossary alone
does not satisfy the request. Save screenshots and a concise implementation handoff.
