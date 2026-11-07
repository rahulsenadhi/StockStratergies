"""Presentation-only building blocks for the research-desk redesign.

Everything here formats values that the existing strategy code already
produced. Nothing in this module calculates, filters or changes financial
results. Builders return HTML strings so they can be unit-tested without a
running Streamlit app; callers render them with
``st.markdown(html, unsafe_allow_html=True)``. Every caller-supplied string is
HTML-escaped.
"""
from __future__ import annotations

from html import escape

import plotly.graph_objects as go

# ── Display thresholds (presentation only; they never change a result) ─────
LOW_SAMPLE_TRADES = 30          # below this, a KPI is labelled "small sample"
FRESH_MAX_DAYS = 7              # saved file counts as current up to 7 days
AGING_MAX_DAYS = 21             # 8-21 days old = ageing, older = stale

TONES = ("gain", "loss", "warn", "info", "muted")

CHECK_STATUS = {
    "not_tested": ("Not tested", "warn"),
    "not_modelled": ("Not modelled", "warn"),
    "known_risk": ("Known risk", "loss"),
    "partial": ("Partly covered", "info"),
    "done": ("Covered", "gain"),
}

# ── Chart colours for light mode (dark mode keeps the original figure) ──────
LIGHT_GRID = "rgba(23,32,51,0.10)"
LIGHT_ZERO = "rgba(23,32,51,0.35)"
LIGHT_TEXT = "#172033"

_DARK_LINES = {"#1a1f35", "#1e293b", "#2a2a2a", "#333", "#333333", "#3a4060", "#1c1c1c"}
_LIGHT_ON_DARK_TEXT = {"#e0e0e0", "#fafafa", "#e4e8f0", "#f1f5f9", "#ffffff", "#fff"}
_DARK_BACKGROUNDS = {"#1c1c1c", "#0f172a", "#111827", "#0e1223"}


def _check_tone(tone: str) -> str:
    if tone not in TONES:
        raise ValueError(f"unknown tone {tone!r}; expected one of {TONES}")
    return tone


# ── Small components ─────────────────────────────────────────────────────────

def status_pill(label: str, tone: str = "muted") -> str:
    """Compact status label, e.g. Live / Paper / Stale."""
    return f'<span class="rd-pill rd-pill--{_check_tone(tone)}">{escape(str(label))}</span>'


def context_bar(items: list[tuple[str, str]], basis: str | None = None) -> str:
    """One line that states what a result belongs to: strategy, universe, period, data date."""
    cells = "".join(
        f'<span class="rd-ctx__item"><span class="rd-ctx__label">{escape(str(k))}</span>'
        f'<span class="rd-ctx__value">{escape(str(v))}</span></span>'
        for k, v in items
    )
    note = f'<span class="rd-ctx__basis">{escape(basis)}</span>' if basis else ""
    return f'<div class="rd-ctx" role="group" aria-label="Result context">{cells}{note}</div>'


def kpi(label: str, value: str, *, sub: str | None = None, tone: str | None = None,
        sample_n: int | None = None, sample_unit: str = "trades") -> str:
    """A metric with its sample size. Small samples are labelled, never hidden."""
    low = sample_n is not None and sample_n < LOW_SAMPLE_TRADES
    cls = "rd-kpi rd-kpi--low-sample" if low else "rd-kpi"
    value_cls = f"rd-kpi__value rd-kpi__value--{_check_tone(tone)}" if tone else "rd-kpi__value"
    parts = [f'<div class="rd-kpi__label">{escape(label)}</div>',
             f'<div class="{value_cls}">{escape(str(value))}</div>']
    meta = []
    if sub:
        meta.append(escape(sub))
    if sample_n is not None:
        meta.append(f"{sample_n:,} {escape(sample_unit)}")
    if meta:
        parts.append(f'<div class="rd-kpi__meta">{" · ".join(meta)}</div>')
    if low:
        parts.append(f'<div class="rd-kpi__warn">Small sample: fewer than '
                     f'{LOW_SAMPLE_TRADES} {escape(sample_unit)}</div>')
    return f'<div class="{cls}">{"".join(parts)}</div>'


