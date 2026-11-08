"""Portfolio ledger: validation, FIFO accounting, persistence, backups."""
from __future__ import annotations

import json
from datetime import date

import pytest

from core import portfolio as pf

TODAY = date(2026, 11, 8)
UNIVERSE = {
    "APLAPOLLO.NS": {"name": "APL Apollo", "exchange": "NSE", "isin": "X1"},
    "ANDHRSUGAR.NS": {"name": "Andhra Sugars", "exchange": "NSE", "isin": "X2"},
    "BHARATGEAR.NS": {"name": "Bharat Gears", "exchange": "NSE", "isin": "X3"},
    "JAYBARMARU.NS": {"name": "Jay Bharat", "exchange": "NSE", "isin": "X4"},
    "MAHLOG.NS": {"name": "Mahindra Logistics", "exchange": "NSE", "isin": "X5"},
    "PFOCUS.NS": {"name": "Prime Focus", "exchange": "NSE", "isin": "X6"},
    "TMCV.NS": {"name": "TMCV", "exchange": "NSE", "isin": "X7"},
    "ABC.BO": {"name": "Abc", "exchange": "BSE", "isin": "X8"},
}
OPENING = [
    ("ANDHRSUGAR.NS", 1571, 95.49), ("APLAPOLLO.NS", 20, 2202.38),
    ("BHARATGEAR.NS", 1051, 100.84), ("JAYBARMARU.NS", 666, 133.03),
    ("MAHLOG.NS", 317, 418.56), ("PFOCUS.NS", 358, 355.87),
    ("TMCV.NS", 132, 458.80),
]


def buy(symbol="APLAPOLLO.NS", qty=10, price=100.0, d="2026-01-05", charges=0.0, **kw):
    tx = {"type": "BUY", "symbol": symbol, "exchange": "NSE", "trade_date": d,
          "price": price, "quantity": qty, "charges": charges,
          "strategy": "momentum_edge", "source": "manual"}
    tx.update(kw)
    return tx


def sell(symbol="APLAPOLLO.NS", qty=5, price=120.0, d="2026-02-05", charges=0.0, **kw):
    return buy(symbol, qty, price, d, charges, type="SELL", **kw)


def opening(symbol, qty, price, as_of="2026-11-08"):
    return {"type": "BUY", "symbol": symbol, "exchange": "NSE", "trade_date": None,
            "date_known": False, "as_of": as_of, "price": price, "quantity": qty,
            "charges": None, "strategy": "other", "source": "opening_balance"}


@pytest.fixture
def path(tmp_path):
    return tmp_path / "portfolio" / "ledger.json"


def add(path, tx):
    return pf.append_transaction(path, tx, universe=UNIVERSE, today=TODAY,
                                 strategy_version="hash123")


# ---------------- accounting ----------------

def test_two_buys_partial_sell_fifo_exact(path):
    add(path, buy(qty=10, price=100.0, d="2026-01-05", charges=10.0))
    add(path, buy(qty=10, price=110.0, d="2026-01-10", charges=20.0))
    add(path, sell(qty=15, price=120.0, d="2026-02-05", charges=30.0))
    pos = pf.positions(pf.load_ledger(path))["APLAPOLLO.NS"]
    # gross: 10*(120-100) + 5*(120-110) = 250 ; charges: 30 sell + 10 + 10 (5/10 of 20)
    assert pos.open_qty == 5
    assert pos.closed is False
    assert pos.realised_charges == 50.00
    assert pos.realised_pnl == 200.00
    assert pos.avg_price == 110.00
    assert pos.avg_price_incl_charges == 112.00
    assert pos.lots == [{"buy_id": pos.lots[0]["buy_id"], "date": "2026-01-10",
                         "price": 110.0, "qty": 5, "charges_alloc": 10.0,
                         "date_known": True, "source": "manual"}]
    assert pos.first_buy_date == "2026-01-10"
    assert pos.date_known is True


def test_full_close_keeps_realised(path):
    add(path, buy(qty=10, price=100.0))
    add(path, sell(qty=10, price=90.5, charges=1.25))
    pos = pf.positions(pf.load_ledger(path))["APLAPOLLO.NS"]
    assert pos.closed is True and pos.open_qty == 0 and pos.lots == []
    assert pos.realised_pnl == -96.25
    assert pos.avg_price == 0.0


