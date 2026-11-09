import json
from datetime import date, datetime

import pytest

import portfolio_monitor as pm
from core.exit_monitor import IST
from core.portfolio import append_transaction, load_ledger, positions
from core.portfolio_alerts import acknowledge, load_alerts
from tests.test_exit_monitor import make_bars, uptrend
from tests.test_portfolio_ledger import buy, opening

NOW = datetime(2026, 11, 9, 18, 0, tzinfo=IST)
NIFTY = date(2026, 11, 6)
UNI = {"APLAPOLLO.NS": {"name": "APL", "exchange": "NSE", "isin": "X"},
       "BHARATGEAR.NS": {"name": "BG", "exchange": "NSE", "isin": "Y"}}


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(pm, "universe_index", lambda *a, **k: UNI)
    d = tmp_path / "portfolio"
    d.mkdir()
    return d, tmp_path / "ui.json"


def add(d, tx):
    return append_transaction(d / "ledger.json", tx, universe=UNI, today=date(2026, 11, 8))


def run(env, bars, now=NOW, nifty=NIFTY):
    d, out = env
    rc = pm.main(["--dir", str(d), "--out", str(out)], now=now,
                 bars_loader=lambda s: bars.get(s), nifty_last_date=nifty)
    return rc, json.loads(out.read_text(encoding="utf-8"))


def test_empty_ledger_gives_zero_positions(env):
    rc, ui = run(env, {})
    assert rc == 0 and ui["positions"] == [] and ui["monitor"]["ok"] is True
    assert ui["scheduler"] == "none" and ui["version"] == 1
    assert (env[0] / "settings.json").exists()


@pytest.mark.parametrize("previous", [None, [], "invalid", 42])
def test_corrupt_ledger_with_non_object_previous_snapshot(env, previous):
    d, out = env
    (d / "ledger.json").write_text("{broken", encoding="utf-8")
    out.write_text(json.dumps(previous), encoding="utf-8")
    rc, ui = run(env, {})
    assert rc == 1
    assert ui["monitor"]["ok"] is False
    assert ui["positions"] == []


def test_missing_calendar_is_not_a_successful_check(env):
    add(env[0], buy("APLAPOLLO.NS", d="2026-10-01"))
    _, ui = run(env, {"APLAPOLLO.NS": make_bars(uptrend(last=140))}, nifty=lambda now: None)
    assert ui["monitor"]["ok"] is False
    assert ui["monitor"]["last_good_check"] is None


def test_acknowledgement_during_evaluation_survives_monitor_write(env):
    d, out = env
    add(d, buy("APLAPOLLO.NS", d="2026-10-01"))
    bars = make_bars(uptrend(last=80))
    run(env, {"APLAPOLLO.NS": bars})
    aid = load_alerts(d / "alerts.json")["alerts"][0]["id"]

    def loader(symbol):
        assert acknowledge(d / "alerts.json", aid)
        return bars

    assert pm.main(["--dir", str(d), "--out", str(out)], now=NOW,
                   bars_loader=loader, nifty_last_date=NIFTY) == 0
    assert load_alerts(d / "alerts.json")["acknowledgements"][0]["alert_id"] == aid
    assert json.loads(out.read_text(encoding="utf-8"))["alerts"][0]["acknowledged_at"]


def test_holding_absent_from_scanner_is_still_evaluated(env):
    add(env[0], dict(opening("BHARATGEAR.NS", 10, 100.0), strategy="momentum_edge"))
    rc, ui = run(env, {"BHARATGEAR.NS": make_bars(uptrend(last=80))})
    ev = ui["positions"][0]["evaluation"]
    assert rc == 0 and (ev["action"], ev["rule"]) == ("EXIT", "hard stop")
    assert ui["positions"][0]["name"] == "BG"


def test_opening_balance_strategy_other_is_review(env):
    add(env[0], opening("APLAPOLLO.NS", 10, 100.0))   # helper uses strategy "other"
    _, ui = run(env, {"APLAPOLLO.NS": make_bars(uptrend(last=80))})
    assert ui["positions"][0]["evaluation"]["action"] == "REVIEW"


def test_missing_file_is_data_unavailable_not_hold(env):
    add(env[0], buy("APLAPOLLO.NS", d="2026-10-01"))
    _, ui = run(env, {})
    assert ui["positions"][0]["evaluation"]["action"] == "DATA UNAVAILABLE"


