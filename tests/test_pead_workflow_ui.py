"""Regression checks for PEAD empty feeds and evidence selection."""
import pandas as pd
import pytest
import json
import subprocess
from streamlit.testing.v1 import AppTest
import pead_dashboard as dashboard


def test_unknown_is_not_failed_or_passed():
    checks = dashboard.qualification_checks({"sue_decile": 10, "piotroski": 6, "pb": 2})
    assert [c["State"] for c in checks] == ["Pass", "Fail", "Missing"]


def test_empty_live_feed_does_not_block_screen(tmp_path, monkeypatch):
    monkeypatch.setattr(dashboard, "DATA", tmp_path)
    monkeypatch.setattr(dashboard, "BASE", tmp_path)
    (tmp_path / "live_signals.csv").write_text("\n")
    events = pd.DataFrame([
        dict(ticker="AAA.NS", sector="IT", result_date="2026-01-20", period_type="Q",
             sue=3., piotroski=8., pb=2., pb_sector_median=3., sue_decile=10,
             qualifies_long=True, eps_actual=5., eps_expected=2.5, eps_history=[1.,2.,3.,4.]),
        dict(ticker="BBB.NS", sector="IT", result_date="2026-01-19", period_type="Q",
             sue=1., piotroski=6., pb=4., pb_sector_median=3., sue_decile=6,
             qualifies_long=False, eps_actual=2., eps_expected=1., eps_history=[1.,1.,1.,1.]),
    ])
    events.to_parquet(tmp_path / "events.parquet", index=False)
    before = (tmp_path / "events.parquet").read_bytes()
    app = AppTest.from_string("import pead_dashboard as p\np.render()", default_timeout=20).run()
    assert not app.exception
    assert next(m for m in app.metric if m.label == "Matching company results").value == "2"
    assert any("feed is empty" in x.value for x in app.info)
    checklists = [x.value for x in app.dataframe if "Check" in x.value.columns]
    assert checklists[0]["#"].tolist() == list(range(1,24))
    assert set(checklists[0]["State"]) == {"Not recorded"}
    app.selectbox[0].select(1).run()
    assert not app.exception
    assert any(x.value == "BBB.NS" for x in app.subheader)
    app.slider[0].set_value(2.).run()
    assert not app.exception
    assert next(m for m in app.metric if m.label == "Matching company results").value == "1"
    app.slider[0].set_value(5.).run()
    assert not app.exception
    assert any("No events match" in x.value for x in app.info)
    assert (tmp_path / "events.parquet").read_bytes() == before


def test_incomplete_schema_is_explained(tmp_path, monkeypatch):
    monkeypatch.setattr(dashboard, "DATA", tmp_path)
    pd.DataFrame({"ticker": ["AAA"]}).to_parquet(tmp_path / "events.parquet")
    app = AppTest.from_string("import pead_dashboard as p\np._tab_screener()", default_timeout=20).run()
    assert not app.exception
    assert "Missing fields" in app.warning[0].value


@pytest.mark.parametrize("metrics", ["\n", "metric,value\ncagr,0.1\n"])
def test_empty_optional_results_do_not_block_screen(tmp_path, monkeypatch, metrics):
    monkeypatch.setattr(dashboard, "DATA", tmp_path)
    monkeypatch.setattr(dashboard, "BASE", tmp_path)
    (tmp_path / "pead_equity.csv").write_text("date,equity\n2026-01-20,100000\n")
    (tmp_path / "pead_kpis.csv").write_text(metrics)
    (tmp_path / "pead_decile_spread.csv").write_text("\n")
    (tmp_path / "pead_trades.csv").write_text("\n")
    (tmp_path / "last_run_status.json").write_text("{")
    app = AppTest.from_string("import pead_dashboard as p\np.render()", default_timeout=20).run()
    assert not app.exception
    assert any("refresh status is unreadable" in x.value for x in app.warning)
    assert any("No earnings events saved" in x.value for x in app.info)
    if metrics.strip():
        assert [m.value for m in app.metric] == ["10.0%", "Not recorded", "Not recorded", "Not recorded"]