def test_void_buy_recomputes_position(path):
    b1 = add(path, buy(qty=10, price=100.0))
    b2 = add(path, buy(qty=10, price=200.0, d="2026-01-10"))
    add(path, {"type": "VOID", "voids": b2["id"], "symbol": "APLAPOLLO.NS",
               "exchange": "NSE"})
    pos = pf.positions(pf.load_ledger(path))["APLAPOLLO.NS"]
    assert pos.open_qty == 10 and pos.avg_price == 100.0
    assert pos.lots[0]["buy_id"] == b1["id"]


def test_void_of_buy_needed_by_a_sell_is_rejected(path):
    b1 = add(path, buy(qty=10))
    add(path, sell(qty=5))
    with pytest.raises(pf.LedgerValidationError):
        add(path, {"type": "VOID", "voids": b1["id"], "symbol": "APLAPOLLO.NS",
                   "exchange": "NSE"})


def test_void_unknown_or_double_void_rejected(path):
    b1 = add(path, buy())
    add(path, {"type": "VOID", "voids": b1["id"], "symbol": "APLAPOLLO.NS", "exchange": "NSE"})
    with pytest.raises(pf.LedgerValidationError):
        add(path, {"type": "VOID", "voids": b1["id"], "symbol": "APLAPOLLO.NS", "exchange": "NSE"})
    with pytest.raises(pf.LedgerValidationError):
        add(path, {"type": "VOID", "voids": "nope", "symbol": "APLAPOLLO.NS", "exchange": "NSE"})


# ---------------- opening balances ----------------

def test_seven_opening_balances_fixture(path):
    for sym, q, p in OPENING:
        add(path, opening(sym, q, p))
    pos = pf.positions(pf.load_ledger(path))
    assert len(pos) == 7
    t = pos["TMCV.NS"]
    assert t.open_qty == 132 and t.avg_price == 458.80
    assert t.date_known is False and t.first_buy_date is None
    assert t.avg_price_incl_charges is None
    assert t.lots[0]["charges_alloc"] is None and t.lots[0]["date"] is None


def test_opening_balance_then_dated_sell(path):
    add(path, opening("APLAPOLLO.NS", 20, 2202.38, as_of="2026-11-01"))
    add(path, sell(qty=8, price=2300.00, d="2026-11-07", charges=40.0))
    pos = pf.positions(pf.load_ledger(path))["APLAPOLLO.NS"]
    # 8 * (2300 - 2202.38) = 780.96 ; buy charges unknown
    assert pos.open_qty == 12
    assert pos.realised_charges is None
    assert pos.charges_known is False
    assert pos.realised_pnl == 740.96  # gross less the known sell charges
    assert pos.date_known is False and pos.first_buy_date is None


def test_opening_balance_then_later_buy_fifo_order(path):
    add(path, opening("APLAPOLLO.NS", 20, 2000.0, as_of="2026-10-01"))
    add(path, buy(qty=10, price=2100.0, d="2026-11-01", charges=5.0))
    add(path, sell(qty=22, price=2200.0, d="2026-11-05", charges=0.0))
    pos = pf.positions(pf.load_ledger(path))["APLAPOLLO.NS"]
    assert pos.open_qty == 8
    assert pos.lots[0]["price"] == 2100.0 and pos.lots[0]["qty"] == 8
    assert pos.lots[0]["charges_alloc"] == 4.0
    assert pos.date_known is True and pos.first_buy_date == "2026-11-01"
    # 20*200 + 2*100 = 4200 ; buy charges of the dated lot sold: 1.0 ; opening unknown
    assert pos.realised_pnl == 4199.00
    assert pos.realised_charges is None


def test_manual_buy_null_trade_date_rejected():
    tx = buy()
    tx["trade_date"] = None
    errs = pf.validate_transaction(tx, [], UNIVERSE, today=TODAY)
    assert any("trade_date" in e for e in errs)


def test_null_charges_only_for_opening_balance():
    tx = buy(charges=None)
    assert any("charges" in e for e in pf.validate_transaction(tx, [], UNIVERSE, today=TODAY))
    ok = opening("TMCV.NS", 132, 458.80)
    assert pf.validate_transaction(ok, [], UNIVERSE, today=TODAY) == []


