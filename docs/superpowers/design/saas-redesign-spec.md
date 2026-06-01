# SaaS Dashboard Redesign Spec — Algo Trading Hub

**Date:** 2026-06-01
**Owner:** rahul.senadhi
**Design system source:** `ui-ux-pro-max` Pro Max — "Exaggerated Minimalism" + dark cinematic fintech pattern (Linear/Vercel/Notion family)
**Existing tokens:** `master_dashboard.py:112-198` (OKLCH SuperDesign tokens, light override at 200-280)
**Spec linkage:** `1-product-vision.md`, `2-strategy-canvas.md`, `6-prioritized-roadmap.md`

---

## Design Principles (locked)

1. **Linear / Vercel / Notion-grade polish** — flat, high-contrast, tight typography, no decoration
2. **Inter font** (already in `master_dashboard.py:110`) — keep
3. **One primary CTA per page** — green accent (`--success` oklch(0.696 0.170 162.480))
4. **No emoji as icons** in new screens — use SVG (Lucide via inline SVG strings; no extra deps)
5. **Tabular numerals** for all KPIs (`font-feature-settings: "tnum"`) — prevents jitter in tables
6. **8px spacing rhythm** — gap-2 (8px), gap-4 (16px), gap-6 (24px), gap-8 (32px)
7. **Card radius:** `var(--radius)` = 0.625rem (already in tokens) — keep
8. **Subtle shadows** — `var(--shadow-sm)` only; no big drop-shadows
9. **Light + Dark parity** — both themes tested before ship (light tokens already at 200-280)
10. **No animations >300ms** — micro-interactions only

---

## New Page 1 — Strategy Library

### ASCII Mockup

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  📚  Strategy Library                                          [+ New strategy]│
│  Browse, compare, deploy your audit-graded strategies                          │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                                │
│  [ All ▾ ]  [ Status: All ▾ ]  [ Sort: Last run ▾ ]   [🔍 Search...]          │
│                                                                                │
│  ┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐│
│  │ Monthly Rotation   🟢│  │ Momentum Edge      🟢│  │ IPO Edge           🟢││
│  │ Quant · Live          │  │ Momentum · Live       │  │ Breakout · Live       ││
│  │                      │  │                      │  │                      ││
│  │  CAGR    +22.49%  ↗  │  │  CAGR    +12.16%  ↗  │  │  CAGR    +10.19%  →  ││
│  │  Sharpe   1.54        │  │  Sharpe   0.84        │  │  Sharpe   1.39        ││
│  │  DD     -11.43%      │  │  DD     -26.35%      │  │  DD      -5.68%      ││
│  │  [▁▂▃▅▆▇█▇▆▇█] 4yr   │  │  [▂▃▅▄▆▇█▆▇█▇] 10yr  │  │  [▂▃▅▆▇▆▇█▇▆] 2yr    ││
│  │                      │  │                      │  │                      ││
│  │  Last: Today 12:42   │  │  Last: Today 13:01   │  │  Last: Today 13:18   ││
│  │  [ Open ]  ⋯           │  │  [ Open ]  ⋯           │  │  [ Open ]  ⋯           ││
│  └──────────────────────┘  └──────────────────────┘  └──────────────────────┘│
│                                                                                │
│  ┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐│
│  │ PEAD               📄│  │ Custom: Q&Mom      🔬│  │ + Add another        ││
│  │ Earnings · Paper      │  │ Multi-factor · Test   │  │                      ││
│  │                      │  │                      │  │   Build a new        ││
│  │  CAGR    +26.10%  ⚠  │  │  CAGR     N/A         │  │   strategy           ││
│  │  Sharpe  15.26 *      │  │  Sharpe  N/A          │  │                      ││
│  │  DD      -3.12%      │  │  DD      N/A          │  │   [ Get started → ]   ││
│  │  [▂▃▄▅▆▆▇█▅▆▇] 2yr   │  │  Draft — not run      │  │                      ││
│  │                      │  │                      │  │                      ││
│  │  Last: Today 02:27   │  │  Saved 3 days ago    │  │                      ││
│  │  [ Open ]  ⋯           │  │  [ Open ]  ⋯           │  │                      ││
│  └──────────────────────┘  └──────────────────────┘  └──────────────────────┘│
└──────────────────────────────────────────────────────────────────────────────┘

Status chips:  🟢 Live      📄 Paper      🔬 Research      ⏸ Paused