def test_audit_log_appends_every_run(env):
    add(env[0], buy("APLAPOLLO.NS", d="2026-10-01"))
    bars = {"APLAPOLLO.NS": make_bars(uptrend(last=140))}
    run(env, bars)
    run(env, bars)
    lines = (env[0] / "evaluations.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2 and json.loads(lines[0])["symbol"] == "APLAPOLLO.NS"


def test_alert_dedupe_and_action_change(env):
    add(env[0], buy("APLAPOLLO.NS", d="2026-10-01"))
    exit_bars = {"APLAPOLLO.NS": make_bars(uptrend(last=80))}
    run(env, exit_bars)
    run(env, exit_bars)
    assert len(load_alerts(env[0] / "alerts.json")["alerts"]) == 1
    run(env, {"APLAPOLLO.NS": make_bars(uptrend(last=140))})      # HOLD: no alert
    assert len(load_alerts(env[0] / "alerts.json")["alerts"]) == 1
    _, ui = run(env, {"APLAPOLLO.NS": make_bars(uptrend(last=100))})  # EMA exit: new alert
    alerts = load_alerts(env[0] / "alerts.json")["alerts"]
    assert [a["rule"] for a in alerts] == ["hard stop", "EMA220 break"]
    assert len(ui["alerts"]) == 2


def test_acknowledgement_changes_alerts_only(env):
    add(env[0], buy("APLAPOLLO.NS", d="2026-10-01"))
    run(env, {"APLAPOLLO.NS": make_bars(uptrend(last=80))})
    before = (env[0] / "ledger.json").read_bytes()
    alert = load_alerts(env[0] / "alerts.json")["alerts"][0]
    assert acknowledge(env[0] / "alerts.json", alert["id"], NOW.replace(tzinfo=None))
    assert (env[0] / "ledger.json").read_bytes() == before
    assert positions(load_ledger(env[0] / "ledger.json"))["APLAPOLLO.NS"].open_qty == 10
    _, ui = run(env, {"APLAPOLLO.NS": make_bars(uptrend(last=80))})
    assert ui["alerts"][0]["acknowledged_at"] and len(ui["alerts"]) == 1


def test_corrupt_ledger_exits_1_with_error_and_leaves_file(env):
    d, out = env
    (d / "ledger.json").write_text("{not json", encoding="utf-8")
    rc, ui = run(env, {})
    assert rc == 1 and ui["monitor"]["ok"] is False and ui["monitor"]["errors"]
    assert (d / "ledger.json").read_text(encoding="utf-8") == "{not json"


def test_per_holding_exception_is_listed_and_exit_zero(env):
    add(env[0], buy("APLAPOLLO.NS", d="2026-10-01"))
    d, out = env

    def boom(sym):
        raise RuntimeError("bad csv")
    rc = pm.main(["--dir", str(d), "--out", str(out)], now=NOW, bars_loader=boom, nifty_last_date=NIFTY)
    ui = json.loads(out.read_text(encoding="utf-8"))
    assert rc == 0 and "bad csv" in ui["monitor"]["errors"][0]


def test_closed_positions_listed_not_evaluated(env):
    from tests.test_portfolio_ledger import sell
    add(env[0], buy("APLAPOLLO.NS", qty=5, d="2026-10-01"))
    add(env[0], sell("APLAPOLLO.NS", qty=5, price=120.0, d="2026-10-20"))
    _, ui = run(env, {})
    assert ui["positions"] == [] and ui["closed"][0]["symbol"] == "APLAPOLLO.NS"


def test_validate_only(env, capsys):
    d, _ = env
    add(d, buy("APLAPOLLO.NS", qty=5, d="2026-10-01"))
    cand = json.loads((d / "ledger.json").read_text(encoding="utf-8"))
    bad = dict(buy("APLAPOLLO.NS", qty=50, d="2026-10-05"), type="SELL", id="x", created_at="t")
    cand["transactions"].append(bad)
    p = d.parent / "cand.json"
    p.write_text(json.dumps(cand), encoding="utf-8")
    assert pm.main(["--validate-only", str(p)]) == 2
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is False and out["errors"]
    cand["transactions"][-1] = dict(bad, quantity=2)
    p.write_text(json.dumps(cand), encoding="utf-8")
    assert pm.main(["--validate-only", str(p)]) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True


def test_exit_stale_exit_raises_one_alert(env):
    add(env[0], buy("APLAPOLLO.NS", d="2026-10-01"))
    bars = {"APLAPOLLO.NS": make_bars(uptrend(last=80))}
    run(env, bars)
    run(env, bars, nifty=date(2026, 11, 9))          # STALE (bar behind Nifty)
    run(env, bars)                                    # EXIT again, same rule
    alerts = load_alerts(env[0] / "alerts.json")["alerts"]
    assert [a["action"] for a in alerts] == ["EXIT", "STALE"]


def test_missing_nifty_lists_error_and_stales_holdings(env):
    add(env[0], buy("APLAPOLLO.NS", d="2026-10-01"))
    d, out = env
    rc = pm.main(["--dir", str(d), "--out", str(out)], now=NOW,
                 bars_loader=lambda s: make_bars(uptrend(last=80)), nifty_last_date=lambda n: None)
    ui = json.loads(out.read_text(encoding="utf-8"))
    assert rc == 0 and ui["positions"][0]["evaluation"]["action"] == "STALE"
    assert any("calendar" in e for e in ui["monitor"]["errors"])


def test_validate_only_malformed_inputs(env, capsys):
    d, _ = env
    p = d.parent / "c.json"
    for text in ("{not json", json.dumps({"transactions": [5]}),
                 json.dumps({"transactions": [{"type": "BUY", "price": "x"}]}), "[]"):
        p.write_text(text, encoding="utf-8")
        assert pm.main(["--validate-only", str(p)]) == 2
        out = json.loads(capsys.readouterr().out)
        assert out["ok"] is False and out["errors"]
    assert pm.main(["--validate-only", str(d.parent / "nope.json")]) == 2


def test_corrupt_ledger_keeps_last_good_positions_marked_stale(env):
    d, out = env
    add(d, buy("APLAPOLLO.NS", d="2026-10-01"))
    run(env, {"APLAPOLLO.NS": make_bars(uptrend(last=140))})
    (d / "ledger.json").write_text("{bad", encoding="utf-8")
    rc, ui = run(env, {})
    ev = ui["positions"][0]["evaluation"]
    assert rc == 1 and ui["monitor"]["ok"] is False
    assert "ledger file unreadable" in ui["monitor"]["errors"][0] and "ledger.json" in ui["monitor"]["errors"][0]
    assert ev["data_status"] == "STALE" and "Ledger unreadable; showing the last good check from" in ev["explanation"]
    rc2, ui2 = run(env, {})                            # still corrupt: last good time preserved
    assert ui2["monitor"]["last_good_check"] == ui["monitor"]["last_good_check"] is not None


def test_corrupt_alerts_file_is_named(env):
    d, _ = env
    (d / "alerts.json").write_text("nope", encoding="utf-8")
    rc, ui = run(env, {})
    assert rc == 1 and "alerts file unreadable" in ui["monitor"]["errors"][0]


def test_append_stores_through_python(env, capsys):
    d, _ = env
    p = d.parent / "tx.json"
    p.write_text(json.dumps(buy("APLAPOLLO.NS", qty=5, d="2026-10-01")), encoding="utf-8")
    assert pm.main(["--dir", str(d), "--append", str(p)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True and out["transaction"]["id"] and out["transaction"]["created_at"]
    assert [t["id"] for t in load_ledger(d / "ledger.json")] == [out["transaction"]["id"]]


def test_append_rejects_without_writing(env, capsys):
    d, _ = env
    p = d.parent / "tx.json"
    p.write_text(json.dumps(dict(buy("APLAPOLLO.NS"), type="SELL")), encoding="utf-8")
    assert pm.main(["--dir", str(d), "--append", str(p)]) == 2
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is False and out["errors"] and not (d / "ledger.json").exists()
    p.write_text("{not json", encoding="utf-8")
    assert pm.main(["--dir", str(d), "--append", str(p)]) == 2
    assert json.loads(capsys.readouterr().out)["ok"] is False


def test_append_never_overwrites_corrupt_ledger(env, capsys):
    d, _ = env
    (d / "ledger.json").write_text("{broken", encoding="utf-8")
    p = d.parent / "tx.json"
    p.write_text(json.dumps(buy("APLAPOLLO.NS", d="2026-10-01")), encoding="utf-8")
    assert pm.main(["--dir", str(d), "--append", str(p)]) == 1
    assert json.loads(capsys.readouterr().out)["ok"] is False
    assert (d / "ledger.json").read_text(encoding="utf-8") == "{broken"


def test_ack_marks_alert_and_touches_only_alerts(env, capsys):
    d, _ = env
    add(d, buy("APLAPOLLO.NS", d="2026-10-01"))
    run(env, {"APLAPOLLO.NS": make_bars(uptrend(last=80))})
    capsys.readouterr()
    ledger_before = (d / "ledger.json").read_bytes()
    aid = load_alerts(d / "alerts.json")["alerts"][0]["id"]
    assert pm.main(["--dir", str(d), "--ack", aid]) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True
    assert load_alerts(d / "alerts.json")["acknowledgements"][0]["alert_id"] == aid
    assert (d / "ledger.json").read_bytes() == ledger_before
    assert pm.main(["--dir", str(d), "--ack", "nope"]) == 2
    assert json.loads(capsys.readouterr().out)["ok"] is False