def kpi_row(kpis: list[str]) -> str:
    return f'<div class="rd-kpis">{"".join(kpis)}</div>'


def validation_checklist(checks: list[tuple[str, str, str]]) -> str:
    """List of research checks with an honest status. Status keys: see CHECK_STATUS."""
    rows = []
    for title, status, note in checks:
        if status not in CHECK_STATUS:
            raise ValueError(f"unknown status {status!r}; expected one of {tuple(CHECK_STATUS)}")
        label, tone = CHECK_STATUS[status]
        rows.append(
            f'<li class="rd-check"><span class="rd-check__title">{escape(title)}</span>'
            f'{status_pill(label, tone)}'
            + (f'<span class="rd-check__note">{escape(note)}</span>' if note else "")
            + "</li>"
        )
    return f'<ul class="rd-checks" aria-label="Validation status">{"".join(rows)}</ul>'


def empty_state(title: str, reason: str) -> str:
    """Explain why a panel is empty. Pair with a real st.button for the action."""
    return (f'<div class="rd-empty" role="status"><div class="rd-empty__title">{escape(title)}</div>'
            f'<div class="rd-empty__reason">{escape(reason)}</div></div>')


def section_label(text: str, meta: str | None = None) -> str:
    """Uppercase micro-label for a panel, with optional right-aligned meta (e.g. data date)."""
    m = f'<span class="rd-sec__meta">{escape(meta)}</span>' if meta else ""
    return f'<div class="rd-sec"><span class="rd-sec__text">{escape(text)}</span>{m}</div>'


def change_pill(value: float | None, *, fmt: str = "{:.2f}%", arrow: bool = True) -> str:
    """Tinted change chip: green up, red down, muted when missing. Value is shown, never altered."""
    if value is None or value != value:  # None or NaN
        return '<span class="rd-chg rd-chg--flat">—</span>'
    direction = "up" if value > 0 else "down" if value < 0 else "flat"
    shown = fmt.format(abs(value) if arrow else value)
    icon = {"up": "↗ ", "down": "↘ ", "flat": ""}[direction] if arrow else ""
    return f'<span class="rd-chg rd-chg--{direction}">{icon}{escape(shown)}</span>'


def _cell_html(kind: str, value) -> str:
    if kind == "name":
        title, sub = value if isinstance(value, (tuple, list)) else (value, "")
        sub_html = f'<span class="rd-name__sub">{escape(str(sub))}</span>' if sub else ""
        return f'<span class="rd-name"><span class="rd-name__title">{escape(str(title))}</span>{sub_html}</span>'
    if kind in ("html", "tag"):
        return str(value or "")          # caller-built markup from this module's builders
    return escape(str(value if value is not None else "—"))


def data_table(columns: list[dict], rows: list[dict], *, selected: str | None = None,
               sorted_key: str | None = None, empty: str = "No rows") -> str:
    """Research table: hairline rows, two-line names, right-aligned numbers, clickable rows.

    columns: [{"key", "label", "kind": name|num|text|html|tag}]; rows: [{"id", "cells": {key: value}}].
    "html" (right-aligned) and "tag" (left-aligned) cells must be markup produced by this module
    (e.g. change_pill, status_pill); all other cells are escaped.
    """
    def cls(col):
        c = ["rd-td"]
        if col.get("kind") in ("num", "html"):
            c.append("rd-td--num")
        if col.get("kind") == "name":
            c.append("rd-td--name")
        if col.get("hide_sm"):
            c.append("rd-col--hide-sm")
        if col["key"] == sorted_key:
            c.append("rd-col--sorted")
        return " ".join(c)

    head = "".join(f'<th class="{cls(c).replace("rd-td", "rd-th")}" scope="col">{escape(c["label"])}</th>'
                   for c in columns)
    if not rows:
        return (f'<div class="rd-table-wrap"><table class="rd-table"><thead><tr>{head}</tr></thead></table>'
                f'<div class="rd-table__empty">{escape(empty)}</div></div>')
    body = []
    for r in rows:
        rid = escape(str(r["id"]))
        sel = " rd-tr--sel" if selected is not None and str(r["id"]) == str(selected) else ""
        tds = "".join(f'<td class="{cls(c)}">{_cell_html(c.get("kind", "text"), r["cells"].get(c["key"]))}</td>'
                      for c in columns)
        body.append(f'<tr class="rd-tr{sel}" data-row="{rid}" tabindex="0">{tds}</tr>')
    return (f'<div class="rd-table-wrap"><table class="rd-table"><thead><tr>{head}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div>')


