"""Persistent portfolio ledger: validation and FIFO accounting.

The ledger is an append-only JSON file (``portfolio/ledger.json``).  Mistakes
are corrected with VOID transactions; nothing is ever deleted.  A generated
signal never creates a transaction.

Money is computed with ``Decimal`` and rounded half-up to 2 dp (paise) on
output.  Per-share averages are rounded to 4 dp.  A ``None`` charge means
"not recorded" (opening balances only) and is propagated as ``None`` -- never
treated as 0.
"""
from __future__ import annotations

import csv
import json
import math
import os
import shutil
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

LEDGER_VERSION = 1
BACKUPS_KEPT = 14
MAX_TEXT = 500
TX_TYPES = ("BUY", "SELL", "VOID")
STRATEGIES = ("momentum_edge", "other")
SOURCES = ("manual", "signal", "import", "opening_balance")
EXCHANGES = ("NSE", "BSE")

_ROOT = Path(__file__).resolve().parent.parent
UNIVERSE_CSV = _ROOT / "data" / "universe" / "combined_universe.csv"

_CENT = Decimal("0.01")
_PRICE = Decimal("0.0001")
_ZERO = Decimal(0)

DEFAULT_SETTINGS: dict[str, Any] = {
    "charges": {
        "as_of": "2026-11-08",
        "note": "Estimates for Indian equity delivery; verify with your broker.",
        "brokerage_pct": 0.0,
        "stt_buy_pct": 0.1,
        "stt_sell_pct": 0.1,
        "exchange_txn_pct": {"NSE": 0.00297, "BSE": 0.00375},
        "sebi_pct": 0.0001,
        "stamp_buy_pct": 0.015,
        "gst_pct": 18.0,
        "dp_charge_per_sell": 15.93,
    },
    "bands": {"hard_stop_pct": 15.0, "ema_review_pct": 3.0, "stop_review_pct": 3.0},
    "monitor": {"experimental_reduce": False},
}


class LedgerCorrupt(Exception):
    """The ledger file is unreadable or has an unsupported version."""


class LedgerValidationError(ValueError):
    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


# --------------------------------------------------------------- helpers

def _dec(x: Any) -> Decimal:
    return Decimal(str(x))


def _money(d: Decimal) -> float:
    return float(d.quantize(_CENT, rounding=ROUND_HALF_UP)) + 0.0  # -0.0 + 0.0 == 0.0


def _price(d: Decimal) -> float:
    return float(d.quantize(_PRICE, rounding=ROUND_HALF_UP))


def _parse_date(s: Any) -> date | None:
    if not isinstance(s, str) or len(s) != 10:
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def _is_num(x: Any) -> bool:
    return (isinstance(x, (int, float, str)) and not isinstance(x, bool)
            and _finite(x))


def _finite(x: Any) -> bool:
    try:
        return math.isfinite(float(x))
    except (TypeError, ValueError):
        return False


def _atomic_write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


# --------------------------------------------------------------- persistence

def load_ledger(path: str | Path) -> list[dict]:
    """Return the transactions.  Missing file -> []; bad file -> LedgerCorrupt.

    A corrupt file is left untouched; a copy is saved under ``backups/``.
    """
    p = Path(path)
    if not p.exists():
        return []
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        ver = raw.get("version") if isinstance(raw, dict) else None
        if not isinstance(raw, dict) or isinstance(ver, bool) or ver != LEDGER_VERSION:
            raise ValueError(f"unsupported ledger version: {raw.get('version') if isinstance(raw, dict) else None!r}")
        txs = raw.get("transactions")
        if not isinstance(txs, list) or not all(isinstance(t, dict) for t in txs):
            raise ValueError("transactions must be a list of objects")
        for i, t in enumerate(txs):
            bad = _shape_error(t)
            if bad:
                raise ValueError(f"transaction #{i}: {bad}")
    except (OSError, ValueError) as exc:  # JSONDecodeError is a ValueError
        _save_corrupt_copy(p)
        raise LedgerCorrupt(f"{p}: {exc}") from exc
    return txs


