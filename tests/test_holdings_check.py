import json
from datetime import datetime

import holdings_check as hc
from core.exit_monitor import IST

NOW = datetime(2026, 11, 14, 16, 20, tzinfo=IST)
ENV = ("TELEGRAM_BOT_TOKEN=123:abc\nTELEGRAM_CHAT_ID=42\n"
       "SMTP_USER=bot@x.com\nSMTP_APP_PASSWORD=hunter2\nALERT_EMAIL_TO=me@x.com\n")
EXIT_ALERT = {"id": "a1", "symbol": "BHARATGEAR.NS", "action": "EXIT", "rule": "Close below 220-day EMA",
              "trigger_bar_date": "2026-11-14", "message": "Close is below the 220-day EMA."}


def position(sym, action="HOLD", status="OK", bar="2026-11-14"):
    return {"symbol": sym, "name": sym[:3], "open_qty": 10, "unrealised_pnl": -5.0, "unrealised_pnl_pct": -1.0,
            "evaluation": {"action": action, "data_status": status, "last_bar_date": bar, "last_close": 99.0}}


def ui_doc(positions, ok=True, errors=()):
    return {"monitor": {"ok": ok, "errors": list(errors)}, "positions": positions}


def alerts_doc(alerts=()):
    state = {a["symbol"]: {"action": a["action"], "rule": a["rule"]} for a in alerts}
    return {"version": 1, "state": state, "alerts": list(alerts), "acknowledgements": []}


def setup_root(tmp_path, env=ENV, settings=None):
    (tmp_path / "portfolio").mkdir()
    if env is not None:
        (tmp_path / ".env").write_text(env, encoding="utf-8")
    if settings is not None:
        (tmp_path / "portfolio" / "settings.json").write_text(json.dumps(settings), encoding="utf-8")
    return tmp_path


def fake_monitor(root, ui=None, alerts=None, rc=0, raw_ui=None, raises=None):
    calls = []

    def monitor(argv):
        calls.append(argv)
        if raises:
            raise raises
        out = root / "ui_portfolio.json"
        out.write_text(raw_ui if raw_ui is not None else json.dumps(ui), encoding="utf-8")
        (root / "portfolio" / "alerts.json").write_text(json.dumps(alerts or alerts_doc()), encoding="utf-8")
        return rc
    monitor.calls = calls
    return monitor


def recorder():
    sent = []
    senders = {"telegram": lambda s, b: sent.append(("telegram", s, b)),
               "email": lambda s, b: sent.append(("email", s, b))}
    return sent, senders


def no_fetch(ticker, start, end):
    return None


def run(root, monitor, senders, argv=(), now=NOW):
    return hc.main(list(argv), now=now, root=root, fetch=no_fetch, monitor=monitor, senders=senders)


def subjects(sent):
    return [(c, s) for c, s, _ in sent]


def test_sends_alerts_and_summary_once_per_day(tmp_path):
    root = setup_root(tmp_path)
    mon = fake_monitor(root, ui_doc([position("BHARATGEAR.NS", "EXIT"), position("MAHLOG.NS")]),
                       alerts_doc([EXIT_ALERT]))
    sent, senders = recorder()
    assert run(root, mon, senders) == 0
    expected = {"EXIT: BHARATGEAR.NS - Close below 220-day EMA", "Holdings check 2026-11-14: 1 EXIT, 1 HOLD"}
    for channel in ("telegram", "email"):
        assert {s for c, s in subjects(sent) if c == channel} == expected
    assert mon.calls == [["--dir", str(root / "portfolio"), "--out", str(root / "ui_portfolio.json")]]
    sent.clear()
    assert run(root, mon, senders) == 0
    assert sent == []


def test_monitor_crash_sends_failure_message(tmp_path):
    root = setup_root(tmp_path)
    sent, senders = recorder()
    assert run(root, fake_monitor(root, raises=RuntimeError("boom")), senders) == 0
    problem = [(c, s, b) for c, s, b in sent if s == "Holdings check problem 2026-11-14"]
    assert {c for c, _, _ in problem} == {"telegram", "email"} and "boom" in problem[0][2]


def test_unreadable_ui_file_sends_failure_message(tmp_path):
    root = setup_root(tmp_path)
    sent, senders = recorder()
    assert run(root, fake_monitor(root, raw_ui="{broken"), senders) == 0
    assert ("telegram", "Holdings check problem 2026-11-14") in subjects(sent)


def test_monitor_not_ok_and_nonzero_rc_are_failures(tmp_path):
    root = setup_root(tmp_path)
    sent, senders = recorder()
    mon = fake_monitor(root, ui_doc([position("A.NS")], ok=False, errors=["A.NS: bad bars"]), rc=1)
    run(root, mon, senders)
    bodies = " ".join(b for c, s, b in sent if c == "telegram" and s.startswith("Holdings check problem"))
    assert "A.NS: bad bars" in bodies and "exit code 1" in bodies


