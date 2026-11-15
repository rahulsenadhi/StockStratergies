import json
import urllib.error
from datetime import datetime

from core import notify
from core.exit_monitor import IST

NOW = datetime(2026, 11, 14, 16, 20, tzinfo=IST)


def test_env_parsing_handles_quotes_comments_bom(tmp_path):
    p = tmp_path / ".env"
    p.write_bytes('﻿# keys\nTELEGRAM_BOT_TOKEN = "123:abc"\nTELEGRAM_CHAT_ID=42\n\nSMTP_USER=me@x.com\n'.encode("utf-8"))
    cfg, notes = notify.load_config(p, environ={})
    assert cfg == {"telegram": {"token": "123:abc", "chat_id": "42"}}
    assert any("email" in n for n in notes)            # incomplete channel reported, not raised


def test_environment_overrides_file(tmp_path):
    p = tmp_path / ".env"
    p.write_text("TELEGRAM_BOT_TOKEN=file\nTELEGRAM_CHAT_ID=1\n", encoding="utf-8")
    cfg, _ = notify.load_config(p, environ={"TELEGRAM_BOT_TOKEN": "env"})
    assert cfg["telegram"]["token"] == "env"


def test_missing_env_file_gives_no_channels(tmp_path):
    assert notify.load_config(tmp_path / ".env", environ={})[0] == {}


def test_only_current_unacknowledged_alerts_are_sent():
    doc = {"state": {"A.NS": {"action": "EXIT", "rule": "ema"}, "B.NS": {"action": "HOLD", "rule": None}},
           "alerts": [{"id": "1", "symbol": "A.NS", "action": "REVIEW", "rule": "ema"},
                      {"id": "2", "symbol": "A.NS", "action": "EXIT", "rule": "ema"},
                      {"id": "3", "symbol": "B.NS", "action": "EXIT", "rule": "stop"},
                      {"id": "4", "symbol": "C.NS", "action": "EXIT", "rule": "stop"}],
           "acknowledgements": []}
    assert [a["id"] for a in notify.alerts_to_send(doc)] == ["2"]
    doc["acknowledgements"] = [{"alert_id": "2"}]
    assert notify.alerts_to_send(doc) == []


def _alert_and_position():
    alert = {"id": "x1", "symbol": "BHARATGEAR.NS", "action": "EXIT", "rule": "Close below 220-day EMA",
             "trigger_bar_date": "2026-11-13", "message": "The model exits at the next session's open."}
    pos = {"symbol": "BHARATGEAR.NS", "name": "Bharat Gears", "open_qty": 1051,
           "unrealised_pnl": -2399.0, "unrealised_pnl_pct": -2.3,
           "evaluation": {"last_close": 98.54, "last_bar_date": "2026-11-13",
                          "levels": {"ema220": 106.53, "ema_distance_pct": -7.5, "hard_stop": 85.71}}}
    return alert, pos


def test_alert_message_has_close_pnl_and_honesty_line():
    alert, pos = _alert_and_position()
    m = notify.alert_message(alert, pos)
    assert m["key"] == "x1" and m["subject"] == "EXIT: BHARATGEAR.NS - Close below 220-day EMA"
    for part in ("Bharat Gears", "1051 shares", "-2.3%", "98.54", "2026-11-13",
                 "Past rules, not a promise. Nothing is sold automatically; you decide."):
        assert part in m["body"]


def test_alert_message_without_position_skips_missing_lines():
    alert, _ = _alert_and_position()
    m = notify.alert_message(alert, None)
    assert "Your holding" not in m["body"] and "None" not in m["body"]
    assert m["body"].endswith("Past rules, not a promise. Nothing is sold automatically; you decide.")


def _ui():
    return {"positions": [{"symbol": s, "evaluation": {"action": a}, "unrealised_pnl_pct": 1.0}
                          for s, a in (("A.NS", "EXIT"), ("B.NS", "REVIEW"), ("C.NS", "HOLD"))]}


