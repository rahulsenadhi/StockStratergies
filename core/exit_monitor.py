"""Evaluate one open holding against the Momentum Edge exit rules (Decision 5).

Pure function of (position, bars, Nifty's last session, now, settings): no file I/O.
``bars_df`` is the frame from ``master_dashboard._compute_full_indicators`` (index =
dates; columns Close, Volume, ema220 ...).  The EMA is NOT recomputed here.

Priority on the latest completed bar:
  DATA UNAVAILABLE > STALE > EXIT (hard stop) > EXIT (EMA220 break) > REVIEW > HOLD
Opening-balance positions (no buy date) skip held-days, peak, drawdown and
reconstruction (reported as null with a reason); the stop and EMA rules still apply.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

IST = timezone(timedelta(hours=5, minutes=30), "IST")
BAR_COMPLETE_AT = time(15, 45)
MIN_BARS = 220          # bars needed to form the EMA220
MATURE_BARS = 440       # below this the EMA220 is still warming up
UNKNOWN_DATE = "buy date unknown"

HARD_STOP_TEXT = ("Exit rule triggered at today's close; earliest action is the next "
                  "session. A stop is a trigger, not a guaranteed price; gaps can fill worse.")
EMA_TEXT = "The model exits at the next session's open."
REVIEW_LABEL = "Advisory, not a model exit."
RECON_LABEL = "Reconstructed from saved prices - no alert existed at the time"


@dataclass
class Evaluation:
    symbol: str
    action: str                       # HOLD | REVIEW | REDUCE | EXIT | STALE | DATA UNAVAILABLE
    rule: str | None
    explanation: str
    levels: dict = field(default_factory=dict)
    last_close: float | None = None
    last_bar_date: str | None = None
    data_status: str = "OK"           # OK | STALE | DATA UNAVAILABLE
    incomplete_bar_ignored: bool = False
    reconstructed_first_exit: dict | None = None
    reconstruction_note: str | None = None
    volume_ratio20: float | None = None
    drawdown_from_peak: float | None = None
    held_days: int | None = None
    strategy: str = "momentum_edge"
    evaluated_at: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _as_ist(now: datetime | None) -> datetime:
    now = now or datetime.now(IST)
    return now.replace(tzinfo=IST) if now.tzinfo is None else now.astimezone(IST)


def completed_cutoff(now: datetime | None) -> date:
    """Latest bar date that may be treated as complete."""
    n = _as_ist(now)
    return n.date() if n.time() >= BAR_COMPLETE_AT else n.date() - timedelta(days=1)


def _iso(d: Any) -> str:
    return d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)[:10]


def _pct(a: float, b: float) -> float:
    return round((a / b - 1.0) * 100.0, 2)


def _base(position: Any, now: datetime | None, **kw: Any) -> Evaluation:
    strategy = (getattr(position, "extra", None) or {}).get("strategy", "momentum_edge")
    return Evaluation(symbol=position.symbol, strategy=strategy,
                      evaluated_at=_as_ist(now).isoformat(timespec="seconds"), **kw)


def _unavailable(position: Any, now: datetime | None, why: str) -> Evaluation:
    return _base(position, now, action="DATA UNAVAILABLE", rule=None, explanation=why,
                 data_status="DATA UNAVAILABLE",
                 reconstruction_note="no price data")


def _trim_bars(bars_df: Any, now: datetime | None) -> tuple[Any, bool]:
    """Drop bars not yet complete.  Returns (bars, incomplete_bar_ignored)."""
    cutoff = completed_cutoff(now)
    dates = [d.date() for d in bars_df.index]
    keep = [i for i, d in enumerate(dates) if d <= cutoff]
    ignored = len(keep) != len(dates)
    return bars_df.iloc[keep], ignored


def _volume_ratio(bars: Any) -> float | None:
    if "Volume" not in bars.columns or len(bars) < 21:
        return None
    avg = float(bars["Volume"].iloc[-21:-1].mean())
    return round(float(bars["Volume"].iloc[-1]) / avg, 2) if avg > 0 else None


def _reconstruct(bars: Any, buy_date: str, stop_level: float) -> dict | None:
    """First bar strictly after the buy date where the stop or EMA rule would fire."""
    for ts, row in bars.iterrows():
        if _iso(ts) <= buy_date:
            continue
        close, ema = float(row["Close"]), float(row["ema220"])
        if close < stop_level:
            return {"date": _iso(ts), "rule": "hard stop", "close": round(close, 2),
                    "level": round(stop_level, 2), "label": RECON_LABEL}
        if close < ema:
            return {"date": _iso(ts), "rule": "EMA220 break", "close": round(close, 2),
                    "level": round(ema, 2), "label": RECON_LABEL}
    return None


def _decide(close: float, ema: float, stop: float, bands: dict) -> tuple[str, str | None, str]:
    if close < stop:
        return "EXIT", "hard stop", HARD_STOP_TEXT
    if close < ema:
        return "EXIT", "EMA220 break", EMA_TEXT
    ema_band = float(bands.get("ema_review_pct", 3.0)) / 100.0
    stop_band = float(bands.get("stop_review_pct", 3.0)) / 100.0
    if close <= ema * (1 + ema_band):
        return ("REVIEW", "near EMA220",
                f"Close is within {bands.get('ema_review_pct', 3.0):g}% above the 220-day EMA. "
                + REVIEW_LABEL)
    if close <= stop * (1 + stop_band):
        return ("REVIEW", "near hard stop",
                f"Close is within {bands.get('stop_review_pct', 3.0):g}% above the hard-stop "
                "level. " + REVIEW_LABEL)
    return "HOLD", None, "No exit rule is triggered on the latest completed bar."


def evaluate_holding(position: Any, bars_df: Any, nifty_last_date: Any,
                     now: datetime | None, settings: dict) -> Evaluation:
    """Evaluate one open position.  Never raises for missing/short data."""
    if (getattr(position, "extra", None) or {}).get("strategy") == "other":
        return _base(position, now, action="REVIEW", rule="no automated rules",
                     explanation="No automated exit rules for this strategy. "
                                 "Review this holding manually.")
    if bars_df is None or len(bars_df) == 0 or "ema220" not in bars_df.columns:
        return _unavailable(position, now, "No price data file found for this symbol.")
    bars, ignored = _trim_bars(bars_df, now)
    if len(bars) < MIN_BARS:
        return _unavailable(position, now,
                            f"Insufficient history: {len(bars)} bars, need {MIN_BARS} "
                            "to form the 220-day EMA.")
    return _evaluate(position, bars, ignored, nifty_last_date, now, settings)


def _evaluate(position: Any, bars: Any, ignored: bool, nifty_last_date: Any,
              now: datetime | None, settings: dict) -> Evaluation:
    bands = settings.get("bands", {})
    last = bars.iloc[-1]
    close, ema = float(last["Close"]), float(last["ema220"])
    last_date = _iso(bars.index[-1])
    stop = position.avg_price * (1 - float(bands.get("hard_stop_pct", 15.0)) / 100.0)
    known = bool(position.date_known and position.first_buy_date)
    levels: dict[str, Any] = {
        "hard_stop": round(stop, 2), "entry_price": position.avg_price,
        "ema220": round(ema, 2), "ema_distance_pct": _pct(close, ema),
        "stop_distance_pct": _pct(close, stop), "bars": len(bars),
        "ema_immature": len(bars) < MATURE_BARS,
        "highest_close_since_entry": None, "peak_note": None if known else UNKNOWN_DATE,
    }
    peak = drawdown = held = recon = note = None
    if known:
        since = bars[[_iso(i) >= position.first_buy_date for i in bars.index]]
        if len(since):
            peak = float(since["Close"].max())
            drawdown = _pct(close, peak)
            levels["highest_close_since_entry"] = round(peak, 2)
        held = (_as_ist(now).date() - date.fromisoformat(position.first_buy_date)).days
        recon = _reconstruct(bars, position.first_buy_date, stop)
        note = None if recon else "no exit rule would have fired since the buy date"
    else:
        note = UNKNOWN_DATE
    action, rule, text = _decide(close, ema, stop, bands)
    status = "OK"
    nifty = _iso(nifty_last_date) if nifty_last_date is not None else None
    if nifty and last_date < nifty:
        status, action, rule = "STALE", "STALE", None
        text = (f"Last price bar is {last_date}, behind the latest market session {nifty}. "
                "Update data before acting on this holding.")
    if levels["ema_immature"]:
        text += f" The 220-day EMA is immature (only {len(bars)} bars of history)."
    if ignored:
        text += " Today's incomplete bar was ignored; the previous completed bar is used."
    return _base(position, now, action=action, rule=rule, explanation=text, levels=levels,
                 last_close=round(close, 2), last_bar_date=last_date, data_status=status,
                 incomplete_bar_ignored=ignored, reconstructed_first_exit=recon,
                 reconstruction_note=note, volume_ratio20=_volume_ratio(bars),
                 drawdown_from_peak=drawdown, held_days=held)