def _shape_error(t: dict) -> str | None:
    """Minimal structural check of a stored entry (None when usable)."""
    if not isinstance(t.get("id"), str) or not t["id"]:
        return "missing id"
    if t.get("type") not in TX_TYPES:
        return "bad or missing type"
    if t["type"] == "VOID":
        return None if isinstance(t.get("voids"), str) else "VOID missing voids"
    if not isinstance(t.get("symbol"), str) or not t["symbol"]:
        return "missing symbol"
    q = t.get("quantity")
    if isinstance(q, bool) or not isinstance(q, int) or q <= 0:
        return "bad quantity"
    if not _is_num(t.get("price")) or _dec(t["price"]) <= 0:
        return "bad price"
    if t.get("charges") is not None and not _is_num(t["charges"]):
        return "bad charges"
    if t.get("source") == "opening_balance":
        if _parse_date(t.get("as_of")) is None:
            return "opening balance missing as_of"
    elif _parse_date(t.get("trade_date")) is None:
        return "bad or missing trade_date"
    return None


def _save_corrupt_copy(p: Path) -> None:
    try:
        bdir = p.parent / "backups"
        bdir.mkdir(parents=True, exist_ok=True)
        target = bdir / f"ledger-corrupt-{p.stat().st_size}-{int(p.stat().st_mtime)}.json"
        if not target.exists():
            shutil.copy2(p, target)
    except OSError:
        pass


def _daily_backup(p: Path, now: datetime) -> None:
    if not p.exists():
        return
    bdir = p.parent / "backups"
    bdir.mkdir(parents=True, exist_ok=True)
    target = bdir / f"ledger-{now.date().isoformat()}.json"
    if not target.exists():
        shutil.copy2(p, target)
    dated = sorted(b for b in bdir.glob("ledger-????-??-??.json"))
    for old in dated[:-BACKUPS_KEPT]:
        old.unlink(missing_ok=True)


def append_transaction(path: str | Path, tx: dict, universe: dict | None = None,
                       today: date | None = None, strategy_version: str | None = None,
                       now: datetime | None = None) -> dict:
    """Validate and append ``tx``; returns the stored transaction."""
    p = Path(path)
    now = now or datetime.now()
    ledger = load_ledger(p)  # raises LedgerCorrupt before anything is written
    uni = universe if universe is not None else universe_index()
    errors = validate_transaction(tx, ledger, uni, today=today or now.date())
    if errors:
        raise LedgerValidationError(errors)
    stored = _normalise(tx)
    stored["id"] = str(uuid.uuid4())
    stored["created_at"] = now.isoformat(timespec="seconds")
    if stored["type"] != "VOID" and not stored.get("strategy_version"):
        stored["strategy_version"] = strategy_version or _current_strategy_version()
    _daily_backup(p, now)
    _atomic_write(p, {"version": LEDGER_VERSION, "transactions": ledger + [stored]})
    return stored


def _current_strategy_version() -> str:
    try:
        import momentum_edge_backtest as meb
        return meb._cfg_hash(meb.CFG)
    except Exception:  # noqa: BLE001 - version tag must never block a write
        return "unknown"


_BASE_KEYS = {"type", "notes", "source", "trade_date", "voids"}
_TRADE_KEYS = _BASE_KEYS | {"symbol", "exchange", "price", "quantity", "charges",
                            "strategy", "strategy_version", "signal_ref",
                            "date_known", "as_of"}
_VOID_KEYS = _BASE_KEYS | {"symbol", "exchange"}


def _allowed_keys(ttype: str) -> set[str]:
    return _VOID_KEYS if ttype == "VOID" else _TRADE_KEYS


def _normalise(tx: dict) -> dict:
    out = {k: v for k, v in tx.items() if k in _allowed_keys(tx["type"])}
    t = out["type"]
    if t == "VOID":
        out.setdefault("notes", "")
        return out
    out.setdefault("signal_ref", None)
    out.setdefault("notes", "")
    out.setdefault("voids", None)
    out.setdefault("source", "manual")
    out.setdefault("strategy", "other")
    out["quantity"] = int(out["quantity"])
    out["price"] = float(out["price"])
    if out.get("charges") is not None:
        out["charges"] = float(out["charges"])
    if out["source"] == "opening_balance":
        out["date_known"] = out.get("trade_date") is not None
        out.setdefault("as_of", None)
    else:
        out["date_known"] = True
    return out


# --------------------------------------------------------------- validation