Card states (hover): scale 1.005, border becomes brighter, shadow elevates
Card actions (⋯ menu): View detail, Edit, Run backtest, Duplicate, Archive, Delete
```

### Streamlit implementation

`pead_dashboard.py`-style render function `_page_strategy_library`. Uses 3-col grid via `st.columns(3, gap='medium')`. Each card is a `st.container(border=True)`.

```python
# In render_sidebar() — add new entry between Momentum Edge and PEAD:
'📚  Strategy Library',

# In main() dispatch:
elif 'Library' in page:
    render_strategy_library()


# At module level:
def render_strategy_library():
    """Strategy Library — grid of all saved strategies."""
    # Header
    st.markdown("""
        <div class="lib-header">
            <div>
                <h1>Strategy Library</h1>
                <p class="lib-subtitle">Browse, compare, deploy your audit-graded strategies</p>
            </div>
        </div>
    """, unsafe_allow_html=True)

    col_action, _ = st.columns([1, 4])
    with col_action:
        if st.button('+ New strategy', type='primary', use_container_width=True):
            st.session_state['_page_override'] = 'add_strategy'
            st.rerun()

    # Filter bar
    f1, f2, f3, f4 = st.columns([2, 2, 2, 4])
    with f1:
        type_filter = st.selectbox('Type', ['All', 'Quant', 'Momentum', 'Breakout', 'Earnings', 'Custom'], label_visibility='collapsed')
    with f2:
        status_filter = st.selectbox('Status', ['All', 'Live', 'Paper', 'Research', 'Paused'], label_visibility='collapsed')
    with f3:
        sort_by = st.selectbox('Sort', ['Last run', 'CAGR', 'Sharpe', 'Name'], label_visibility='collapsed')
    with f4:
        search = st.text_input('Search', placeholder='🔍  Search strategies...', label_visibility='collapsed')

    # Load strategies
    strats = _load_all_strategies()  # returns List[dict]
    strats = _filter_and_sort(strats, type_filter, status_filter, sort_by, search)

    # Grid — 3 cols
    for row_start in range(0, len(strats), 3):
        cols = st.columns(3, gap='medium')
        for col, strat in zip(cols, strats[row_start:row_start + 3]):
            with col:
                _render_strategy_card(strat)

    # Trailing "Add new" placeholder card if last row not full
    remainder = 3 - (len(strats) % 3 or 3)
    if remainder < 3:
        cols = st.columns(3, gap='medium')
        for i in range(remainder):
            with cols[3 - remainder + i]:
                _render_add_card()


def _render_strategy_card(strat: dict) -> None:
    status = strat['status']  # 'Live', 'Paper', 'Research', 'Paused'
    status_chip = {
        'Live':     '<span class="chip chip-live">🟢 Live</span>',
        'Paper':    '<span class="chip chip-paper">📄 Paper</span>',
        'Research': '<span class="chip chip-research">🔬 Research</span>',
        'Paused':   '<span class="chip chip-paused">⏸ Paused</span>',
    }[status]

    delta_arrow = '↗' if strat['cagr'] > 0 else '↘'
    delta_class = 'pos' if strat['cagr'] > 0 else 'neg'

    with st.container(border=True):
        st.markdown(f"""
            <div class="strat-card">
              <div class="strat-card-head">
                <div class="strat-name">{strat['name']}</div>
                <div class="strat-status">{status_chip}</div>
              </div>
              <div class="strat-subtype">{strat['type']} · {status}</div>
              <div class="strat-kpis">
                <div class="kpi"><span class="kpi-label">CAGR</span>
                     <span class="kpi-val {delta_class}">{strat['cagr']:+.2f}%  {delta_arrow}</span></div>
                <div class="kpi"><span class="kpi-label">Sharpe</span>
                     <span class="kpi-val">{strat['sharpe']:.2f}</span></div>
                <div class="kpi"><span class="kpi-label">Max DD</span>
                     <span class="kpi-val neg">{strat['max_dd']:+.2f}%</span></div>
              </div>
            </div>
        """, unsafe_allow_html=True)

        # Sparkline
        _render_sparkline(strat['equity_curve'])

        st.markdown(f"""
            <div class="strat-footer">
              <span class="last-run">Last: {strat['last_run_str']}</span>
            </div>
        """, unsafe_allow_html=True)

        b1, b2 = st.columns([3, 1])
        with b1:
            if st.button('Open', key=f"open_{strat['id']}", use_container_width=True):
                st.session_state['_active_strategy'] = strat['id']
                st.rerun()
        with b2:
            st.popover('⋯').markdown(
                '\n'.join([
                    '[Edit](#)',
                    '[Run backtest](#)',
                    '[Duplicate](#)',
                    '[Archive](#)',
                    '[Delete](#)',
                ])
            )