def headline(lead: str, emphasis: str, tone: str, meta: list[str] | None = None) -> str:
    """One plain-language sentence about the current situation, e.g. market trend + data age."""
    meta_html = "".join(f'<span class="rd-headline__meta">{escape(m)}</span>' for m in (meta or []))
    return (f'<div class="rd-headline"><div class="rd-headline__text">{escape(lead)} '
            f'<span class="rd-headline__em rd-headline__em--{_check_tone(tone)}">{escape(emphasis)}</span>'
            f'</div><div class="rd-headline__metas">{meta_html}</div></div>')


# ── Freshness ────────────────────────────────────────────────────────────────

def freshness_tone(age_days: int | None) -> str:
    if age_days is None:
        return "muted"
    if age_days <= FRESH_MAX_DAYS:
        return "gain"
    if age_days <= AGING_MAX_DAYS:
        return "warn"
    return "loss"


def freshness_label(age_days: int | None) -> str:
    if age_days is None:
        return "no saved file"
    if age_days == 0:
        return "updated today"
    return f"{age_days} day old" if age_days == 1 else f"{age_days} days old"


# ── Charts ───────────────────────────────────────────────────────────────────

def _norm(color) -> str:
    return str(color).strip().lower() if color else ""


def adapt_figure_to_theme(fig: go.Figure | None, *, is_light: bool) -> go.Figure | None:
    """Return a copy of ``fig`` whose dark-only chrome colours suit light mode.

    Only gridlines, axis lines, reference lines, background and title/legend
    text are touched. Trace data, trace colours and values are never changed.
    In dark mode the original figure is returned untouched.
    """
    if fig is None or not is_light:
        return fig
    out = go.Figure(fig)

    def _axis(ax):
        updates = {}
        for attr in ("gridcolor", "linecolor", "zerolinecolor"):
            if _norm(getattr(ax, attr, None)) in _DARK_LINES:
                updates[attr] = LIGHT_GRID
        if updates:
            ax.update(**updates)

    out.for_each_xaxis(_axis)
    out.for_each_yaxis(_axis)

    for shape in out.layout.shapes or ():
        if shape.line and _norm(shape.line.color) in _DARK_LINES:
            shape.line.color = LIGHT_ZERO

    lay = out.layout
    if lay.title and lay.title.font and _norm(lay.title.font.color) in _LIGHT_ON_DARK_TEXT:
        lay.title.font.color = LIGHT_TEXT
    if lay.legend and lay.legend.font and _norm(lay.legend.font.color) in _LIGHT_ON_DARK_TEXT:
        lay.legend.font.color = LIGHT_TEXT
    if lay.font and _norm(lay.font.color) in _LIGHT_ON_DARK_TEXT:
        lay.font.color = LIGHT_TEXT
    for attr in ("paper_bgcolor", "plot_bgcolor"):
        if _norm(getattr(lay, attr, None)) in _DARK_BACKGROUNDS:
            setattr(lay, attr, "rgba(0,0,0,0)")
    for ann in lay.annotations or ():
        if ann.font and _norm(ann.font.color) in _LIGHT_ON_DARK_TEXT:
            ann.font.color = LIGHT_TEXT
    return out


# ── Styles ───────────────────────────────────────────────────────────────────
# Tokens build on the existing OKLCH variables defined in master_dashboard.py
# (--foreground, --muted-foreground, --card, --border, --success, --warning,
# --destructive, --info), which already switch between light and dark.