def test_opening_balance_requires_as_of_and_is_buy_only():
    tx = opening("TMCV.NS", 1, 1.0)
    del tx["as_of"]
    assert any("as_of" in e for e in pf.validate_transaction(tx, [], UNIVERSE, today=TODAY))
    tx = opening("TMCV.NS", 1, 1.0)
    tx["type"] = "SELL"
    assert pf.validate_transaction(tx, [], UNIVERSE, today=TODAY)


# ---------------- validation ----------------

def test_sell_more_than_open_rejected(path):
    add(path, buy(qty=10))
    with pytest.raises(pf.LedgerValidationError):
        add(path, sell(qty=11))
    assert len(pf.load_ledger(path)) == 1


def test_backdated_sell_before_buy_rejected(path):
    add(path, buy(qty=10, d="2026-03-01"))
    assert pf.validate_transaction(sell(qty=5, d="2026-02-01"), pf.load_ledger(path),
                                   UNIVERSE, today=TODAY)


def test_unknown_symbol_and_exchange_mismatch_rejected():
    assert pf.validate_transaction(buy(symbol="NOPE.NS"), [], UNIVERSE, today=TODAY)
    assert pf.validate_transaction(buy(symbol="ABC.BO"), [], UNIVERSE, today=TODAY)  # exchange NSE
    assert pf.validate_transaction(buy(symbol="ABC.BO", exchange="BSE"), [], UNIVERSE, today=TODAY) == []


def test_future_date_rejected():
    assert pf.validate_transaction(buy(d="2026-11-09"), [], UNIVERSE, today=TODAY)
    assert pf.validate_transaction(buy(d="2026-11-08"), [], UNIVERSE, today=TODAY) == []


@pytest.mark.parametrize("field,value", [
    ("price", 0), ("price", -1), ("price", float("nan")), ("price", "x"),
    ("quantity", 0), ("quantity", 1.5), ("quantity", True), ("charges", -1),
    ("trade_date", "05-01-2026"), ("notes", "x" * 501), ("strategy", "magic"),
    ("source", "alien"),
])
def test_bad_fields_rejected(field, value):
    tx = buy()
    tx[field] = value
    assert pf.validate_transaction(tx, [], UNIVERSE, today=TODAY)


# ---------------- persistence ----------------

def test_restart_roundtrip(path):
    add(path, buy(qty=10))
    add(path, sell(qty=4))
    first = pf.positions(pf.load_ledger(path))
    again = pf.positions(pf.load_ledger(path))
    assert first == again
    raw = json.loads(path.read_text())
    assert raw["version"] == 1 and len(raw["transactions"]) == 2
    tx = raw["transactions"][0]
    assert tx["id"] and tx["created_at"] and tx["strategy_version"] == "hash123"


def test_missing_file_is_empty_ledger(path):
    assert pf.load_ledger(path) == []


def test_corrupt_file_raises_and_is_untouched(path):
    path.parent.mkdir(parents=True)
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(pf.LedgerCorrupt):
        pf.load_ledger(path)
    with pytest.raises(pf.LedgerCorrupt):
        add(path, buy())
    assert path.read_text(encoding="utf-8") == "{not json"


def test_bad_version_raises(path):
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"version": 99, "transactions": []}), encoding="utf-8")
    with pytest.raises(pf.LedgerCorrupt):
        pf.load_ledger(path)


def test_backup_once_per_day(path):
    add(path, buy(qty=1))          # no ledger yet -> nothing to back up
    pf.append_transaction(path, buy(qty=2), universe=UNIVERSE, today=TODAY,
                          strategy_version="h", now=_dt("2026-11-08T09:00:00"))
    pf.append_transaction(path, buy(qty=3), universe=UNIVERSE, today=TODAY,
                          strategy_version="h", now=_dt("2026-11-08T10:00:00"))
    backups = sorted((path.parent / "backups").glob("ledger-*.json"))
    assert [b.name for b in backups] == ["ledger-2026-11-08.json"]
    # the backup holds the state before the first write of that day (1 tx)
    assert len(json.loads(backups[0].read_text())["transactions"]) == 1
    pf.append_transaction(path, buy(qty=4), universe=UNIVERSE, today=date(2026, 11, 9),
                          strategy_version="h", now=_dt("2026-11-09T09:00:00"))
    assert len(list((path.parent / "backups").glob("ledger-*.json"))) == 2