def _render_sparkline(equity_series: pd.Series) -> None:
    """Tiny inline plotly sparkline (60 × 28 px-ish), no axes, no legend."""
    import plotly.graph_objects as go
    fig = go.Figure(go.Scatter(
        y=equity_series.values, mode='lines',
        line=dict(color='oklch(0.696 0.170 162.480)', width=1.5),
        fill='tozeroy', fillcolor='rgba(34, 197, 94, 0.10)',
    ))
    fig.update_layout(
        height=40,
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(visible=False), yaxis=dict(visible=False),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True, config={'staticPlot': True})
```

### CSS additions (append to existing `<style>` block in master_dashboard.py)

```css
/* ── Strategy Library tokens ────────────────────────────────────────────── */
.lib-header {
    display: flex; align-items: end; justify-content: space-between;
    margin-bottom: 24px; padding-bottom: 16px;
    border-bottom: 1px solid var(--border);
}
.lib-header h1 {
    font-size: 32px; font-weight: 700; letter-spacing: -0.025em;
    margin: 0; color: var(--foreground);
}
.lib-subtitle {
    font-size: 14px; color: var(--muted-foreground);
    margin: 4px 0 0 0;
}

/* Strategy cards */
.strat-card { padding: 4px 4px 12px 4px; }
.strat-card-head {
    display: flex; align-items: start; justify-content: space-between;
    gap: 8px;
}
.strat-name {
    font-size: 16px; font-weight: 600; letter-spacing: -0.01em;
    color: var(--foreground); line-height: 1.2;
}
.strat-subtype {
    font-size: 12px; color: var(--muted-foreground);
    margin-top: 4px; text-transform: capitalize;
}

/* Status chips */
.chip {
    display: inline-flex; align-items: center; gap: 4px;
    font-size: 11px; font-weight: 500;
    padding: 2px 8px; border-radius: 999px;
    border: 1px solid var(--border);
    background: var(--card);
    line-height: 1.4; white-space: nowrap;
}
.chip-live     { color: oklch(0.696 0.170 162.480); border-color: oklch(0.696 0.170 162.480 / 0.4); }
.chip-paper    { color: oklch(0.623 0.214 259.815); border-color: oklch(0.623 0.214 259.815 / 0.4); }
.chip-research { color: oklch(0.708 0 0); }
.chip-paused   { color: oklch(0.625 0.245 27.325); border-color: oklch(0.625 0.245 27.325 / 0.4); }

/* KPIs inside cards */
.strat-kpis {
    display: grid; grid-template-columns: 1fr 1fr 1fr;
    gap: 12px; margin: 16px 0 12px 0;
}
.strat-kpis .kpi { display: flex; flex-direction: column; gap: 2px; }
.kpi-label {
    font-size: 11px; color: var(--muted-foreground);
    text-transform: uppercase; letter-spacing: 0.06em;
}
.kpi-val {
    font-family: var(--font-mono);
    font-size: 14px; font-weight: 600;
    font-feature-settings: "tnum";       /* tabular figures */
    color: var(--foreground);
}
.kpi-val.pos { color: oklch(0.696 0.170 162.480); }
.kpi-val.neg { color: oklch(0.625 0.245 27.325); }

.strat-footer {
    display: flex; align-items: center; justify-content: space-between;
    margin: 6px 0 8px 0;
    font-size: 11px; color: var(--muted-foreground);
}

/* Card hover */
[data-testid="stContainer"]:hover .strat-card {
    /* nothing — Streamlit wraps; rely on the border element itself */
}

/* Add-new placeholder card (dotted border) */
.add-card {
    border: 1.5px dashed var(--border) !important;
    background: transparent !important;
    text-align: center; padding: 28px 16px;
    transition: border-color 150ms ease, background 150ms ease;
}
.add-card:hover {
    border-color: var(--success) !important;
    background: oklch(0.696 0.170 162.480 / 0.04) !important;
}