COMPONENT_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
:root {
  --rd-fs-xs: 11px; --rd-fs-sm: 12px; --rd-fs-base: 13px; --rd-fs-md: 14px; --rd-fs-lg: 16px; --rd-fs-xl: 22px;
  --rd-sp-1: 4px; --rd-sp-2: 8px; --rd-sp-3: 12px; --rd-sp-4: 16px; --rd-sp-5: 24px; --rd-sp-6: 32px;
  --rd-radius: 10px; --rd-radius-sm: 6px;
  --rd-font: 'Inter', ui-sans-serif, system-ui, -apple-system, 'Segoe UI', sans-serif;
  --rd-mono: var(--rd-font);
  /* light (default) */
  --rd-bg: #F7F6F3; --rd-card: #FFFFFF; --rd-sidebar: #F2F1EC; --rd-line: #E7E4DD;
  --rd-hover: rgba(29,29,27,.04); --rd-active: #E8E6E0; --rd-tint: rgba(29,29,27,.025);
  --rd-text: #1D1D1B; --rd-text-2: #45443F; --rd-text-muted: #77756E;
  --rd-gain: #12805C; --rd-loss: #C2364B; --rd-warn: #A86200; --rd-info: #1F6F78;
  --rd-gain-bg: #E4F3EC; --rd-loss-bg: #FBE8EB; --rd-warn-bg: #FBF0DF; --rd-info-bg: #E3F0F1;
  --rd-surface: var(--rd-card);
}
[data-theme="dark"] {
  --rd-bg: #191A1A; --rd-card: #202222; --rd-sidebar: #1C1D1D; --rd-line: #2E3131;
  --rd-hover: rgba(255,255,255,.04); --rd-active: #2B2D2D; --rd-tint: rgba(255,255,255,.03);
  --rd-text: #ECECEA; --rd-text-2: #C9C9C5; --rd-text-muted: #91918C;
  --rd-gain: #3DBE8B; --rd-loss: #F06C80; --rd-warn: #E3A44A; --rd-info: #57BCC4;
  --rd-gain-bg: rgba(61,190,139,.14); --rd-loss-bg: rgba(240,108,128,.14);
  --rd-warn-bg: rgba(227,164,74,.14); --rd-info-bg: rgba(87,188,196,.14);
}
.rd-pill { display:inline-flex; align-items:center; gap:4px; padding:1px 8px; border-radius:999px;
  font-size:var(--rd-fs-xs); font-weight:600; line-height:18px; white-space:nowrap;
  border:0; }
.rd-pill--gain { color:var(--rd-gain); background:var(--rd-gain-bg); }
.rd-pill--loss { color:var(--rd-loss); background:var(--rd-loss-bg); }
.rd-pill--warn { color:var(--rd-warn); background:var(--rd-warn-bg); }
.rd-pill--info { color:var(--rd-info); background:var(--rd-info-bg); }
.rd-pill--muted { color:var(--rd-text-muted); background:transparent; }

.rd-ctx { display:flex; flex-wrap:wrap; align-items:center; gap:var(--rd-sp-2) var(--rd-sp-5);
  padding:var(--rd-sp-2) var(--rd-sp-3); border:1px solid var(--rd-line); border-radius:var(--rd-radius);
  font-size:var(--rd-fs-sm); color:var(--rd-text); margin:0 0 var(--rd-sp-4); }
.rd-ctx__item { display:inline-flex; gap:6px; align-items:baseline; }
.rd-ctx__label { color:var(--rd-text-muted); font-size:var(--rd-fs-xs); text-transform:uppercase;
  letter-spacing:.06em; }
.rd-ctx__value { font-weight:600; font-variant-numeric:tabular-nums; }
.rd-ctx__basis { margin-left:auto; color:var(--rd-warn); font-weight:600; font-size:var(--rd-fs-xs); }

.rd-kpis { display:grid; grid-template-columns:repeat(auto-fit, minmax(150px, 1fr));
  border:1px solid var(--rd-line); border-radius:var(--rd-radius); margin:0 0 var(--rd-sp-4); }