def test_summary_counts_and_holiday_wording():
    m = notify.summary_message(_ui(), "2026-11-14", "2026-11-14")
    assert m["key"] == "summary:2026-11-14"
    assert m["subject"] == "Holdings check 2026-11-14: 1 EXIT, 1 REVIEW, 1 HOLD"
    assert "No new trading session today" not in m["body"]
    holiday = notify.summary_message(_ui(), "2026-11-13", "2026-11-14")
    assert "No new trading session today" in holiday["body"]


def test_failure_message_key_and_text():
    m = notify.failure_message("prices old", "2026-11-14")
    assert m["key"].startswith("failure:2026-11-14:") and len(m["key"].split(":")[-1]) == 8
    assert m["subject"] == "Holdings check problem 2026-11-14"
    assert "prices old" in m["body"] and "holdings_check.log" in m["body"]
    assert notify.failure_message("other", "2026-11-14")["key"] != m["key"]


def test_texts_never_use_forbidden_words():
    alert, pos = _alert_and_position()
    msgs = [notify.alert_message(alert, pos), notify.summary_message(_ui(), "2026-11-13", "2026-11-14"),
            notify.failure_message("x", "2026-11-14")]
    for m in msgs:
        text = (m["subject"] + " " + m["body"]).lower()
        assert "guarantee" not in text and "no loss" not in text and "100%" not in text


def test_deliver_sends_once_and_retries_failed_channel(tmp_path):
    log, calls = tmp_path / "n.jsonl", []
    ok = lambda s, b: calls.append(("tg", s))

    def down(s, b):
        raise OSError("smtp down")
    msgs = [notify.failure_message("prices old", "2026-11-14")]
    problems = notify.deliver(msgs, {"telegram": ok, "email": down}, log, NOW)
    assert calls == [("tg", msgs[0]["subject"])] and problems == [f"email: {msgs[0]['key']}: OSError: smtp down"]
    notify.deliver(msgs, {"telegram": ok, "email": lambda s, b: calls.append(("em", s))}, log, NOW)
    assert [c[0] for c in calls] == ["tg", "em"]      # telegram not repeated, email retried
    rows = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert [(r["channel"], r["ok"]) for r in rows] == [("telegram", True), ("email", False), ("email", True)]
    assert rows[0]["sent_at"] == "2026-11-14T16:20:00+05:30" and rows[0]["error"] is None


def test_deliver_redacts_secrets(tmp_path):
    def leak(s, b):
        raise RuntimeError("bad url https://x/bot123:abc/send pw=hunter2")
    log = tmp_path / "n.jsonl"
    problems = notify.deliver([notify.failure_message("x", "2026-11-14")], {"telegram": leak}, log, NOW,
                              secrets=["123:abc", "hunter2"])
    assert "123:abc" not in problems[0] and "hunter2" not in problems[0] and "***" in problems[0]
    assert "123:abc" not in log.read_text(encoding="utf-8")


def test_settings_default_daily_summary_on(tmp_path):
    from core.portfolio import load_settings
    assert load_settings(tmp_path / "none.json")["notifications"] == {"daily_summary": True}
    (tmp_path / "s.json").write_text('{"notifications": {"daily_summary": false}}', encoding="utf-8")
    s = load_settings(tmp_path / "s.json")
    assert s["notifications"]["daily_summary"] is False and "charges" in s


class _Resp:
    def __init__(self, payload):
        self.payload = payload
        self.status = 200

    def read(self):
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_telegram_sender_posts_send_message(monkeypatch):
    seen = {}

    def fake_urlopen(req, timeout):
        seen["url"], seen["data"], seen["timeout"] = req.full_url, json.loads(req.data), timeout
        seen["ctype"] = req.get_header("Content-type")
        return _Resp({"ok": True})
    monkeypatch.setattr(notify.urllib.request, "urlopen", fake_urlopen)
    notify.make_senders({"telegram": {"token": "123:abc", "chat_id": "42"}})["telegram"]("Subj", "Body")
    assert seen["url"] == "https://api.telegram.org/bot123:abc/sendMessage"
    assert seen["data"] == {"chat_id": "42", "text": "Subj\n\nBody"} and seen["timeout"] == 20
    assert seen["ctype"] == "application/json"


