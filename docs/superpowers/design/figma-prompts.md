# Figma Prompt Pack — NSE Strategy Hub (Streamlit dashboards)

**Goal:** generate design frames in **Figma Make / Figma AI**, then connect the file so Claude pulls them via the Figma MCP and translates the visual tokens into the existing `<style>` block in `master_dashboard.py`.

**Hard constraints (baked into every prompt):**
- Density-first. Linear / Vercel / Notion grade. No card bloat, no decoration, no hero illustrations.
- Fonts: **IBM Plex Sans** (UI) + **IBM Plex Mono** (all numbers/KPIs/tables).
- Tabular numerals on every number.
- 8px spacing rhythm (8 / 16 / 24 / 32).
- Card radius 10px, hairline 1px borders, subtle shadow only.
- Dark theme is primary; must also work in light.
- Status by text + chip, never color alone.

---

## Palette (paste into Figma as styles — hex maps 1:1 to the app's OKLCH tokens)

**Dark (primary)**
| Token | Hex | Use |
|---|---|---|
| background | `#171717` | page bg |
| card | `#212121` | panels, cards |
| surface-2 | `#2b2b2b` | nested/hover |
| foreground | `#fafafa` | primary text |
| muted-foreground | `#9a9a9a` | labels, captions |
| border | `#3a3a3a` | hairlines |
| success (emerald) | `#10b981` | positive, primary CTA |
| warning (amber) | `#f59e0b` | caution |
| info (blue) | `#3b82f6` | neutral accent |
| destructive (red) | `#ef4444` | negative, loss |
| chart purple | `#8b5cf6` | series 4 |
| chart cyan | `#06b6d4` | series 5 |

**Light**
| Token | Hex |
|---|---|
| background | `#fafafa` |
| card | `#ffffff` |
| foreground | `#1a1a1a` |
| muted-foreground | `#737373` |
| border | `#e3e3e3` |

---

## PROMPT 0 — Design system (run this FIRST in Figma Make)

```
Create a design system for a dense, professional fintech analytics dashboard
in the style of Linear, Vercel, and Notion. Dark theme primary, with a light
variant.

Typography: IBM Plex Sans for all UI text; IBM Plex Mono for every number,
KPI value, and table cell, with tabular (monospaced) figures. Type scale:
H1 32/700 letter-spacing -0.025em; H2 22/600 -0.02em; body 14/400;
caption/label 11-12/500 uppercase letter-spacing 0.06em.

Color styles (create as named styles):
- bg #171717, card #212121, surface-2 #2b2b2b
- text #fafafa, muted text #9a9a9a, border #3a3a3a
- success #10b981, warning #f59e0b, info #3b82f6, danger #ef4444
- chart: #3b82f6 #10b981 #f59e0b #ef4444 #8b5cf6 #06b6d4

Spacing: 8px base rhythm (8/16/24/32). Card corner radius 10px. Borders 1px
hairline using border color. One subtle shadow style only (y1 blur3 black 10%).

Build these reusable components:
1. KPI tile — small label (uppercase 11px muted) above a large mono value;
   optional delta with up/down arrow colored success/danger. Tight padding.
2. Status chip — pill, 11px, dot + text label. Variants: Live (emerald),
   Paper (blue), Research (gray), Paused (amber).
3. Dense data table — 32px rows, hairline row dividers, mono numeric columns
   right-aligned, sticky header in muted uppercase, zebra off, hover row tint.
4. Sidebar nav item — icon + label, active state = 2px emerald left bar +
   subtle bg tint, not a full pill.
5. Section header — H2 title + muted subtitle on one line, optional single
   primary button (emerald) right-aligned, hairline divider below.
6. Sparkline card — KPI tile with a tiny filled area line chart (emerald,
   no axes, no legend) underneath.
7. Primary button (emerald bg, dark text) and secondary button (border only).

Deliver a light variant of every component using: bg #fafafa, card #ffffff,
text #1a1a1a, muted #737373, border #e3e3e3, same accents.
Keep everything flat and tight. No gradients, no large shadows, no emoji icons.
```

---

## PROMPT 1 — Strategy Hub overview (landing)