.rd-kpi { padding:var(--rd-sp-3); border-right:1px solid var(--rd-line); min-width:0; }
.rd-kpi:last-child { border-right:0; }
.rd-kpi__label { font-size:var(--rd-fs-xs); color:var(--rd-text-muted); text-transform:uppercase;
  letter-spacing:.06em; }
.rd-kpi__value { font-family:var(--rd-mono); font-size:var(--rd-fs-xl); font-weight:600;
  color:var(--rd-text); font-variant-numeric:tabular-nums; line-height:1.25; margin-top:2px; }
.rd-kpi__value--gain { color:var(--rd-gain); } .rd-kpi__value--loss { color:var(--rd-loss); }
.rd-kpi__value--warn { color:var(--rd-warn); } .rd-kpi__value--info { color:var(--rd-info); }
.rd-kpi__value--muted { color:var(--rd-text-muted); }
.rd-kpi__meta { font-size:var(--rd-fs-xs); color:var(--rd-text-muted); margin-top:2px; }
.rd-kpi__warn { font-size:var(--rd-fs-xs); color:var(--rd-warn); font-weight:600; margin-top:2px; }

.rd-checks { list-style:none; margin:0 0 var(--rd-sp-4); padding:0; border:1px solid var(--rd-line);
  border-radius:var(--rd-radius); }
.rd-check { display:grid; grid-template-columns:minmax(140px, 220px) auto 1fr; gap:var(--rd-sp-3);
  align-items:center; padding:var(--rd-sp-2) var(--rd-sp-3); border-bottom:1px solid var(--rd-line);
  font-size:var(--rd-fs-sm); color:var(--rd-text); }
.rd-check:last-child { border-bottom:0; }
.rd-check__title { font-weight:600; }
.rd-check__note { color:var(--rd-text-muted); }

.rd-empty { padding:var(--rd-sp-3) var(--rd-sp-4); border:1px dashed var(--rd-line);
  border-radius:var(--rd-radius); font-size:var(--rd-fs-sm); color:var(--rd-text); }
.rd-empty__title { font-weight:600; }
.rd-empty__reason { color:var(--rd-text-muted); margin-top:2px; }

.rd-sec { display:flex; align-items:baseline; gap:var(--rd-sp-3); margin:var(--rd-sp-5) 0 var(--rd-sp-2);
  padding-bottom:var(--rd-sp-1); border-bottom:1px solid var(--rd-line); }
.rd-sec__text { font-size:var(--rd-fs-xs); font-weight:700; letter-spacing:.08em;
  text-transform:uppercase; color:var(--rd-text); }
.rd-sec__meta { margin-left:auto; font-size:var(--rd-fs-xs); color:var(--rd-text-muted); }

.rd-headline { padding:var(--rd-sp-4) 0 var(--rd-sp-3); margin:0 0 var(--rd-sp-2);
  border-bottom:1px solid var(--rd-line); }
.rd-headline__text { font-size:var(--rd-fs-xl); line-height:1.3; font-weight:500; color:var(--rd-text);
  letter-spacing:-.01em; }
.rd-headline__em { font-weight:700; }
.rd-headline__em--gain { color:var(--rd-gain); } .rd-headline__em--loss { color:var(--rd-loss); }
.rd-headline__em--warn { color:var(--rd-warn); } .rd-headline__em--info { color:var(--rd-info); }
.rd-headline__em--muted { color:var(--rd-text-muted); }
.rd-headline__metas { display:flex; flex-wrap:wrap; gap:var(--rd-sp-1) var(--rd-sp-4); margin-top:var(--rd-sp-2); }
.rd-headline__meta { font-size:var(--rd-fs-sm); color:var(--rd-text-muted); }

.rd-strat-head { padding:var(--rd-sp-1) 0; font-size:var(--rd-fs-xs); color:var(--rd-text-muted);
  text-transform:uppercase; letter-spacing:.06em; border-bottom:1px solid var(--rd-line); }