def validate_transaction(tx: dict, ledger: list[dict], universe: dict,
                         today: date | None = None) -> list[str]:
    """Return a list of human-readable errors (empty means valid)."""
    today = today or date.today()
    if not isinstance(tx, dict):
        return ["transaction must be an object"]
    ttype = tx.get("type")
    if ttype not in TX_TYPES:
        return [f"type must be one of {TX_TYPES}"]
    errs = _check_text_fields(tx)
    if ttype == "VOID":
        errs += _check_void(tx, ledger)
    else:
        errs += _check_trade_fields(tx, universe, today)
    if errs:
        return errs
    errs = _check_sell_vs_opening(tx, ledger)
    if errs:
        return errs
    # Replay the ledger with the candidate to catch oversells (incl. backdated
    # sells and voids of buys that later sells depend on).
    _, replay_errs = _replay(list(ledger) + [dict(tx, id="__candidate__")])
    return replay_errs


def _check_sell_vs_opening(tx: dict, ledger: list[dict]) -> list[str]:
    if tx["type"] != "SELL":
        return []
    for _, b in _active(ledger):
        if (b["type"] == "BUY" and b.get("source") == "opening_balance"
                and b.get("symbol") == tx["symbol"]
                and (b.get("as_of") or "") > tx["trade_date"]):
            return [f"SELL dated {tx['trade_date']} is before the opening balance "
                    f"as_of {b['as_of']} for {tx['symbol']}; that balance already "
                    f"reflects earlier sales, so entering it would double count"]
    return []


def _check_text_fields(tx: dict) -> list[str]:
    errs = []
    extra = sorted(str(k) for k in set(tx) - _allowed_keys(tx["type"]))
    if extra:
        errs.append(f"unknown field(s) not allowed: {', '.join(extra)[:100]}")
    for k in ("notes", "signal_ref", "symbol", "voids", "strategy_version"):
        v = tx.get(k)
        if v is not None and not isinstance(v, str):
            errs.append(f"{k} must be a string")
    for k, v in tx.items():
        if isinstance(v, str) and len(v) > MAX_TEXT:
            errs.append(f"{k} must be at most {MAX_TEXT} characters")
    return errs


def _check_void(tx: dict, ledger: list[dict]) -> list[str]:
    target = tx.get("voids")
    if not isinstance(target, str) or not target:
        return ["voids must reference a transaction id"]
    orig = next((t for t in ledger if t.get("id") == target), None)
    if orig is None:
        return [f"voids: no transaction with id {target}"]
    if orig.get("type") == "VOID":
        return ["a VOID cannot be voided"]
    if any(t.get("type") == "VOID" and t.get("voids") == target for t in ledger):
        return [f"transaction {target} is already voided"]
    return []


def _check_trade_fields(tx: dict, universe: dict, today: date) -> list[str]:
    errs: list[str] = []
    ttype = tx["type"]
    source = tx.get("source", "manual")
    opening = source == "opening_balance"
    if source not in SOURCES:
        errs.append(f"source must be one of {SOURCES}")
    if tx.get("strategy", "other") not in STRATEGIES:
        errs.append(f"strategy must be one of {STRATEGIES}")
    errs += _check_symbol(tx, universe)
    errs += _check_dates(tx, today, opening, ttype)
    if not _is_num(tx.get("price")) or _dec(tx["price"]) <= 0:
        errs.append("price must be a number > 0")
    qty = tx.get("quantity")
    if (isinstance(qty, bool) or not isinstance(qty, int) or qty <= 0):
        errs.append("quantity must be an integer > 0")
    charges = tx.get("charges")
    if charges is None:
        if not opening:
            errs.append("charges are required (use 0 if none) unless source is opening_balance")
    elif not _is_num(charges) or _dec(charges) < 0:
        errs.append("charges must be a number >= 0")
    return errs


def _check_symbol(tx: dict, universe: dict) -> list[str]:
    sym, exch = tx.get("symbol"), tx.get("exchange")
    if exch not in EXCHANGES:
        return [f"exchange must be one of {EXCHANGES}"]
    if not isinstance(sym, str) or sym not in universe:
        return [f"symbol {sym!r} is not in the universe"]
    if universe[sym].get("exchange") != exch:
        return [f"symbol {sym} trades on {universe[sym].get('exchange')}, not {exch}"]
    return []


def _check_dates(tx: dict, today: date, opening: bool, ttype: str) -> list[str]:
    errs: list[str] = []
    td = tx.get("trade_date")
    if opening:
        if ttype != "BUY":
            errs.append("opening_balance is only valid for BUY")
        d = _parse_date(tx.get("as_of"))
        if d is None:
            errs.append("as_of (YYYY-MM-DD) is required for opening_balance")
        elif d > today:
            errs.append("as_of cannot be in the future")
        if td is not None:
            errs += _check_one_date("trade_date", td, today)
        elif tx.get("date_known") not in (False, None):
            errs.append("date_known must be false when trade_date is null")
        return errs
    if td is None:
        return ["trade_date is required unless source is opening_balance"]
    return _check_one_date("trade_date", td, today)