/* Filter bar */
div[data-testid="stSelectbox"] > div, div[data-testid="stTextInput"] input {
    border-radius: var(--radius-md);
    border-color: var(--border);
}
```

---

## New Page 2 — Add Strategy (Wizard)

### ASCII Mockup

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  ←  Back to Library                              Step 3 of 5  ●●●○○             │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                                │
│  Create new strategy                                                           │
│  Define your entry, exit, and sizing rules                                     │
│                                                                                │
│  ┌──── Step indicator ─────────────────────────────────────────────────────┐ │
│  │   1                2                3                4                5    │ │
│  │  ──●────────────●────────────●────────────○────────────○──                │ │
│  │  Basics       Universe     Entry rules    Exit rules    Sizing & Save     │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                                │
│  ┌──── Step 3: Entry rules ─────────────────────────────────────────────────┐│
│  │                                                                            ││
│  │  Choose input mode:   [● Formula DSL]  [○ Rule builder]                    ││
│  │                                                                            ││
│  │  Enter formula (uses pandas-eval syntax):                                  ││
│  │  ┌─────────────────────────────────────────────────────────────────────┐ ││
│  │  │  sue > 2 AND piotroski >= 7 AND pb < pb_sector_median                │ ││
│  │  └─────────────────────────────────────────────────────────────────────┘ ││
│  │                                                                            ││
│  │  Available columns: ticker, sector, sue, piotroski, pb, pb_sector_median, ││
│  │  rsi_14, atr_14, sma_50, sma_200, volume_z, mcap_cr                       ││
│  │                                                                            ││
│  │  💡 Tip: This signal fires on a strict positive earnings beat with a      ││
│  │     healthy balance sheet, at a discount to sector peer P/B.              ││
│  │                                                                            ││
│  │  ✓ Formula valid — would trigger ~12 events/yr on Nifty 200               ││
│  │                                                                            ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                                │
│                        [ ← Back ]       [ Skip ]       [ Next: Exit rules → ] │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Wizard step contents

| Step | Title | Inputs | Validation |
|---|---|---|---|
| 1 | Basics | Name (text, required), Description (textarea), Type chip (Quant / Momentum / Breakout / Earnings / Custom) | name unique vs existing |
| 2 | Universe | Radio: Nifty 50 / Nifty 200 / Nifty 500 / Sector / Custom CSV | If Custom: validate CSV columns |
| 3 | Entry rules | Mode toggle: Formula DSL or Rule builder (chip cards); textarea or rule rows | Live-validate formula via dry-run on a small sample |
| 4 | Exit rules | Multi-select: Time-based (N days), Next earnings, Hard stop (% loss), Trailing stop (% from peak); each with numeric input | At least one exit rule required |
| 5 | Sizing & Save | Position sizing: Equal weight (cap N positions) / Volatility-target / SUE-weighted; Initial cash; Then [Save as Research] or [Save + Run Backtest] | Cash > 0 |

### Streamlit implementation

```python
def render_add_strategy():
    """5-step wizard for creating a new strategy."""
    if '_wizard_step' not in st.session_state:
        st.session_state['_wizard_step'] = 1
        st.session_state['_wizard_data'] = {}

    step = st.session_state['_wizard_step']
    data = st.session_state['_wizard_data']

    # Header with back + progress
    h1, h2 = st.columns([1, 4])
    with h1:
        if st.button('← Back to Library'):
            st.session_state['_wizard_step'] = 1
            st.session_state['_wizard_data'] = {}
            st.session_state['_page_override'] = 'library'
            st.rerun()
    with h2:
        st.markdown(
            f'<div class="step-pill">Step {step} of 5</div>',
            unsafe_allow_html=True,
        )

    # Step indicator
    _render_step_indicator(step)

    # Step body in bordered container
    with st.container(border=True):
        if step == 1:
            _step_basics(data)
        elif step == 2:
            _step_universe(data)
        elif step == 3:
            _step_entry(data)
        elif step == 4:
            _step_exit(data)
        elif step == 5:
            _step_sizing_save(data)

    # Footer nav
    b1, b2, b3, b4 = st.columns([1, 1, 1, 2])
    with b1:
        if step > 1 and st.button('← Back'):
            st.session_state['_wizard_step'] -= 1; st.rerun()
    with b2:
        if step < 5 and st.button('Skip'):
            st.session_state['_wizard_step'] += 1; st.rerun()
    with b4:
        next_label = ['Next: Universe →', 'Next: Entry rules →', 'Next: Exit rules →',
                      'Next: Sizing →', 'Save & Run Backtest'][step - 1]
        if st.button(next_label, type='primary', use_container_width=True):
            if _validate_step(step, data):
                if step == 5:
                    _save_strategy(data)
                    _run_backtest(data)
                    st.session_state['_page_override'] = 'library'
                else:
                    st.session_state['_wizard_step'] += 1
                st.rerun()