.rd-strat-name { font-weight:700; font-size:var(--rd-fs-base); color:var(--rd-text); }
.rd-strat-desc { font-size:var(--rd-fs-sm); color:var(--rd-text-muted); line-height:1.4; }
.rd-num { font-family:var(--rd-mono); font-variant-numeric:tabular-nums; font-size:var(--rd-fs-base);
  color:var(--rd-text); }
.rd-num--gain { color:var(--rd-gain); } .rd-num--loss { color:var(--rd-loss); }
.rd-num__sub { display:block; font-family:inherit; font-size:var(--rd-fs-xs); color:var(--rd-text-muted); }
.rd-num__warn { display:block; font-size:var(--rd-fs-xs); color:var(--rd-warn); font-weight:600; }
.rd-num__label { display:none; font-size:var(--rd-fs-xs); color:var(--rd-text-muted);
  text-transform:uppercase; letter-spacing:.06em; }

@media (max-width: 700px) {
  .rd-strat-head, .st-key-rd_strat_header { display:none; }
  .rd-num__label { display:inline-block; min-width:96px; }
  .rd-num, .rd-num__sub, .rd-num__warn { display:inline; margin-right:6px; }
  .rd-headline__text { font-size:var(--rd-fs-lg); }
  .rd-kpi { border-right:0; border-bottom:1px solid var(--rd-line); }
  .rd-check { grid-template-columns:1fr auto; }
  .rd-check__note { grid-column:1 / -1; }
  .rd-ctx__basis { margin-left:0; }
}

/* Light-mode safety net: inline text colours written for dark backgrounds. */
[data-theme="light"] [style*="color:#e4e8f0"], [data-theme="light"] [style*="color: #e4e8f0"],
[data-theme="light"] [style*="color:#e0e0e0"], [data-theme="light"] [style*="color: #e0e0e0"],
[data-theme="light"] [style*="color:#fafafa"], [data-theme="light"] [style*="color: #fafafa"],
[data-theme="light"] [style*="color:#b0b8cc"] { color: var(--rd-text) !important; }
"""


# Shell layer: restyles Streamlit's own containers to the research-desk look
# (warm off-white canvas, white hairline cards, icon sidebar). Loaded after the
# legacy CSS in master_dashboard.py, so it uses !important where that CSS does.
SHELL_CSS = """
html, body, [data-testid="stApp"], [data-testid="stSidebar"], button, input, textarea, select,
[data-testid="stMarkdownContainer"] { font-family: var(--rd-font) !important; }
html body [data-testid="stApp"], html body [data-theme] [data-testid="stApp"] { background: var(--rd-bg) !important; }
[data-testid="stApp"]::before, [data-testid="stApp"]::after { display:none !important; }
html body [data-testid="stHeader"], html body [data-theme] [data-testid="stHeader"] { background: var(--rd-bg) !important; }
[data-testid="stMainBlockContainer"] { padding-top: 1.25rem !important; max-width: 1360px; }

/* Sidebar: quiet icon list */
html body [data-testid="stSidebar"] > div:first-child, html body [data-theme] [data-testid="stSidebar"] > div:first-child { background: var(--rd-sidebar) !important; }
[data-testid="stSidebar"] { border-right: 1px solid var(--rd-line) !important; }
html body [data-testid="stSidebar"] .stRadio [role="radiogroup"] { gap: 1px !important; }
html body [data-testid="stSidebar"] .stRadio [role="radiogroup"] label { position:relative; width:100% !important;
  margin:0 !important; padding:6px 10px !important; border:0 !important; border-radius:8px !important;
  background:transparent !important; box-shadow:none !important; min-height:0 !important; }
html body [data-testid="stSidebar"] .stRadio [role="radiogroup"] label > div:first-child { display:none !important; }
html body [data-testid="stSidebar"] .stRadio [role="radiogroup"] label:hover { background: var(--rd-hover) !important; }
html body [data-testid="stSidebar"] .stRadio [role="radiogroup"] label:has(input:checked) { background: var(--rd-active) !important; }
html body [data-testid="stSidebar"] .stRadio [role="radiogroup"] label p { font-size: var(--rd-fs-md) !important; font-weight:500 !important;
  color: var(--rd-text-2) !important; display:flex; align-items:center; gap:10px; }