```
Design a dashboard overview screen "NSE Strategy Hub" using the design system.
Layout: left sidebar (240px) with nav items: Overview, Monthly Rotation,
Momentum Edge, IPO Edge, PEAD Strategy, Buy-Now Signals, Position Sizer,
Insights. Active item uses the 2px emerald left bar state.

Main area:
- Section header "Strategy Hub" + subtitle "4 live strategies · last refresh
  today 13:18" + theme toggle on the right.
- A row of 4 KPI tiles: Portfolio CAGR, Combined Sharpe, Max Drawdown,
  Open Positions. Mono values, deltas with arrows.
- Below, a 2-column grid (NOT bloated cards) of 4 strategy summary rows, each
  a compact sparkline card: name + status chip, three inline KPIs
  (CAGR / Sharpe / Max DD) in mono, a small emerald sparkline, and a single
  "Open" link. Tight 16px gaps.
Dense, scannable, one screen, no wasted vertical space.
```

---

## PROMPT 2 — Strategy detail / backtest view

```
Design a strategy detail screen (e.g. "Momentum Edge") using the design system.
- Section header with strategy name, status chip, and a primary "Run backtest"
  button.
- Row of 6 compact KPI tiles: CAGR, Sharpe, Sortino, Max DD, Win rate,
  Exposure. Mono values, tabular figures.
- A large equity-curve area chart (emerald line, faint fill, dark transparent
  bg, thin gridlines #ffffff at 10% opacity, mono axis ticks). Below it a
  smaller drawdown chart in red.
- A dense trades table below: columns Date | Ticker | Side | Entry | Exit |
  Return% | Hold days. Numeric columns mono + right-aligned, Return% colored
  success/danger, 32px rows, hairline dividers, sticky header.
Everything tight and aligned to the 8px grid.
```

---

## PROMPT 3 — Buy-Now signals (actionable)

```
Design a "Buy-Now Signals" screen using the design system. Purpose: show
today's actionable entries with confidence.
- Section header "Buy-Now Signals" + subtitle "As of today's close · paper
  account".
- A filter bar: strategy dropdown, confidence dropdown, search — compact,
  hairline inputs.
- A dense signal table: Ticker | Strategy | Signal | Confidence (a thin
  horizontal meter 0-100 with mono % label) | Suggested size | Entry zone |
  Stop. Confidence meter uses emerald→amber→red by level. 32px rows.
- A right-side detail drawer (360px) for a selected signal: large ticker,
  status chip, mono KPI tiles, a "why this fired" plain-English block, and a
  primary "Add to watchlist" button.
Dense, no card padding bloat.
```

---

## PROMPT 4 — PEAD Screener (table-heavy)

```
Design a "PEAD Screener" screen using the design system — this is a
data-dense screening table, the densest screen in the app.
- Section header "PEAD Screener" + subtitle "Post-earnings drift candidates".
- Filter row: SUE decile range, Piotroski min, P/B vs sector toggle, sector
  multiselect — all compact hairline controls on one line.
- A full-width dense table: Ticker | Sector | SUE | SUE decile | Piotroski |
  P/B | P/B vs sector | Earnings date | Drift since | Action. All numeric
  columns mono, right-aligned, tabular figures. Decile shown as a tiny 10-cell
  heat strip. 30px rows, sticky header, hover tint, hairline dividers.
- Footer: row count + "Export CSV" secondary button.
Maximize information density; minimize chrome.
```

---

## PROMPT 5 — Position Sizer + Insights

```
Design two screens using the design system.

(A) Position Sizer: a compact calculator panel — inputs (account size,
risk % per trade, entry, stop) as hairline fields on the left; outputs on the
right as mono KPI tiles (shares, position value, risk amount, % of account).
A small allocation donut. One primary "Apply" button. Single card, tight.

(B) Insights / trade analytics: a grid of small analytics tiles —
win/loss distribution histogram, returns by holding period bar chart,
monthly returns heatmap, equity vs benchmark line. Each in a compact card with
an H2 title and mono summary stat. Charts use the chart palette, dark
transparent bg, thin gridlines. 16px grid gaps, dense.
```

---

## Connect-back checklist (after you generate in Figma)

1. In Figma: keep frames named clearly (`Overview`, `Strategy Detail`, etc.).
2. Authorize the Figma MCP when Claude prompts (one-time OAuth).
3. Paste the **Figma file URL** (or a specific frame link) back to Claude.
4. Claude pulls each frame, extracts colors/type/spacing/component specs, and
   maps them onto the existing OKLCH tokens + `<style>` block in
   `master_dashboard.py` — translating, not pasting React.
5. Review per-screen in dark + light before commit.
```