def test_stale_position_is_a_failure(tmp_path):
    root = setup_root(tmp_path)
    sent, senders = recorder()
    run(root, fake_monitor(root, ui_doc([position("TMCV.NS", "STALE", "STALE", "2026-11-07")])), senders)
    problem = [b for c, s, b in sent if c == "telegram" and s == "Holdings check problem 2026-11-14"]
    assert problem and "TMCV.NS" in problem[0]


def test_daily_summary_can_be_switched_off(tmp_path):
    root = setup_root(tmp_path, settings={"notifications": {"daily_summary": False}})
    sent, senders = recorder()
    run(root, fake_monitor(root, ui_doc([position("A.NS")])), senders)
    assert not any(s.startswith("Holdings check 2026-11-14") for _, s in subjects(sent))


def test_catch_up_run_next_morning_reports_previous_session(tmp_path):
    root = setup_root(tmp_path)
    sent, senders = recorder()
    run(root, fake_monitor(root, ui_doc([position("A.NS")])), senders,
        now=datetime(2026, 11, 15, 9, 0, tzinfo=IST))
    summary = [b for c, s, b in sent if c == "telegram" and s.startswith("Holdings check 2026-11-14")]
    assert summary and "No new trading session" not in summary[0]


def test_failed_nifty_download_is_reported(tmp_path):
    root = setup_root(tmp_path)
    sent, senders = recorder()

    def offline(ticker, start, end):
        raise ConnectionError("offline")
    hc.main([], now=NOW, root=root, fetch=offline, monitor=fake_monitor(root, ui_doc([position("A.NS")])),
            senders=senders)
    problem = [b for c, s, b in sent if c == "telegram" and s.startswith("Holdings check problem")]
    assert problem and "Nifty" in problem[0]


def test_send_failure_returns_1_and_hides_secrets(tmp_path, capsys):
    root = setup_root(tmp_path)

    def down(s, b):
        raise OSError("refused for 123:abc")
    rc = run(root, fake_monitor(root, ui_doc([position("A.NS")])), {"telegram": down})
    out = capsys.readouterr().out
    assert rc == 1 and "123:abc" not in out and "***" in out


def test_no_channels_configured_returns_1(tmp_path, capsys, monkeypatch):
    for key in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "SMTP_USER", "SMTP_APP_PASSWORD", "ALERT_EMAIL_TO"):
        monkeypatch.delenv(key, raising=False)
    root = setup_root(tmp_path, env=None)
    mon = fake_monitor(root, ui_doc([]))
    assert run(root, mon, None) == 1
    assert "TELEGRAM_BOT_TOKEN" in capsys.readouterr().out and mon.calls == []


def test_test_message_flag_sends_one_message_per_channel(tmp_path):
    root = setup_root(tmp_path)
    sent, senders = recorder()
    mon = fake_monitor(root, ui_doc([]))
    assert run(root, mon, senders, argv=["--test-message"]) == 0
    assert subjects(sent) == [("telegram", "Test message from NSE Strategy Hub"),
                              ("email", "Test message from NSE Strategy Hub")]
    assert mon.calls == []


FRIDAY = datetime(2026, 11, 13, 16, 20, tzinfo=IST)


def test_old_session_on_a_weekday_is_a_failure_even_with_summary_off(tmp_path):
    root = setup_root(tmp_path, settings={"notifications": {"daily_summary": False}})
    sent, senders = recorder()
    run(root, fake_monitor(root, ui_doc([position("A.NS", bar="2026-11-12")])), senders, now=FRIDAY)
    problem = [b for c, s, b in sent if c == "telegram" and s == "Holdings check problem 2026-11-13"]
    assert problem and "No price bar for 2026-11-13" in problem[0] and "2026-11-12" in problem[0]


def test_weekend_run_is_not_a_failure(tmp_path):
    root = setup_root(tmp_path)
    sent, senders = recorder()
    run(root, fake_monitor(root, ui_doc([position("A.NS", bar="2026-11-13")])), senders)   # NOW is a Saturday
    assert not any(s.startswith("Holdings check problem") for _, s in subjects(sent))


def test_unexpected_crash_after_monitor_still_sends_failure(tmp_path):
    root = setup_root(tmp_path)
    sent, senders = recorder()
    bad_alerts = {"version": 1, "state": {}, "alerts": ["junk"], "acknowledgements": []}
    rc = run(root, fake_monitor(root, ui_doc([position("A.NS")]), alerts=bad_alerts), senders)
    problem = [b for c, s, b in sent if c == "telegram" and s.startswith("Holdings check problem")]
    assert problem and "crashed" in problem[0] and rc == 1


def test_system_exit_from_monitor_is_reported(tmp_path):
    root = setup_root(tmp_path)
    sent, senders = recorder()
    run(root, fake_monitor(root, raises=SystemExit(2)), senders)
    assert any(s.startswith("Holdings check problem") for c, s in subjects(sent) if c == "telegram")