html body [data-testid="stSidebar"] .stRadio [role="radiogroup"] label:has(input:checked) p { color: var(--rd-text) !important; font-weight:600 !important; }
html body [data-testid="stSidebar"] .stRadio [role="radiogroup"] label p span[data-testid="stIconMaterial"] { font-size:18px; color: var(--rd-text-muted); }
html body [data-testid="stSidebar"] .stRadio [role="radiogroup"] label:nth-child(2),
html body [data-testid="stSidebar"] .stRadio [role="radiogroup"] label:nth-child(4),
html body [data-testid="stSidebar"] .stRadio [role="radiogroup"] label:nth-child(9) { margin-top: 26px !important; }
html body [data-testid="stSidebar"] .stRadio [role="radiogroup"] label:nth-child(2)::before,
html body [data-testid="stSidebar"] .stRadio [role="radiogroup"] label:nth-child(4)::before,
html body [data-testid="stSidebar"] .stRadio [role="radiogroup"] label:nth-child(9)::before {
  position:absolute; top:-20px; left:10px; font-size: var(--rd-fs-xs); font-weight:600;
  letter-spacing:.06em; text-transform:uppercase; color: var(--rd-text-muted); }
html body [data-testid="stSidebar"] .stRadio [role="radiogroup"] label:nth-child(2)::before { content:"Strategies"; }
html body [data-testid="stSidebar"] .stRadio [role="radiogroup"] label:nth-child(4)::before { content:"Find stocks"; }
html body [data-testid="stSidebar"] .stRadio [role="radiogroup"] label:nth-child(9)::before { content:"Evaluate"; }

/* Cards, tabs, buttons, expanders */
[class*="st-key-rd_card"] { background: var(--rd-card) !important; border:1px solid var(--rd-line) !important;
  border-radius: 12px !important; box-shadow: none !important; padding: 14px 16px !important; }
[data-testid="stExpander"] details { background: var(--rd-card) !important; border:1px solid var(--rd-line) !important;
  border-radius: 10px !important; box-shadow:none !important; }
[data-testid="stTabs"] [role="tablist"] { gap: 4px; border-bottom: 1px solid var(--rd-line); }
[data-testid="stTabs"] button[role="tab"] { background:transparent !important; border-radius:0 !important;
  padding: 6px 2px !important; margin-right: 18px; }
[data-testid="stTabs"] button[role="tab"] p { font-size: var(--rd-fs-md) !important; font-weight:500 !important; color: var(--rd-text-muted) !important; }
[data-testid="stTabs"] button[role="tab"][aria-selected="true"] p { color: var(--rd-text) !important; font-weight:600 !important; }
.stButton button[kind="secondary"], [data-testid="stPopover"] button {
  background: var(--rd-card) !important; border:1px solid var(--rd-line) !important; color: var(--rd-text) !important;
  border-radius: 8px !important; box-shadow:none !important; min-height: 34px; }
.stButton button[kind="secondary"]:hover { background: var(--rd-hover) !important; }
.stButton button p { font-size: var(--rd-fs-base) !important; font-weight:500 !important; }
[data-testid="stCaptionContainer"], .stCaption { color: var(--rd-text-muted) !important; }

/* Page header */
.rd-page { margin: 0 0 var(--rd-sp-3); }
.rd-page__title { font-size: 24px; font-weight: 600; letter-spacing:-.015em; color: var(--rd-text); line-height:1.2; }
.rd-page__sub { font-size: var(--rd-fs-md); color: var(--rd-text-muted); margin-top: 4px; }
.rd-note { font-size: var(--rd-fs-sm); color: var(--rd-text-muted); }