def _render_step_indicator(active: int) -> None:
    steps = ['Basics', 'Universe', 'Entry rules', 'Exit rules', 'Sizing & Save']
    html = '<div class="step-indicator">'
    for i, label in enumerate(steps, start=1):
        state = 'done' if i < active else ('active' if i == active else 'todo')
        html += f'<div class="step step-{state}">'
        html += f'<div class="step-dot">{i}</div>'
        html += f'<div class="step-label">{label}</div>'
        html += '</div>'
        if i < len(steps):
            html += f'<div class="step-line {"line-done" if i < active else "line-todo"}"></div>'
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)


def _step_entry(data: dict) -> None:
    st.markdown('### Entry rules')
    st.caption('Define when to enter a position')

    mode = st.radio('Mode',
                    ['Formula DSL', 'Rule builder'],
                    horizontal=True,
                    key='entry_mode')

    if mode == 'Formula DSL':
        data['entry_formula'] = st.text_area(
            'Formula',
            value=data.get('entry_formula', ''),
            placeholder='e.g., sue > 2 AND piotroski >= 7 AND pb < pb_sector_median',
            height=80,
        )
        st.caption('Available columns: ticker, sector, sue, piotroski, pb, '
                   'pb_sector_median, rsi_14, atr_14, sma_50, sma_200, '
                   'volume_z, mcap_cr')

        # Live validation
        if data.get('entry_formula'):
            valid, msg, est_events = _dry_run_formula(data['entry_formula'])
            if valid:
                st.success(f"✓ Formula valid — would trigger ~{est_events} events/yr on Nifty 200")
            else:
                st.error(f"❌ {msg}")
    else:
        _render_rule_builder(data)
```

### CSS for wizard

```css
/* ── Wizard ────────────────────────────────────────────────────────────── */
.step-pill {
    display: inline-block;
    padding: 4px 12px; border-radius: 999px;
    background: var(--secondary);
    font-size: 12px; color: var(--muted-foreground);
    text-align: right; float: right;
}

.step-indicator {
    display: flex; align-items: center; gap: 8px;
    margin: 24px 0 32px 0;
}
.step {
    display: flex; flex-direction: column; align-items: center;
    gap: 8px; flex: 0 0 auto;
}
.step-dot {
    width: 32px; height: 32px;
    display: flex; align-items: center; justify-content: center;
    border-radius: 50%;
    font-size: 13px; font-weight: 600;
    border: 1.5px solid var(--border);
    background: var(--card);
    color: var(--muted-foreground);
    transition: all 150ms ease;
}
.step.step-active .step-dot {
    background: var(--success);
    border-color: var(--success);
    color: var(--background);
    box-shadow: 0 0 0 4px oklch(0.696 0.170 162.480 / 0.15);
}
.step.step-done .step-dot {
    background: var(--success);
    border-color: var(--success);
    color: var(--background);
}
.step-label {
    font-size: 11px; color: var(--muted-foreground);
    text-transform: uppercase; letter-spacing: 0.04em;
    font-weight: 500;
}
.step.step-active .step-label,
.step.step-done .step-label {
    color: var(--foreground);
}