def _check_one_date(name: str, value: Any, today: date) -> list[str]:
    d = _parse_date(value)
    if d is None:
        return [f"{name} must be an ISO date YYYY-MM-DD"]
    if d > today:
        return [f"{name} cannot be in the future"]
    return []


# --------------------------------------------------------------- accounting

@dataclass
class Position:
    symbol: str
    exchange: str
    open_qty: int
    lots: list[dict]
    avg_price: float
    avg_price_incl_charges: float | None
    realised_pnl: float
    realised_charges: float | None   # None when any consumed buy lot had unrecorded charges
    charges_known: bool              # False -> realised_pnl excludes unrecorded buy charges
    first_buy_date: str | None
    date_known: bool
    closed: bool
    allocated_charges: float | None = None  # buy charges of open lots; None if unknown
    realised_gross: float = 0.0
    sell_count: int = 0
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return dict(self.__dict__)


def _lot_sort_key(tx: dict, idx: int) -> tuple:
    if tx.get("source") == "opening_balance":
        return (0, tx.get("as_of") or "", idx)
    return (1, tx.get("trade_date") or "", 0 if tx["type"] == "BUY" else 1, idx)


def _active(ledger: list[dict]) -> list[tuple[int, dict]]:
    voided = {t.get("voids") for t in ledger if t.get("type") == "VOID"}
    return [(i, t) for i, t in enumerate(ledger)
            if t.get("type") in ("BUY", "SELL") and t.get("id") not in voided]


def positions(ledger: list[dict]) -> dict[str, Position]:
    """Replay the ledger (FIFO) into one Position per symbol, closed ones included."""
    return _replay(ledger)[0]


class _State:
    def __init__(self, exchange: str):
        self.exchange = exchange
        self.lots: list[dict] = []        # open lots (Decimal fields)
        self.all_buys: list[dict] = []
        self.gross = _ZERO
        self.sell_charges = _ZERO
        self.buy_charges_used = _ZERO
        self.unknown_charges = False
        self.sells = 0


def _replay(ledger: list[dict]) -> tuple[dict[str, Position], list[str]]:
    states: dict[str, _State] = {}
    errors: list[str] = []
    ordered = sorted(_active(ledger), key=lambda it: _lot_sort_key(it[1], it[0]))
    for _, tx in ordered:
        st = states.setdefault(tx["symbol"], _State(tx.get("exchange", "")))
        if tx["type"] == "BUY":
            _apply_buy(st, tx)
        else:
            err = _apply_sell(st, tx)
            if err:
                errors.append(err)
    return {s: _to_position(s, st) for s, st in states.items()}, errors


def _apply_buy(st: _State, tx: dict) -> None:
    known = tx.get("trade_date") is not None
    lot = {
        "buy_id": tx.get("id"), "date": tx.get("trade_date"),
        "price": _dec(tx["price"]), "orig_qty": int(tx["quantity"]),
        "qty": int(tx["quantity"]),
        "charges": None if tx.get("charges") is None else _dec(tx["charges"]),
        "date_known": known, "source": tx.get("source", "manual"),
    }
    st.lots.append(lot)
    st.all_buys.append(lot)


def _apply_sell(st: _State, tx: dict) -> str | None:
    want = int(tx["quantity"])
    have = sum(lot["qty"] for lot in st.lots)
    err = None
    if want > have:
        err = (f"SELL of {want} {tx['symbol']} exceeds open quantity {have}"
               f" on {tx.get('trade_date')}")
        want = have
    price = _dec(tx["price"])
    left = want
    while left > 0:
        lot = st.lots[0]
        take = min(left, lot["qty"])
        st.gross += (price - lot["price"]) * take
        if lot["charges"] is None:
            st.unknown_charges = True
        else:
            st.buy_charges_used += lot["charges"] * take / lot["orig_qty"]
        lot["qty"] -= take
        left -= take
        if lot["qty"] == 0:
            st.lots.pop(0)
    st.sell_charges += _dec(tx.get("charges") or 0)
    st.sells += 1
    return err