def test_telegram_ok_false_raises(monkeypatch):
    import pytest
    monkeypatch.setattr(notify.urllib.request, "urlopen",
                        lambda req, timeout: _Resp({"ok": False, "description": "chat not found"}))
    with pytest.raises(RuntimeError, match="chat not found"):
        notify.make_senders({"telegram": {"token": "t", "chat_id": "1"}})["telegram"]("S", "B")


def test_email_sender_uses_gmail_ssl(monkeypatch):
    seen = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            seen["host"], seen["port"], seen["timeout"] = host, port, timeout

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def login(self, user, password):
            seen["login"] = (user, password)

        def send_message(self, msg):
            seen["msg"] = msg
    monkeypatch.setattr(notify.smtplib, "SMTP_SSL", FakeSMTP)
    cfg = {"email": {"user": "bot@x.com", "password": "pw", "to": "me@x.com"}}
    notify.make_senders(cfg)["email"]("Subj", "Body")
    msg = seen["msg"]
    assert (seen["host"], seen["port"], seen["timeout"]) == ("smtp.gmail.com", 465, 20)
    assert seen["login"] == ("bot@x.com", "pw")
    assert msg["Subject"] == "Subj" and msg["To"] == "me@x.com" and msg["From"] == "bot@x.com"
    assert msg.get_content().strip() == "Body"


def test_make_senders_only_for_configured_channels():
    assert set(notify.make_senders({"telegram": {"token": "t", "chat_id": "1"}})) == {"telegram"}
    assert notify.make_senders({}) == {}


def test_secret_in_error_is_redacted(tmp_path, monkeypatch):
    cfg = {"telegram": {"token": "123:abc", "chat_id": "42"},
           "email": {"user": "bot@x.com", "password": "hunter2", "to": "me@x.com"}}
    assert set(notify.secrets_of(cfg)) == {"123:abc", "hunter2"}

    def boom(req, timeout):
        raise urllib.error.URLError(f"failed {req.full_url}")
    monkeypatch.setattr(notify.urllib.request, "urlopen", boom)
    log = tmp_path / "n.jsonl"
    senders = {"telegram": notify.make_senders(cfg)["telegram"]}
    problems = notify.deliver([notify.failure_message("x", "2026-11-14")], senders, log, NOW,
                              secrets=notify.secrets_of(cfg))
    assert "123:abc" not in problems[0] and "***" in problems[0]
    assert "123:abc" not in log.read_text(encoding="utf-8")


def test_alert_message_uses_evaluation_date_and_shows_rule_levels():
    alert = {"id": "x2", "symbol": "ANDHRSUGAR.NS", "action": "EXIT", "rule": "ema220",
             "trigger_bar_date": "2026-11-06", "message": "The model exits at the next session's open."}
    pos = {"symbol": "ANDHRSUGAR.NS", "name": "Andhra Sugars", "open_qty": 1571,
           "unrealised_pnl": -14000.0, "unrealised_pnl_pct": -9.3,
           "evaluation": {"last_close": 82.1, "last_bar_date": "2026-11-13",
                          "levels": {"ema220": 86.12, "ema_distance_pct": -4.67, "hard_stop": 81.17}}}
    body = notify.alert_message(alert, pos)["body"]
    assert "Last close 2026-11-13: ₹82.10" in body and "2026-11-06: ₹" not in body
    assert "Rule levels: 220-day EMA ₹86.12 (close -4.7% from it), hard stop ₹81.17" in body


def test_sent_log_with_bad_bytes_is_still_read(tmp_path):
    log = tmp_path / "n.jsonl"
    log.write_bytes(b"\xff\xfe junk\n" + json.dumps({"key": "k1", "channel": "telegram", "ok": True}).encode() + b"\n")
    calls = []
    notify.deliver([{"key": "k1", "subject": "s", "body": "b"}],
                   {"telegram": lambda s, b: calls.append(s)}, log, NOW)
    assert calls == []
