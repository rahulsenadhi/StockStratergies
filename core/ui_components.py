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
:root {
  --rd-fs-xs: 11px; --rd-fs-sm: 12px; --rd-fs-base: 13px; --rd-fs-lg: 16px; --rd-fs-xl: 22px;
  --rd-sp-1: 4px; --rd-sp-2: 8px; --rd-sp-3: 12px; --rd-sp-4: 16px; --rd-sp-5: 24px; --rd-sp-6: 32px;
  --rd-radius: 6px; --rd-radius-sm: 4px;
  --rd-text: var(--foreground, #172033);
  --rd-text-muted: var(--muted-foreground, #5b6475);
  --rd-surface: var(--card, transparent);
  --rd-line: var(--border, rgba(127,127,127,.25));
  --rd-gain: var(--success, #0a8a5f);
  --rd-loss: var(--destructive, #c62828);
  --rd-warn: var(--warning, #b26a00);
  --rd-info: var(--info, #2f5bd3);
  --rd-mono: var(--font-mono, 'IBM Plex Mono', ui-monospace, monospace);
}
.rd-pill { display:inline-flex; align-items:center; gap:4px; padding:1px 8px; border-radius:999px;
  font-size:var(--rd-fs-xs); font-weight:600; line-height:18px; white-space:nowrap;
  border:1px solid currentColor; }
.rd-pill--gain { color:var(--rd-gain); background:color-mix(in oklch, var(--rd-gain) 10%, transparent); }
.rd-pill--loss { color:var(--rd-loss); background:color-mix(in oklch, var(--rd-loss) 10%, transparent); }
.rd-pill--warn { color:var(--rd-warn); background:color-mix(in oklch, var(--rd-warn) 12%, transparent); }
.rd-pill--info { color:var(--rd-info); background:color-mix(in oklch, var(--rd-info) 10%, transparent); }
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


def component_css() -> str:
    return f"<style>{COMPONENT_CSS}</style>"