.step-line {
    flex: 1; height: 2px; margin-top: -16px;
    background: var(--border);
}
.step-line.line-done {
    background: var(--success);
}
```

---

## Polish Pass — Apply Globally

Tightening that doesn't touch behavior:

| Selector | Change |
|---|---|
| `h1` site-wide | `font-size: 32px; font-weight: 700; letter-spacing: -0.025em;` |
| `h2` site-wide | `font-size: 22px; font-weight: 600; letter-spacing: -0.02em;` |
| `.kpi-val`, all table cells with numeric data | `font-feature-settings: "tnum"; font-variant-numeric: tabular-nums;` |
| `button[kind="primary"]` (Streamlit primary) | Background `var(--success)`, color `var(--background)` |
| Cards (`[data-testid="stContainer"][data-border="true"]`) | `box-shadow: var(--shadow-sm); border-radius: var(--radius);` |
| Sidebar radio active | Subtle 2px green-accent left bar (instead of just background change) |
| Page-title hr | Hairline (1px var(--border)), not double-line |
| All metric cards (current Streamlit `st.metric`) | Hide default thin chrome, use custom HTML for KPI tiles instead |

---

## Component Inventory After Redesign

| Component | Re-usable across pages | Location |
|---|---|---|
| `_render_strategy_card(strat)` | yes — used in Library + Suggestions | helpers section |
| `_render_sparkline(series)` | yes | helpers section |
| `_render_step_indicator(active, total)` | yes — Wizard + future onboarding | helpers section |
| `_kpi_tile(label, value, sub, trend)` | yes — replace `st.metric` site-wide | helpers section |
| `_status_chip(status_str)` | yes | helpers section |
| `_section_header(title, subtitle, action_button)` | yes | helpers section |

---

## Data Layer Additions

To support the Strategy Library, add a strategies registry. Single JSON file is fine for n=1:

`strategies_index.json` schema:
```json
{
  "strategies": [
    {
      "id": "monthly_rotation",
      "name": "Monthly Rotation",
      "type": "Quant",
      "status": "Live",
      "entry_rule": "auto",
      "exit_rule": "last-friday-monthly-rebalance",
      "universe": "nifty50",
      "trades_csv": "backtest_results.csv",
      "equity_csv": "monthly_rotation_equity.csv",
      "kpis_csv": null,
      "kpis_inline": {"cagr": 0.2249, "sharpe": 1.54, "max_dd": -0.1143},
      "last_run": "2026-06-01T12:42:00",
      "created": "2025-12-01"
    },
    {
      "id": "momentum_edge",
      "name": "Momentum Edge",
      "type": "Momentum",
      "status": "Live",
      ...
    }
  ]
}
```

Loader: `_load_all_strategies()` reads this JSON, returns a list of dicts. Builds the equity-curve sparkline from the referenced CSV. Caches via `@st.cache_data(ttl=60)`.

For user-created strategies (from the wizard): write to `strategies/<id>.json` with full DSL + run history.

---

## Accessibility & Anti-Patterns Check

| Check | Status |
|---|---|
| Color contrast ≥4.5:1 | Pass (OKLCH light=0.205 fg on 0.985 bg ≈ 12:1; dark inverse same) |
| No info conveyed by color alone | Pass (status chips have text label, KPI values have arrows) |
| Focus rings | Add `outline: 2px solid var(--ring); outline-offset: 2px;` on `:focus-visible` for all buttons/links |
| Tabular numerals on numeric cells | Specified |
| No emoji as structural icon in new screens | All cards use status text + chip; emoji only as decorative |
| Reduced-motion | Wrap card-hover scale + transitions in `@media (prefers-reduced-motion: no-preference)` |
| Card hover doesn't shift layout | `transform: scale(1.005)` — scale only, no layout move |
| Primary CTA per page | Strategy Library: "+ New strategy" (top-right). Wizard: "Next" / final "Save & Run". |
| Step indicator on multi-step | Yes (1–5 dots with labels) |
| Inline validation | Formula textarea live-validates |

---

## Implementation Order

1. **Phase A — Token + global polish** (1h)
   - Add new CSS block to existing `<style>` in master_dashboard.py
   - Apply `font-feature-settings: "tnum"` globally
   - Tighten heading scale

2. **Phase B — Strategy Library** (3h)
   - Add `strategies_index.json` with 4 existing strategies registered
   - Implement `_load_all_strategies` + `_render_strategy_card` + `_render_sparkline`
   - Add page to sidebar radio + dispatch
   - Test light + dark theme parity

3. **Phase C — Add Strategy wizard** (4h)
   - Implement 5 step functions + step indicator
   - Formula DSL: integrate `pandas.eval` dry-run validator
   - Save → `strategies/<id>.json` + auto-run backtest via subprocess
   - Test happy path with one new strategy

4. **Phase D — Per-strategy detail page** (2h, optional this round)
   - Click-through from card "Open" button
   - Reuses existing single-strategy renderers

5. **Phase E — Polish + accessibility** (1h)
   - Focus rings everywhere
   - Reduced-motion respect
   - Light/dark theme final pass

**Total: ~11h implementation. 2-3 evenings.**

---

## Out of Scope (intentional)

- Strategy edit-after-save (read-only for now; create new = duplicate + edit)
- Rule builder UI (formula DSL only in v1; Rule Builder is P2 from brainstorm)
- Drag-to-reorder strategy cards
- Compare 2-4 strategies side-by-side (brainstorm DE1 — defer)
- Strategy archiving / soft delete
- Permissions / sharing (n=1)