def _to_position(symbol: str, st: _State) -> Position:
    open_qty = sum(lot["qty"] for lot in st.lots)
    cost = sum((lot["price"] * lot["qty"] for lot in st.lots), _ZERO)
    unknown_open = any(lot["charges"] is None for lot in st.lots)
    alloc = None if unknown_open else sum(
        (lot["charges"] * lot["qty"] / lot["orig_qty"] for lot in st.lots), _ZERO)
    basis = st.lots if st.lots else st.all_buys
    dates = [lot["date"] for lot in basis if lot["date_known"]]
    date_known = all(lot["date_known"] for lot in basis)
    realised_charges = st.sell_charges + st.buy_charges_used
    return Position(
        symbol=symbol, exchange=st.exchange, open_qty=open_qty,
        lots=[_lot_out(lot) for lot in st.lots],
        avg_price=_price(cost / open_qty) if open_qty else 0.0,
        avg_price_incl_charges=(_price((cost + alloc) / open_qty)
                                if open_qty and alloc is not None else None),
        realised_pnl=_money(st.gross - realised_charges),
        realised_charges=None if st.unknown_charges else _money(realised_charges),
        charges_known=not st.unknown_charges,
        first_buy_date=min(dates) if dates and date_known else None,
        date_known=date_known, closed=open_qty == 0 and bool(st.all_buys),
        allocated_charges=None if alloc is None else _money(alloc),
        realised_gross=_money(st.gross), sell_count=st.sells,
    )


def _lot_out(lot: dict) -> dict:
    alloc = (None if lot["charges"] is None
             else _money(lot["charges"] * lot["qty"] / lot["orig_qty"]))
    return {"buy_id": lot["buy_id"], "date": lot["date"], "price": float(lot["price"]),
            "qty": lot["qty"], "charges_alloc": alloc,
            "date_known": lot["date_known"], "source": lot["source"]}


# --------------------------------------------------------------- settings / costs

def _merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in over.items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def load_settings(path: str | Path) -> dict:
    """Defaults (Decision 4) merged with the user's ``settings.json`` if present."""
    p = Path(path)
    defaults = json.loads(json.dumps(DEFAULT_SETTINGS))
    if not p.exists():
        return defaults
    try:
        user = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise LedgerCorrupt(f"{p}: {exc}") from exc
    return _merge(defaults, user) if isinstance(user, dict) else defaults


def estimated_exit_costs(symbol: str, exchange: str, qty: int, price: float,
                         settings: dict) -> dict:
    """Itemised estimate of selling ``qty`` at ``price``; never mixed with incurred charges."""
    c = settings["charges"]
    turnover = _dec(price) * int(qty)

    def pct(rate: Any) -> Decimal:
        return (turnover * _dec(rate) / 100).quantize(_CENT, rounding=ROUND_HALF_UP)

    brokerage = pct(c["brokerage_pct"])
    stt = pct(c["stt_sell_pct"])
    exch = pct(c["exchange_txn_pct"][exchange])
    sebi = pct(c["sebi_pct"])
    gst = ((brokerage + exch + sebi) * _dec(c["gst_pct"]) / 100).quantize(
        _CENT, rounding=ROUND_HALF_UP)
    dp = _dec(c["dp_charge_per_sell"]).quantize(_CENT, rounding=ROUND_HALF_UP)
    total = brokerage + stt + exch + sebi + gst + dp
    return {
        "symbol": symbol, "exchange": exchange, "quantity": int(qty),
        "price": float(price), "turnover": _money(turnover),
        "brokerage": _money(brokerage), "stt": _money(stt),
        "exchange_txn": _money(exch), "sebi": _money(sebi), "gst": _money(gst),
        "stamp_duty": 0.0, "dp_charge": _money(dp), "total": _money(total),
        "is_estimate": True, "as_of": c.get("as_of"), "note": c.get("note"),
    }


# --------------------------------------------------------------- universe

def universe_index(path: str | Path | None = None) -> dict[str, dict]:
    """``{symbol: {name, exchange, isin}}`` from combined_universe.csv."""
    out: dict[str, dict] = {}
    with open(path or UNIVERSE_CSV, encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            sym = (row.get("Symbol") or "").strip()
            if sym and sym not in out:
                out[sym] = {"name": (row.get("Name") or "").strip(),
                            "exchange": (row.get("Exchange") or "").strip(),
                            "isin": (row.get("ISIN") or "").strip()}
    return out