def test_backups_pruned_to_14(path):
    add(path, buy(qty=1))
    bdir = path.parent / "backups"
    bdir.mkdir(exist_ok=True)
    for i in range(1, 20):
        (bdir / f"ledger-2026-10-{i:02d}.json").write_text("{}")
    add(path, buy(qty=1))
    assert len(list(bdir.glob("ledger-*.json"))) == 14


def _dt(s):
    from datetime import datetime
    return datetime.fromisoformat(s)


# ---------------- costs, settings, universe ----------------

def test_estimated_exit_costs_nse_100000():
    s = pf.load_settings("does-not-exist.json")
    c = pf.estimated_exit_costs("APLAPOLLO.NS", "NSE", 100, 1000.0, s)
    assert c["turnover"] == 100000.00
    assert c["brokerage"] == 0.00
    assert c["stt"] == 100.00
    assert c["exchange_txn"] == 2.97
    assert c["sebi"] == 0.10
    assert c["gst"] == 0.55
    assert c["stamp_duty"] == 0.00
    assert c["dp_charge"] == 15.93
    assert c["total"] == 119.55
    assert c["is_estimate"] is True
    assert c["as_of"] == "2026-11-08"


def test_bse_exchange_rate():
    s = pf.load_settings("does-not-exist.json")
    c = pf.estimated_exit_costs("ABC.BO", "BSE", 100, 1000.0, s)
    assert c["exchange_txn"] == 3.75


def test_load_settings_merges_overrides(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"charges": {"dp_charge_per_sell": 20}}), encoding="utf-8")
    s = pf.load_settings(p)
    assert s["charges"]["dp_charge_per_sell"] == 20
    assert s["charges"]["stt_sell_pct"] == 0.1


def test_universe_index_real_file():
    idx = pf.universe_index()
    assert idx["APLAPOLLO.NS"]["exchange"] == "NSE"
    assert set(idx["APLAPOLLO.NS"]) == {"name", "exchange", "isin"}
    assert len(idx) > 1000


# ---------------- fix round 1 ----------------

def test_sell_before_opening_as_of_rejected(path):
    add(path, opening("APLAPOLLO.NS", 20, 2000.0, as_of="2026-11-05"))
    errs = pf.validate_transaction(sell(qty=1, d="2026-11-04"), pf.load_ledger(path),
                                   UNIVERSE, today=TODAY)
    assert any("opening balance" in e and "double count" in e for e in errs)
    assert pf.validate_transaction(sell(qty=1, d="2026-11-05"), pf.load_ledger(path),
                                   UNIVERSE, today=TODAY) == []


def test_unknown_key_rejected_and_never_stored(path):
    with pytest.raises(pf.LedgerValidationError) as ei:
        add(path, buy(hack="x" * 10000))
    assert "hack" in str(ei.value)
    assert not path.exists()


def test_long_string_rejected_on_any_field():
    assert pf.validate_transaction(buy(signal_ref="x" * 501), [], UNIVERSE, today=TODAY)


def test_stored_record_only_whitelisted_keys(path):
    stored = add(path, buy())
    assert set(stored) <= pf._TRADE_KEYS | {"id", "created_at"}


@pytest.mark.parametrize("missing", ["symbol", "quantity", "price", "type", "id"])
def test_load_rejects_entry_missing_required_key(path, missing):
    add(path, buy())
    raw = json.loads(path.read_text())
    del raw["transactions"][0][missing]
    path.write_text(json.dumps(raw))
    with pytest.raises(pf.LedgerCorrupt):
        pf.load_ledger(path)


def test_version_true_rejected(path):
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"version": True, "transactions": []}))
    with pytest.raises(pf.LedgerCorrupt):
        pf.load_ledger(path)


def test_no_negative_zero(path):
    add(path, buy(qty=1, price=100.0))
    add(path, sell(qty=1, price=100.0))
    pos = pf.positions(pf.load_ledger(path))["APLAPOLLO.NS"]
    import math
    assert pos.realised_pnl == 0.0 and math.copysign(1, pos.realised_pnl) == 1.0
    from decimal import Decimal
    assert math.copysign(1, pf._money(Decimal("-0.001"))) == 1.0
