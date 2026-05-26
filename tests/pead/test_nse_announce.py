import json
from datetime import date

from core.nse_announce import (
    parse_announcements,
    infer_period_type,
    nse_symbol_to_yf,
)


def test_parse_announcements_quarterly(fixtures_dir):
    raw = json.loads((fixtures_dir / "nse_announce_sample.json").read_text())
    events = parse_announcements(raw)
    rel = next(e for e in events if e["symbol"] == "RELIANCE")
    assert rel["result_date"] == date(2026, 4, 21)
    assert rel["period_from"] == date(2026, 1, 1)
    assert rel["period_to"] == date(2026, 3, 31)
    assert rel["period_type"] == "Q"


def test_parse_announcements_annual(fixtures_dir):
    raw = json.loads((fixtures_dir / "nse_announce_sample.json").read_text())
    events = parse_announcements(raw)
    tcs = next(e for e in events if e["symbol"] == "TCS")
    assert tcs["period_type"] == "A"


def test_parse_announcements_unknown_period_dropped(fixtures_dir):
    raw = json.loads((fixtures_dir / "nse_announce_sample.json").read_text())
    events = parse_announcements(raw)
    symbols = {e["symbol"] for e in events}
    assert "INFY" not in symbols  # empty fromDate/toDate -> dropped


def test_infer_period_type_quarter():
    assert infer_period_type(date(2026, 1, 1), date(2026, 3, 31)) == "Q"


def test_infer_period_type_annual():
    assert infer_period_type(date(2025, 4, 1), date(2026, 3, 31)) == "A"


def test_infer_period_type_unknown():
    # 6-month span — neither Q nor A
    assert infer_period_type(date(2025, 10, 1), date(2026, 3, 31)) is None


def test_nse_symbol_to_yf_basic():
    assert nse_symbol_to_yf("RELIANCE") == "RELIANCE.NS"


def test_nse_symbol_to_yf_ampersand():
    assert nse_symbol_to_yf("M&M") == "M&M.NS"  # yfinance handles & directly