def test_invalid_dates_preserve_reviewable_evidence(tmp_path, monkeypatch):
    monkeypatch.setattr(dashboard, "DATA", tmp_path)
    monkeypatch.setattr(dashboard, "BASE", tmp_path)
    pd.DataFrame([dict(ticker="AAA.NS", sector="IT", result_date="unknown",
                       sue=3., piotroski=8., pb=2.)]).to_parquet(tmp_path / "events.parquet")
    app = AppTest.from_string("import pead_dashboard as p\np.render()", default_timeout=20).run()
    assert not app.exception
    assert any("Dates not recorded" in x.value for x in app.caption)
    assert any("No dated earnings history" in x.value for x in app.info)
    assert any(x.value == "AAA.NS" for x in app.subheader)


def test_failed_refresh_keeps_saved_results_and_guided_navigation(tmp_path, monkeypatch):
    monkeypatch.setattr(dashboard, "DATA", tmp_path)
    monkeypatch.setattr(dashboard, "BASE", tmp_path)
    (tmp_path / "last_run_status.json").write_text('{"run_date":"2026-09-09","error":"Provider unavailable"}')
    pd.DataFrame([
        dict(ticker="AAA.NS", sector="IT", result_date=date, period_type="Q",
             sue=1., piotroski=8., pb=2., eps_actual=3., eps_expected=2.)
        for date in ["2026-01-20", "2025-10-20"]
    ]).to_parquet(tmp_path / "events.parquet")
    app = AppTest.from_string("import pead_dashboard as p\np.render()", default_timeout=30).run()
    assert not app.exception
    assert any("last update failed" in w.value for w in app.warning)
    assert any("2 company results" in m.value and "1 company" in m.value for m in app.markdown)
    assert not any("0 company results saved" in c.value for c in app.caption)
    assert next(m for m in app.metric if m.label == "Marked eligible in saved run").value == "Not recorded"
    assert any("above the previous-four-period average" in m.value for m in app.markdown)
    assert [tab.label for tab in app.tabs] == ["Overview", "Find companies", "Saved signals", "Past performance", "Results calendar"]
    next(b for b in app.button if b.label == "Find companies to review").click().run()
    assert not app.exception
    assert app.session_state["pead_section"] == "Find companies"
    assert next(s for s in app.slider if s.key == "pead_sue").value == -3.
    assert next(s for s in app.slider if s.key == "pead_pio").value == 5
    assert next(n for n in app.number_input if n.key == "pead_pb").value == 10.


def test_missing_run_counts_are_not_assumed_zero(tmp_path, monkeypatch):
    monkeypatch.setattr(dashboard, "DATA", tmp_path)
    (tmp_path / "last_run_status.json").write_text('{"run_date":"2026-09-09"}')
    app = AppTest.from_string("import pead_dashboard as p\np._refresh_strip()", default_timeout=20).run()
    assert not app.exception
    assert any("counts were not recorded" in c.value for c in app.caption)
    assert not any("0" in c.value for c in app.caption if "counts" in c.value)


def test_refresh_strip_points_updates_to_new_app(tmp_path, monkeypatch):
    """Updates run from the Next.js app only, so two apps never write pead_data at once."""
    from core.workflow_ui import UPDATES_MOVED_NOTE
    monkeypatch.setattr(dashboard, "DATA", tmp_path)
    (tmp_path / "last_run_status.json").write_text('{"run_date":"2026-11-06","rows_written":3,"qualified_long":1}')

    def no_update(*a, **k):
        raise AssertionError("Streamlit must not start the PEAD downloader")

    monkeypatch.setattr(subprocess, "run", no_update)
    app = AppTest.from_string("import pead_dashboard as p\np._refresh_strip()", default_timeout=20).run()
    assert not app.exception
    assert not app.button
    assert any(UPDATES_MOVED_NOTE == c.value for c in app.caption)
    assert any("3 company results saved" in c.value for c in app.caption)


def test_empty_state_text_names_the_new_app(tmp_path, monkeypatch):
    monkeypatch.setattr(dashboard, "DATA", tmp_path)
    monkeypatch.setattr(dashboard, "BASE", tmp_path)
    app = AppTest.from_string("import pead_dashboard as p\np.render()", default_timeout=20).run()
    assert not app.exception
    assert not any("Use Update earnings data" in i.value for i in app.info)
