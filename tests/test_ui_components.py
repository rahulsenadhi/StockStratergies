"""Tests for presentation-only UI components (no business logic)."""
import plotly.graph_objects as go
import pytest

from core import ui_components as ui


# ── status pill ──────────────────────────────────────────────────────────────

def test_status_pill_renders_label_and_tone_class():
    html = ui.status_pill("Live", "gain")
    assert "Live" in html
    assert "rd-pill--gain" in html


def test_status_pill_escapes_label():
    html = ui.status_pill("<b>x</b>", "info")
    assert "<b>" not in html
    assert "&lt;b&gt;" in html


def test_status_pill_rejects_unknown_tone():
    with pytest.raises(ValueError):
        ui.status_pill("x", "purple")


# ── context bar ──────────────────────────────────────────────────────────────

def test_context_bar_lists_every_item_in_order():
    html = ui.context_bar([("Strategy", "Monthly Rotation"), ("Universe", "Nifty 50"),
                           ("Period", "Jun 2023 – Jun 2026")])
    assert html.index("Monthly Rotation") < html.index("Nifty 50") < html.index("Jun 2023")
    assert html.count("rd-ctx__item") == 3


def test_context_bar_shows_basis_note_when_given():
    html = ui.context_bar([("Strategy", "X")], basis="Gross, before costs")
    assert "Gross, before costs" in html


def test_context_bar_escapes_values():
    html = ui.context_bar([("Strategy", "<script>")])
    assert "<script>" not in html


# ── KPI with sample size ─────────────────────────────────────────────────────

def test_kpi_shows_sample_size():
    html = ui.kpi("CAGR", "+20.9%", sample_n=36)
    assert "+20.9%" in html and "36 trades" in html


def test_kpi_flags_small_sample():
    html = ui.kpi("CAGR", "+26.1%", sample_n=4)
    assert "rd-kpi--low-sample" in html
    assert "fewer than" in html.lower()


def test_kpi_no_flag_at_threshold():
    html = ui.kpi("CAGR", "+1%", sample_n=ui.LOW_SAMPLE_TRADES)
    assert "rd-kpi--low-sample" not in html


def test_kpi_sample_unit_is_configurable():
    html = ui.kpi("CAGR", "+20.9%", sample_n=36, sample_unit="monthly rebalances")
    assert "36 monthly rebalances" in html and "trades" not in html


def test_kpi_small_sample_warning_uses_unit():
    html = ui.kpi("CAGR", "+1%", sample_n=4, sample_unit="rebalances")
    assert "fewer than 30 rebalances" in html


def test_kpi_without_sample_has_no_sample_text():
    html = ui.kpi("Sharpe", "1.44")
    assert "trades" not in html


def test_kpi_tone_class():
    assert "rd-kpi__value--loss" in ui.kpi("Max DD", "-12%", tone="loss")


def test_kpi_row_wraps_all_kpis():
    html = ui.kpi_row([ui.kpi("A", "1"), ui.kpi("B", "2")])
    assert html.startswith('<div class="rd-kpis"')
    assert html.count('class="rd-kpi') >= 2


# ── validation checklist ─────────────────────────────────────────────────────

def test_checklist_renders_each_check_with_status_label():
    html = ui.validation_checklist([
        ("Out-of-sample test", "not_tested", "Only one historical period was simulated."),
        ("Trading costs", "not_modelled", "Results are gross."),
    ])
    assert "Out-of-sample test" in html and "Not tested" in html
    assert "Trading costs" in html and "Not modelled" in html


def test_checklist_rejects_unknown_status():
    with pytest.raises(ValueError):
        ui.validation_checklist([("x", "great", "")])


def test_checklist_never_claims_passed_without_status():
    html = ui.validation_checklist([("Look-ahead audit", "not_tested", "")])
    assert "Passed" not in html


# ── empty state ──────────────────────────────────────────────────────────────

def test_empty_state_has_title_and_reason():
    html = ui.empty_state("No IPO breakouts", "The saved scan is 31 days old.")
    assert "No IPO breakouts" in html and "31 days old" in html
    assert 'role="status"' in html


# ── freshness ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("days,tone", [(0, "gain"), (7, "gain"), (8, "warn"),
                                       (21, "warn"), (22, "loss"), (None, "muted")])
def test_freshness_tone(days, tone):
    assert ui.freshness_tone(days) == tone


def test_freshness_label_text():
    assert ui.freshness_label(0) == "updated today"
    assert ui.freshness_label(1) == "1 day old"
    assert ui.freshness_label(31) == "31 days old"
    assert ui.freshness_label(None) == "no saved file"


# ── chart theme adapter ──────────────────────────────────────────────────────

def _dark_fig():
    fig = go.Figure(go.Scatter(x=[1, 2], y=[3, 4]))
    fig.add_hline(y=0, line=dict(color="#333", dash="dash", width=1))
    fig.update_layout(title=dict(text="T", font=dict(color="#e0e0e0")),
                      xaxis=dict(gridcolor="#1a1f35"), yaxis=dict(gridcolor="#1E293B"))
    return fig


def test_adapt_figure_light_replaces_dark_grid_and_title():
    fig = ui.adapt_figure_to_theme(_dark_fig(), is_light=True)
    assert fig.layout.xaxis.gridcolor == ui.LIGHT_GRID
    assert fig.layout.yaxis.gridcolor == ui.LIGHT_GRID
    assert fig.layout.title.font.color == ui.LIGHT_TEXT
    assert fig.layout.shapes[0].line.color == ui.LIGHT_ZERO


def test_adapt_figure_dark_leaves_figure_unchanged():
    before = _dark_fig().to_plotly_json()
    after = ui.adapt_figure_to_theme(_dark_fig(), is_light=False).to_plotly_json()
    assert before == after


def test_adapt_figure_does_not_touch_trace_data():
    fig = ui.adapt_figure_to_theme(_dark_fig(), is_light=True)
    assert list(fig.data[0].x) == [1, 2] and list(fig.data[0].y) == [3, 4]


def test_adapt_figure_keeps_non_dark_colors():
    fig = go.Figure()
    fig.update_layout(xaxis=dict(gridcolor="rgba(148,163,184,0.10)"))
    fig = ui.adapt_figure_to_theme(fig, is_light=True)
    assert fig.layout.xaxis.gridcolor == "rgba(148,163,184,0.10)"


def test_adapt_figure_handles_none():
    assert ui.adapt_figure_to_theme(None, is_light=True) is None