/* Research table */
.rd-table-wrap { border:1px solid var(--rd-line); border-radius: 10px; background: var(--rd-card); overflow:auto; }
.rd-table { width:100%; border-collapse: collapse; font-size: var(--rd-fs-base); color: var(--rd-text);
  font-variant-numeric: tabular-nums; }
.rd-th { text-align:left; font-weight:500; font-size: var(--rd-fs-sm); color: var(--rd-text-muted);
  padding: 9px 12px; border-bottom:1px solid var(--rd-line); white-space:nowrap; background: var(--rd-card);
  position: sticky; top: 0; z-index: 1; }
.rd-td { padding: 9px 12px; border-bottom:1px solid var(--rd-line); vertical-align: middle; white-space: nowrap; }
.rd-th.rd-td--num, .rd-th--num, .rd-td--num { text-align:right; }
.rd-table tbody tr:last-child .rd-td { border-bottom: 0; }
.rd-td--name { white-space: normal; min-width: 140px; }
@media (max-width: 700px) { .rd-col--hide-sm { display:none; } .rd-td, .rd-th { padding: 8px 10px; } }
.rd-td--num { width: 1%; }
.rd-col--sorted { background: var(--rd-tint); }
.rd-tr { cursor: pointer; }
.rd-tr:hover .rd-td { background: var(--rd-hover); }
.rd-tr:focus-visible { outline: 2px solid var(--rd-info); outline-offset: -2px; }
.rd-tr--sel .rd-td { background: var(--rd-info-bg) !important; }
.rd-tr--sel .rd-td:first-child { box-shadow: inset 3px 0 0 var(--rd-info); }
.rd-name { display:flex; flex-direction:column; line-height:1.25; }
.rd-name__title { font-weight: 500; color: var(--rd-text); }
.rd-name__sub { font-size: var(--rd-fs-xs); color: var(--rd-text-muted); margin-top: 1px; }
.rd-table__empty { padding: 18px 14px; color: var(--rd-text-muted); font-size: var(--rd-fs-sm); }
.rd-chg { display:inline-block; padding: 2px 7px; border-radius: 6px; font-size: var(--rd-fs-sm);
  font-weight: 500; font-variant-numeric: tabular-nums; white-space: nowrap; }
.rd-chg--up { color: var(--rd-gain); background: var(--rd-gain-bg); }
.rd-chg--down { color: var(--rd-loss); background: var(--rd-loss-bg); }
.rd-chg--flat { color: var(--rd-text-muted); background: var(--rd-tint); }

/* Rail list (right column) */
.rd-list { border:1px solid var(--rd-line); border-radius:10px; background: var(--rd-card); }
.rd-list__head { padding: 10px 14px; font-size: var(--rd-fs-md); font-weight:600; color: var(--rd-text);
  border-bottom: 1px solid var(--rd-line); display:flex; justify-content:space-between; align-items:baseline; }
.rd-list__head span { font-size: var(--rd-fs-xs); font-weight:400; color: var(--rd-text-muted); }
.rd-li { display:flex; align-items:center; justify-content:space-between; gap: 10px; padding: 8px 14px;
  border-bottom:1px solid var(--rd-line); font-size: var(--rd-fs-base); }
.rd-li:last-child { border-bottom:0; }
.rd-li__main { display:flex; flex-direction:column; min-width:0; }
.rd-li__title { color: var(--rd-text); font-weight:500; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.rd-li__sub { color: var(--rd-text-muted); font-size: var(--rd-fs-xs); }
.rd-li__val { text-align:right; font-variant-numeric: tabular-nums; color: var(--rd-text); white-space:nowrap; }
.rd-dot { display:inline-block; width:8px; height:8px; border-radius:50%; margin-right:6px; vertical-align:middle; }
[class*="st-key-rd_card"] [data-testid="stPlotlyChart"] { border:0 !important; box-shadow:none !important; background:transparent !important; }
html body [data-testid="stSidebar"] [data-testid="stPopover"] button p { font-size: var(--rd-fs-md) !important; }
"""


def component_css() -> str:
    return f"<style>{COMPONENT_CSS}{SHELL_CSS}</style>"
