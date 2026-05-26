# PEAD Strategy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Post-Earnings-Announcement-Drift (PEAD) as strategy #4 — daily incremental fundamentals refresh, quarterly + annual SUE, top-decile + Piotroski≥7 + P/B≤sector-median entries, 60d/next-earnings exits, 4-tab Streamlit dashboard.

**Architecture:** Hybrid — shared primitives go into `core/` (sue, piotroski, fundamentals, nse_announce); PEAD-specific scripts at repo root (`pead_downloader.py`, `pead_backtest.py`, `pead_dashboard.py`). Additive — no refactor of existing strategies.

**Tech Stack:** Python 3.11+, pandas, pyarrow, yfinance, requests, streamlit, plotly, pytest.

**Spec:** `docs/superpowers/specs/2026-05-25-pead-strategy-design.md`

---

## Phase 0 — Test Infrastructure

### Task 0.1: Add pytest config + tests/ skeleton

**Files:**
- Create: `pyproject.toml`
- Create: `tests/__init__.py`
- Create: `tests/pead/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create pyproject.toml**

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
addopts = "-v --tb=short"
filterwarnings = [
    "ignore::DeprecationWarning:yfinance",
    "ignore::FutureWarning:pandas",
]

[tool.coverage.run]
source = ["core", "pead_downloader", "pead_backtest"]
omit = ["tests/*"]

[tool.coverage.report]
fail_under = 80
```

- [ ] **Step 2: Create tests/__init__.py and tests/pead/__init__.py**

Both files empty.

- [ ] **Step 3: Create tests/conftest.py**

```python
"""Shared pytest fixtures for PEAD tests."""
from pathlib import Path

import pytest


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parent / "pead" / "fixtures"
```

- [ ] **Step 4: Verify pytest runs**

Run: `pytest --collect-only`
Expected: `no tests ran` (0 collected, no errors).

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml tests/
git commit -m "test: add pytest config and tests/ skeleton for PEAD"
```

---

## Phase 1 — Foundation (core/ primitives)

### Task 1.1: `core/sue.py` — quarterly SUE

**Files:**
- Create: `core/sue.py`
- Test: `tests/pead/test_sue.py`

- [ ] **Step 1: Write failing tests**

`tests/pead/test_sue.py`:

```python
import math

import pytest

from core.sue import quarterly_sue


def test_quarterly_sue_textbook():
    # actual=12, prior=[10,11,9,10] -> mean=10, std=0.8165 (ddof=1)
    sue = quarterly_sue(actual=12.0, prior=[10.0, 11.0, 9.0, 10.0])
    assert math.isclose(sue, (12 - 10) / 0.8164965809277261, rel_tol=1e-6)


def test_quarterly_sue_negative_actual():
    sue = quarterly_sue(actual=-2.0, prior=[5.0, 6.0, 4.0, 5.0])
    assert sue < 0


def test_quarterly_sue_zero_std_returns_nan():
    sue = quarterly_sue(actual=15.0, prior=[10.0, 10.0, 10.0, 10.0])
    assert math.isnan(sue)


def test_quarterly_sue_fewer_than_4_returns_nan():
    sue = quarterly_sue(actual=12.0, prior=[10.0, 11.0, 9.0])
    assert math.isnan(sue)


def test_quarterly_sue_nan_in_prior_returns_nan():
    sue = quarterly_sue(actual=12.0, prior=[10.0, float("nan"), 9.0, 10.0])
    assert math.isnan(sue)


def test_quarterly_sue_nan_actual_returns_nan():
    sue = quarterly_sue(actual=float("nan"), prior=[10.0, 11.0, 9.0, 10.0])
    assert math.isnan(sue)
```

- [ ] **Step 2: Run tests — confirm fail**

Run: `pytest tests/pead/test_sue.py -v`
Expected: ImportError — `core.sue` not found.

- [ ] **Step 3: Implement core/sue.py**

```python
"""SUE (Standardised Unexpected Earnings) math — quarterly + annual flavors."""
from __future__ import annotations

import math
import statistics
from typing import Sequence


def _clean(prior: Sequence[float]) -> list[float] | None:
    """Return list of 4 finite floats, or None if any nan/missing."""
    if len(prior) != 4:
        return None
    out = [float(x) for x in prior]
    if any(math.isnan(x) or math.isinf(x) for x in out):
        return None
    return out


def quarterly_sue(actual: float, prior: Sequence[float]) -> float:
    """SUE = (actual - mean(prior)) / stdev(prior, ddof=1).

    Expects prior = [t-1, t-2, t-3, t-4] (last 4 reported quarters).
    Returns nan if any input is nan, fewer than 4 priors, or zero std.
    """
    if actual is None or math.isnan(float(actual)):
        return math.nan
    cleaned = _clean(prior)
    if cleaned is None:
        return math.nan
    expected = statistics.fmean(cleaned)
    std = statistics.stdev(cleaned)  # ddof=1
    if std == 0:
        return math.nan
    return (float(actual) - expected) / std


def annual_sue(actual: float, prior: Sequence[float]) -> float:
    """SUE for annual EPS. Same formula, prior = last 4 fiscal years."""
    return quarterly_sue(actual, prior)
```

- [ ] **Step 4: Run tests — confirm pass**

Run: `pytest tests/pead/test_sue.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add core/sue.py tests/pead/test_sue.py
git commit -m "feat(pead): add core/sue.py with quarterly_sue + tests"
```

### Task 1.2: `core/sue.py` — annual SUE tests + decile helper

**Files:**
- Modify: `core/sue.py`
- Test: `tests/pead/test_sue.py`

- [ ] **Step 1: Append failing tests**

Append to `tests/pead/test_sue.py`:

```python
from core.sue import annual_sue, assign_deciles


def test_annual_sue_same_as_quarterly():
    a = annual_sue(20.0, [15.0, 16.0, 14.0, 15.0])
    q = quarterly_sue(20.0, [15.0, 16.0, 14.0, 15.0])
    assert a == q


def test_assign_deciles_basic():
    # 30 values, 1..30; decile 10 should be top 3 values.
    sues = list(range(1, 31))
    deciles = assign_deciles(sues)
    assert deciles[29] == 10
    assert deciles[28] == 10
    assert deciles[27] == 10
    assert deciles[0] == 1


def test_assign_deciles_with_nan():
    sues = [float("nan"), 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
    deciles = assign_deciles(sues)
    assert math.isnan(deciles[0])  # nan stays nan
    assert deciles[10] == 10        # max → top decile


def test_assign_deciles_fewer_than_10_unique():
    # Only 3 unique values — qcut may collapse; expect ranks 1..3 mapped sensibly.
    sues = [1.0, 1.0, 2.0, 2.0, 3.0, 3.0]
    deciles = assign_deciles(sues)
    # Lowest values get decile 1; highest get max decile present.
    assert deciles[0] <= deciles[-1]
```

- [ ] **Step 2: Run — confirm fail**

Run: `pytest tests/pead/test_sue.py -v`
Expected: ImportError for `assign_deciles`.

- [ ] **Step 3: Implement assign_deciles**

Append to `core/sue.py`:

```python
import pandas as pd


def assign_deciles(sues: Sequence[float]) -> list[float]:
    """Rank-based decile assignment (1..10). NaN inputs return NaN.

    Uses pandas.qcut with duplicates='drop' so collisions don't crash.
    If fewer than 10 unique non-nan values, decile labels span 1..k where k<10.
    """
    s = pd.Series(sues, dtype="float64")
    mask = s.notna()
    if mask.sum() == 0:
        return [math.nan] * len(sues)
    ranked = s[mask].rank(method="average")
    n_unique = ranked.nunique()
    bins = min(10, max(1, n_unique))
    labels = list(range(1, bins + 1))
    deciles = pd.qcut(ranked, q=bins, labels=labels, duplicates="drop")
    out = pd.Series([math.nan] * len(sues), dtype="float64")
    out.loc[mask] = deciles.astype("float64").values
    return out.tolist()
```

- [ ] **Step 4: Run — confirm pass**

Run: `pytest tests/pead/test_sue.py -v`
Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
git add core/sue.py tests/pead/test_sue.py
git commit -m "feat(pead): annual_sue + assign_deciles in core/sue.py"
```

### Task 1.3: `core/piotroski.py` — 9-component F-score

**Files:**
- Create: `core/piotroski.py`
- Test: `tests/pead/test_piotroski.py`

- [ ] **Step 1: Write failing tests**

`tests/pead/test_piotroski.py`:

```python
import math

import pandas as pd
import pytest

from core.piotroski import piotroski_score, PiotroskiInputs


def _good_inputs() -> PiotroskiInputs:
    """All 9 conditions pass → score 9."""
    return PiotroskiInputs(
        net_income=100, net_income_prev=80,
        total_assets=1000, total_assets_prev=900,
        ocf=120, ocf_prev=80,
        long_term_debt=200, long_term_debt_prev=250,
        current_assets=500, current_liab=200,
        current_assets_prev=400, current_liab_prev=200,
        shares_outstanding=100, shares_outstanding_prev=100,
        gross_profit=400, revenue=1000,
        gross_profit_prev=300, revenue_prev=900,
    )


def test_piotroski_all_pass_returns_9():
    score = piotroski_score(_good_inputs())
    assert score == 9


def test_piotroski_all_fail_returns_0():
    inp = PiotroskiInputs(
        net_income=-100, net_income_prev=80,
        total_assets=1000, total_assets_prev=900,
        ocf=-50, ocf_prev=80,
        long_term_debt=300, long_term_debt_prev=200,
        current_assets=300, current_liab=400,
        current_assets_prev=400, current_liab_prev=200,
        shares_outstanding=120, shares_outstanding_prev=100,
        gross_profit=200, revenue=1000,
        gross_profit_prev=300, revenue_prev=900,
    )
    assert piotroski_score(inp) == 0


def test_piotroski_roa_positive_alone():
    inp = _good_inputs()
    inp.net_income = -1
    assert piotroski_score(inp) == 8  # ROA fails


def test_piotroski_ocf_gt_ni_accrual():
    inp = _good_inputs()
    inp.ocf = 50  # less than net_income=100 -> accrual condition fails
    assert piotroski_score(inp) == 8


def test_piotroski_shares_issued_fails():
    inp = _good_inputs()
    inp.shares_outstanding = 110  # issued shares -> fails
    assert piotroski_score(inp) == 8


def test_piotroski_returns_nan_on_missing_input():
    inp = _good_inputs()
    inp.total_assets_prev = math.nan
    score = piotroski_score(inp)
    assert math.isnan(score)
```

- [ ] **Step 2: Run — confirm fail**

Run: `pytest tests/pead/test_piotroski.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement core/piotroski.py**

```python
"""Piotroski F-Score — 9 binary components, computed on annual financials."""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class PiotroskiInputs:
    net_income: float
    net_income_prev: float
    total_assets: float
    total_assets_prev: float
    ocf: float                         # operating cash flow
    ocf_prev: float
    long_term_debt: float
    long_term_debt_prev: float
    current_assets: float
    current_liab: float
    current_assets_prev: float
    current_liab_prev: float
    shares_outstanding: float
    shares_outstanding_prev: float
    gross_profit: float
    revenue: float
    gross_profit_prev: float
    revenue_prev: float


def _has_nan(inp: PiotroskiInputs) -> bool:
    for v in inp.__dict__.values():
        if v is None:
            return True
        try:
            if math.isnan(float(v)):
                return True
        except (TypeError, ValueError):
            return True
    return False


def piotroski_score(inp: PiotroskiInputs) -> float:
    """Return integer score 0..9. Returns nan if any input is nan/missing."""
    if _has_nan(inp):
        return math.nan

    roa = inp.net_income / inp.total_assets
    roa_prev = inp.net_income_prev / inp.total_assets_prev
    lev = inp.long_term_debt / inp.total_assets
    lev_prev = inp.long_term_debt_prev / inp.total_assets_prev
    cr = inp.current_assets / inp.current_liab
    cr_prev = inp.current_assets_prev / inp.current_liab_prev
    gm = inp.gross_profit / inp.revenue
    gm_prev = inp.gross_profit_prev / inp.revenue_prev
    at = inp.revenue / inp.total_assets
    at_prev = inp.revenue_prev / inp.total_assets_prev

    score = 0
    score += int(roa > 0)                                 # 1. ROA positive
    score += int(inp.ocf > 0)                             # 2. OCF positive
    score += int(roa > roa_prev)                          # 3. ΔROA positive
    score += int(inp.ocf > inp.net_income)                # 4. OCF > NI (accrual)
    score += int(lev < lev_prev)                          # 5. Δ leverage negative
    score += int(cr > cr_prev)                            # 6. Δ current ratio positive
    score += int(inp.shares_outstanding <= inp.shares_outstanding_prev)  # 7. No new shares
    score += int(gm > gm_prev)                            # 8. Δ gross margin positive
    score += int(at > at_prev)                            # 9. Δ asset turnover positive
    return float(score)
```

- [ ] **Step 4: Run — confirm pass**

Run: `pytest tests/pead/test_piotroski.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add core/piotroski.py tests/pead/test_piotroski.py
git commit -m "feat(pead): core/piotroski.py with 9-component F-score + tests"
```

### Task 1.4: `core/nse_announce.py` — parser + period inference

**Files:**
- Create: `core/nse_announce.py`
- Test: `tests/pead/test_nse_announce.py`
- Create: `tests/pead/fixtures/nse_announce_sample.json`

- [ ] **Step 1: Create fixture file**

`tests/pead/fixtures/nse_announce_sample.json`:

```json
[
  {
    "symbol": "RELIANCE",
    "broadcastDate": "21-Apr-2026 18:30:00",
    "fromDate": "01-Jan-2026",
    "toDate": "31-Mar-2026",
    "filingDate": "21-Apr-2026",
    "audited": "Un-Audited"
  },
  {
    "symbol": "TCS",
    "broadcastDate": "15-Apr-2026 14:00:00",
    "fromDate": "01-Apr-2025",
    "toDate": "31-Mar-2026",
    "filingDate": "15-Apr-2026",
    "audited": "Audited"
  },
  {
    "symbol": "INFY",
    "broadcastDate": "20-Apr-2026 17:00:00",
    "fromDate": "",
    "toDate": "",
    "filingDate": "20-Apr-2026"
  }
]
```

- [ ] **Step 2: Write failing tests**

`tests/pead/test_nse_announce.py`:

```python
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
```

- [ ] **Step 3: Run — confirm fail**

Run: `pytest tests/pead/test_nse_announce.py -v`
Expected: ImportError.

- [ ] **Step 4: Implement core/nse_announce.py**

```python
"""NSE corporate-financial-results client + parser.

Endpoints:
    https://www.nseindia.com/api/corporates-financial-results?index=equities&period=Quarterly
    https://www.nseindia.com/api/corporates-financial-results?index=equities&period=Annual

Required cookie/header dance: GET nseindia.com first, then call API with browser
UA + Referer. Retries 3× on 401/403 with cookie reseed. 2s sleep between calls.
"""
from __future__ import annotations

import json
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any

import requests


_NSE_HOME = "https://www.nseindia.com"
_NSE_API = "https://www.nseindia.com/api/corporates-financial-results"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": (
        "https://www.nseindia.com/companies-listing/"
        "corporate-filings-financial-results"
    ),
}


def _parse_date(s: str) -> date | None:
    """Parse '21-Apr-2026' or '21-Apr-2026 18:30:00' into date."""
    if not s:
        return None
    s = s.strip()
    for fmt in ("%d-%b-%Y %H:%M:%S", "%d-%b-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def infer_period_type(period_from: date, period_to: date) -> str | None:
    """Return 'Q' (~90d span), 'A' (~365d span), or None if neither."""
    if period_from is None or period_to is None:
        return None
    span = (period_to - period_from).days + 1
    if 80 <= span <= 100:
        return "Q"
    if 350 <= span <= 380:
        return "A"
    return None


def nse_symbol_to_yf(symbol: str) -> str:
    """Map NSE bare symbol to yfinance ticker (.NS suffix)."""
    return f"{symbol.strip()}.NS"


def parse_announcements(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert raw NSE API rows into normalized events. Drops unparseable rows."""
    out: list[dict[str, Any]] = []
    for row in raw:
        sym = (row.get("symbol") or "").strip()
        rd = _parse_date(row.get("broadcastDate") or row.get("filingDate") or "")
        pf = _parse_date(row.get("fromDate") or "")
        pt = _parse_date(row.get("toDate") or "")
        period = infer_period_type(pf, pt) if (pf and pt) else None
        if not sym or rd is None or period is None:
            continue
        out.append(
            {
                "symbol": sym,
                "yf_ticker": nse_symbol_to_yf(sym),
                "result_date": rd,
                "period_from": pf,
                "period_to": pt,
                "period_type": period,
            }
        )
    return out


def _new_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(_HEADERS)
    s.get(_NSE_HOME, timeout=30)
    time.sleep(1)
    return s


def fetch_announcements(period: str = "Quarterly", retries: int = 3) -> list[dict]:
    """Fetch raw rows from NSE corp-announce API. Returns list of dicts."""
    assert period in ("Quarterly", "Annual")
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            sess = _new_session()
            r = sess.get(
                _NSE_API,
                params={"index": "equities", "period": period},
                timeout=30,
            )
            if r.status_code in (401, 403):
                raise RuntimeError(f"NSE_BLOCKED status={r.status_code}")
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last_err = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"NSE_BLOCKED after {retries} retries: {last_err}")


def cache_raw(raw: list[dict], cache_dir: Path, day: date) -> Path:
    """Persist raw JSON to pead_data/nse_announce_raw/{YYYY-MM-DD}.json."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{day.isoformat()}.json"
    path.write_text(json.dumps(raw, indent=2))
    return path
```

- [ ] **Step 5: Run — confirm pass**

Run: `pytest tests/pead/test_nse_announce.py -v`
Expected: 8 passed.

- [ ] **Step 6: Commit**

```bash
git add core/nse_announce.py tests/pead/test_nse_announce.py tests/pead/fixtures/
git commit -m "feat(pead): core/nse_announce.py — parser + fetch + period inference"
```

### Task 1.5: `core/fundamentals.py` — yfinance wrapper + cache

**Files:**
- Create: `core/fundamentals.py`
- Test: `tests/pead/test_fundamentals.py`

- [ ] **Step 1: Write failing tests**

`tests/pead/test_fundamentals.py`:

```python
import math
from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from core.fundamentals import (
    get_quarterly_eps_history,
    get_annual_eps_history,
    get_piotroski_inputs,
    get_price_and_book_value,
)


def _make_quarterly_df():
    return pd.DataFrame(
        {
            "Earnings": [100, 110, 95, 120, 130, 140, 125, 150],
        },
        index=pd.to_datetime(
            ["2024-03-31", "2024-06-30", "2024-09-30", "2024-12-31",
             "2025-03-31", "2025-06-30", "2025-09-30", "2025-12-31"]
        ),
    )


@patch("core.fundamentals.yf.Ticker")
def test_get_quarterly_eps_history_returns_last_4(mock_ticker):
    mock_t = MagicMock()
    mock_t.quarterly_earnings = _make_quarterly_df()
    mock_ticker.return_value = mock_t

    hist = get_quarterly_eps_history("RELIANCE.NS", as_of=date(2026, 1, 15))
    assert hist == [150, 125, 140, 130]   # most-recent-first


@patch("core.fundamentals.yf.Ticker")
def test_get_quarterly_eps_history_filters_post_asof(mock_ticker):
    mock_t = MagicMock()
    mock_t.quarterly_earnings = _make_quarterly_df()
    mock_ticker.return_value = mock_t

    hist = get_quarterly_eps_history("RELIANCE.NS", as_of=date(2025, 4, 1))
    # Only 2024 quarters before 2025-04-01 -> [2024-12-31, ..., 2024-03-31]
    assert hist == [120, 95, 110, 100]


@patch("core.fundamentals.yf.Ticker")
def test_get_quarterly_eps_history_empty(mock_ticker):
    mock_t = MagicMock()
    mock_t.quarterly_earnings = pd.DataFrame()
    mock_ticker.return_value = mock_t

    hist = get_quarterly_eps_history("ZZZ.NS", as_of=date(2026, 1, 1))
    assert hist == []


@patch("core.fundamentals.yf.Ticker")
def test_get_price_and_book_value(mock_ticker):
    mock_t = MagicMock()
    mock_t.info = {"sector": "Energy", "bookValue": 500.0}
    mock_t.history.return_value = pd.DataFrame(
        {"Close": [2500.0]},
        index=pd.to_datetime(["2026-04-20"]),
    )
    mock_ticker.return_value = mock_t

    info = get_price_and_book_value("RELIANCE.NS", as_of=date(2026, 4, 21))
    assert info["sector"] == "Energy"
    assert info["price"] == 2500.0
    assert info["book_value"] == 500.0
    assert math.isclose(info["pb"], 5.0)
```

- [ ] **Step 2: Run — confirm fail**

Run: `pytest tests/pead/test_fundamentals.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement core/fundamentals.py**

```python
"""yfinance fundamentals wrapper. Returns dicts/lists ready for SUE & Piotroski.

All getters accept `as_of: date` and FILTER OUT periods whose announce date
(approximated by period_end) is >= as_of. This is the primary look-ahead guard
at the data layer; the backtest engine re-verifies.
"""
from __future__ import annotations

import math
from datetime import date
from typing import Any

import pandas as pd
import yfinance as yf

from core.piotroski import PiotroskiInputs


def _safe_float(v: Any) -> float:
    try:
        f = float(v)
        return f if not math.isnan(f) else math.nan
    except (TypeError, ValueError):
        return math.nan


def get_quarterly_eps_history(ticker: str, as_of: date, n: int = 4) -> list[float]:
    """Return last n quarterly EPS strictly before as_of, most-recent-first.

    Returns [] if yfinance has nothing or fewer than n usable quarters.
    """
    t = yf.Ticker(ticker)
    df = t.quarterly_earnings
    if df is None or len(df) == 0 or "Earnings" not in df.columns:
        return []
    df = df.sort_index(ascending=False)
    df = df[df.index.date < as_of]
    if len(df) < n:
        return []
    return [_safe_float(v) for v in df["Earnings"].head(n).tolist()]


def get_annual_eps_history(ticker: str, as_of: date, n: int = 4) -> list[float]:
    """Return last n annual EPS strictly before as_of, most-recent-first."""
    t = yf.Ticker(ticker)
    df = getattr(t, "earnings", None)
    if df is None or len(df) == 0 or "Earnings" not in df.columns:
        return []
    df = df.sort_index(ascending=False)
    df = df[df.index.year < as_of.year]
    if len(df) < n:
        return []
    return [_safe_float(v) for v in df["Earnings"].head(n).tolist()]


def get_piotroski_inputs(ticker: str, as_of: date) -> PiotroskiInputs | None:
    """Build PiotroskiInputs from yfinance annual statements.

    Uses last 2 fiscal years (current vs prior). Returns None if any
    required line item is missing.
    """
    t = yf.Ticker(ticker)
    try:
        inc = t.income_stmt
        bal = t.balance_sheet
        cf = t.cashflow
    except Exception:
        return None
    if inc is None or bal is None or cf is None:
        return None
    if inc.empty or bal.empty or cf.empty:
        return None

    # yfinance frames have columns = fiscal-year-end dates, descending.
    def _col(df: pd.DataFrame, i: int) -> pd.Series | None:
        if df.shape[1] <= i:
            return None
        col = df.columns[i]
        if col.date() >= as_of:
            return None
        return df[col]

    cur = _col(inc, 0)
    prev = _col(inc, 1)
    if cur is None or prev is None:
        return None
    bal_cur = _col(bal, 0)
    bal_prev = _col(bal, 1)
    cf_cur = _col(cf, 0)
    cf_prev = _col(cf, 1)
    if bal_cur is None or bal_prev is None or cf_cur is None or cf_prev is None:
        return None

    def _g(s: pd.Series, *keys: str) -> float:
        for k in keys:
            if k in s.index:
                return _safe_float(s[k])
        return math.nan

    inp = PiotroskiInputs(
        net_income=_g(cur, "Net Income", "NetIncome"),
        net_income_prev=_g(prev, "Net Income", "NetIncome"),
        total_assets=_g(bal_cur, "Total Assets"),
        total_assets_prev=_g(bal_prev, "Total Assets"),
        ocf=_g(cf_cur, "Operating Cash Flow", "Total Cash From Operating Activities"),
        ocf_prev=_g(cf_prev, "Operating Cash Flow", "Total Cash From Operating Activities"),
        long_term_debt=_g(bal_cur, "Long Term Debt"),
        long_term_debt_prev=_g(bal_prev, "Long Term Debt"),
        current_assets=_g(bal_cur, "Current Assets", "Total Current Assets"),
        current_liab=_g(bal_cur, "Current Liabilities", "Total Current Liabilities"),
        current_assets_prev=_g(bal_prev, "Current Assets", "Total Current Assets"),
        current_liab_prev=_g(bal_prev, "Current Liabilities", "Total Current Liabilities"),
        shares_outstanding=_g(bal_cur, "Share Issued", "Ordinary Shares Number"),
        shares_outstanding_prev=_g(bal_prev, "Share Issued", "Ordinary Shares Number"),
        gross_profit=_g(cur, "Gross Profit"),
        revenue=_g(cur, "Total Revenue", "Revenue"),
        gross_profit_prev=_g(prev, "Gross Profit"),
        revenue_prev=_g(prev, "Total Revenue", "Revenue"),
    )
    return inp


def get_price_and_book_value(ticker: str, as_of: date) -> dict[str, Any]:
    """Return {sector, price, book_value, pb} as of last close before as_of."""
    t = yf.Ticker(ticker)
    info = t.info or {}
    sector = info.get("sector") or "Unknown"
    book = _safe_float(info.get("bookValue"))
    # Pull last close strictly before as_of
    hist = t.history(start=str(as_of.replace(day=1)), end=str(as_of))
    if hist is None or hist.empty:
        return {"sector": sector, "price": math.nan, "book_value": book, "pb": math.nan}
    price = _safe_float(hist["Close"].iloc[-1])
    pb = price / book if (book and book > 0 and not math.isnan(price)) else math.nan
    return {"sector": sector, "price": price, "book_value": book, "pb": pb}
```

- [ ] **Step 4: Run — confirm pass**

Run: `pytest tests/pead/test_fundamentals.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add core/fundamentals.py tests/pead/test_fundamentals.py
git commit -m "feat(pead): core/fundamentals.py — yfinance EPS/Piotroski/PB wrappers"
```

### Task 1.6: Update core/__init__.py exports

**Files:**
- Modify: `core/__init__.py`

- [ ] **Step 1: Add new modules to __all__**

Replace the `__all__` block:

```python
__all__ = [
    'config',
    'data_io',
    'indicators',
    'cache',
    'regime',
    'glossary',
    'sue',
    'piotroski',
    'nse_announce',
    'fundamentals',
]
```

- [ ] **Step 2: Verify imports**

Run: `python -c "from core import sue, piotroski, nse_announce, fundamentals; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add core/__init__.py
git commit -m "chore(pead): export new core/ modules"
```

---

## Phase 2 — Event Builder

### Task 2.1: PEAD event-row assembly function

**Files:**
- Create: `pead_event_builder.py`
- Test: `tests/pead/test_event_builder.py`

- [ ] **Step 1: Write failing test**

`tests/pead/test_event_builder.py`:

```python
import math
from datetime import date
from unittest.mock import patch

from pead_event_builder import build_event


def _stub_fundamentals(ticker, as_of):
    return {"sector": "IT", "price": 1500.0, "book_value": 300.0, "pb": 5.0}


def _stub_qhist(ticker, as_of, n=4):
    return [22.0, 21.0, 23.0, 22.5]  # mean ~22.125, std ~0.78


def _stub_ahist(ticker, as_of, n=4):
    return [85.0, 80.0, 90.0, 88.0]


def _stub_piotroski_inputs(ticker, as_of):
    return None  # downstream handles None as nan score


@patch("pead_event_builder.get_price_and_book_value", _stub_fundamentals)
@patch("pead_event_builder.get_quarterly_eps_history", _stub_qhist)
@patch("pead_event_builder.get_annual_eps_history", _stub_ahist)
@patch("pead_event_builder.get_piotroski_inputs", _stub_piotroski_inputs)
def test_build_event_quarterly():
    ev = build_event(
        ticker="INFY.NS",
        result_date=date(2026, 4, 20),
        period_type="Q",
        eps_actual=25.0,
    )
    assert ev["ticker"] == "INFY.NS"
    assert ev["period_type"] == "Q"
    assert ev["result_date"] == date(2026, 4, 20)
    assert ev["sector"] == "IT"
    assert ev["eps_actual"] == 25.0
    assert ev["eps_history"] == [22.0, 21.0, 23.0, 22.5]
    assert math.isclose(ev["eps_expected"], 22.125)
    assert ev["sue"] > 0
    assert math.isnan(ev["piotroski"])
    assert ev["pb"] == 5.0


@patch("pead_event_builder.get_price_and_book_value", _stub_fundamentals)
@patch("pead_event_builder.get_quarterly_eps_history", _stub_qhist)
@patch("pead_event_builder.get_annual_eps_history", _stub_ahist)
@patch("pead_event_builder.get_piotroski_inputs", _stub_piotroski_inputs)
def test_build_event_annual():
    ev = build_event(
        ticker="INFY.NS",
        result_date=date(2026, 5, 10),
        period_type="A",
        eps_actual=95.0,
    )
    assert ev["period_type"] == "A"
    assert ev["eps_history"] == [85.0, 80.0, 90.0, 88.0]
    assert ev["sue"] > 0
```

- [ ] **Step 2: Run — confirm fail**

Run: `pytest tests/pead/test_event_builder.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement pead_event_builder.py**

```python
"""Assembles a single PEAD event row from primitives.

Single function `build_event(ticker, result_date, period_type, eps_actual)`
returns a dict matching the spec data model. Decile + qualifies flags are
filled in later by the cohort step.
"""
from __future__ import annotations

import math
from datetime import date
from typing import Any

from core.fundamentals import (
    get_annual_eps_history,
    get_piotroski_inputs,
    get_price_and_book_value,
    get_quarterly_eps_history,
)
from core.piotroski import piotroski_score
from core.sue import quarterly_sue, annual_sue


def build_event(
    ticker: str,
    result_date: date,
    period_type: str,
    eps_actual: float,
) -> dict[str, Any]:
    assert period_type in ("Q", "A")
    if period_type == "Q":
        hist = get_quarterly_eps_history(ticker, as_of=result_date, n=4)
        sue = quarterly_sue(eps_actual, hist) if len(hist) == 4 else math.nan
    else:
        hist = get_annual_eps_history(ticker, as_of=result_date, n=4)
        sue = annual_sue(eps_actual, hist) if len(hist) == 4 else math.nan

    pf_info = get_price_and_book_value(ticker, as_of=result_date)
    pf_inputs = get_piotroski_inputs(ticker, as_of=result_date)
    pio = piotroski_score(pf_inputs) if pf_inputs is not None else math.nan

    expected = float(sum(hist) / len(hist)) if len(hist) == 4 else math.nan

    return {
        "ticker": ticker,
        "sector": pf_info["sector"],
        "result_date": result_date,
        "period_type": period_type,
        "eps_actual": float(eps_actual),
        "eps_history": hist,
        "eps_expected": expected,
        "sue": sue,
        "piotroski": pio,
        "pb": pf_info["pb"],
        "price_at_result": pf_info["price"],
        "book_value": pf_info["book_value"],
        # Filled later:
        "pb_sector_median": math.nan,
        "sue_decile": math.nan,
        "qualifies_long": False,
        "qualifies_short": False,
    }
```

- [ ] **Step 4: Run — confirm pass**

Run: `pytest tests/pead/test_event_builder.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add pead_event_builder.py tests/pead/test_event_builder.py
git commit -m "feat(pead): pead_event_builder.build_event() assembles event row"
```

### Task 2.2: Cohort decile + qualifies flags

**Files:**
- Create: `pead_cohort.py`
- Test: `tests/pead/test_cohort.py`

- [ ] **Step 1: Write failing test**

`tests/pead/test_cohort.py`:

```python
import math
from datetime import date, timedelta

import pandas as pd
import pytest

from pead_cohort import compute_cohort_deciles, mark_qualifies


def _make_events(n=30, ref_date=date(2026, 4, 20)):
    rows = []
    for i in range(n):
        rows.append(
            {
                "ticker": f"T{i}.NS",
                "sector": "IT" if i < 15 else "Energy",
                "result_date": ref_date + timedelta(days=(i % 5) - 2),
                "sue": float(i),  # 0..n-1
                "piotroski": 8 if i % 2 == 0 else 4,
                "pb": 1.0,
                "pb_sector_median": 2.0,
            }
        )
    return pd.DataFrame(rows)


def test_compute_cohort_deciles_window_5td():
    df = _make_events()
    out = compute_cohort_deciles(df, window_td=5)
    # SUE=29 should be in top decile (10)
    assert out.loc[out["sue"] == 29.0, "sue_decile"].iloc[0] == 10
    # SUE=0 should be in decile 1
    assert out.loc[out["sue"] == 0.0, "sue_decile"].iloc[0] == 1


def test_mark_qualifies_long():
    df = _make_events()
    df = compute_cohort_deciles(df, window_td=5)
    df = mark_qualifies(df)
    long_only = df[df["qualifies_long"]]
    # Must satisfy: decile==10 AND piotroski>=7 AND pb<=pb_sector_median
    for _, row in long_only.iterrows():
        assert row["sue_decile"] == 10
        assert row["piotroski"] >= 7
        assert row["pb"] <= row["pb_sector_median"]


def test_mark_qualifies_short_diagnostic():
    df = _make_events()
    df = compute_cohort_deciles(df, window_td=5)
    df = mark_qualifies(df)
    short_only = df[df["qualifies_short"]]
    for _, row in short_only.iterrows():
        assert row["sue_decile"] == 1
        assert row["piotroski"] <= 3
```

- [ ] **Step 2: Run — confirm fail**

Run: `pytest tests/pead/test_cohort.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement pead_cohort.py**

```python
"""Cohort decile assignment + qualifies_long/short flags.

For each event, decile is computed within events whose result_date is in
[result_date - window_td, result_date + window_td]. This handles spec
section §5 rolling cohort.
"""
from __future__ import annotations

import math
from datetime import timedelta

import pandas as pd

from core.sue import assign_deciles


def compute_cohort_deciles(events: pd.DataFrame, window_td: int = 5) -> pd.DataFrame:
    """Assign SUE decile per event using a ±window_td trading-day cohort.

    NOTE: window_td is approximated as calendar days here (5 td ≈ 7 cal days).
    For backtest accuracy we use trading-day arithmetic; for live live_signals
    the look-ahead window collapses naturally to [d-window, d].
    """
    events = events.copy()
    events["sue_decile"] = float("nan")
    cal_window = timedelta(days=window_td + 2)  # 5 td ≈ 7 cal days
    for idx, row in events.iterrows():
        rd = row["result_date"]
        mask = (events["result_date"] >= rd - cal_window) & (
            events["result_date"] <= rd + cal_window
        )
        cohort = events.loc[mask, "sue"].tolist()
        deciles = assign_deciles(cohort)
        cohort_idx = events.loc[mask].index.tolist()
        pos = cohort_idx.index(idx)
        events.at[idx, "sue_decile"] = deciles[pos]
    return events


def mark_qualifies(events: pd.DataFrame) -> pd.DataFrame:
    """Apply entry rules from spec §2.

    qualifies_long  = decile == 10 AND piotroski >= 7 AND pb <= pb_sector_median
    qualifies_short = decile ==  1 AND piotroski <= 3                  (diagnostic)
    """
    events = events.copy()
    top = events["sue_decile"] == 10
    bot = events["sue_decile"] == 1
    pio_ok = events["piotroski"] >= 7
    pio_bad = events["piotroski"] <= 3
    pb_ok = events["pb"] <= events["pb_sector_median"]
    events["qualifies_long"] = (top & pio_ok & pb_ok).fillna(False)
    events["qualifies_short"] = (bot & pio_bad).fillna(False)
    return events
```

- [ ] **Step 4: Run — confirm pass**

Run: `pytest tests/pead/test_cohort.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add pead_cohort.py tests/pead/test_cohort.py
git commit -m "feat(pead): cohort decile + qualifies_long/short flags"
```

### Task 2.3: Sector P/B median helper

**Files:**
- Create: `pead_sector_pb.py`
- Test: `tests/pead/test_sector_pb.py`

- [ ] **Step 1: Write failing test**

`tests/pead/test_sector_pb.py`:

```python
import math

import pandas as pd

from pead_sector_pb import compute_sector_medians, attach_sector_median


def test_compute_sector_medians_basic():
    df = pd.DataFrame(
        {
            "sector": ["IT", "IT", "IT", "Energy", "Energy"],
            "pb": [2.0, 4.0, 6.0, 1.0, 3.0],
        }
    )
    medians = compute_sector_medians(df)
    assert medians["IT"] == 4.0
    assert medians["Energy"] == 2.0


def test_compute_sector_medians_skips_nan():
    df = pd.DataFrame(
        {"sector": ["IT", "IT", "IT"], "pb": [2.0, float("nan"), 6.0]}
    )
    medians = compute_sector_medians(df)
    assert medians["IT"] == 4.0


def test_attach_sector_median_fallback_to_universe():
    df = pd.DataFrame(
        {
            "sector": ["IT", "IT", "Unknown"],
            "pb": [2.0, 4.0, 5.0],
            "pb_sector_median": [float("nan")] * 3,
        }
    )
    out = attach_sector_median(df)
    assert out.loc[out["sector"] == "IT", "pb_sector_median"].iloc[0] == 3.0
    # Unknown sector falls back to universe median = median([2,4,5]) = 4.0
    assert out.loc[out["sector"] == "Unknown", "pb_sector_median"].iloc[0] == 4.0
```

- [ ] **Step 2: Run — confirm fail**

Run: `pytest tests/pead/test_sector_pb.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement pead_sector_pb.py**

```python
"""Sector-level P/B median computation + attachment to events."""
from __future__ import annotations

import math
import pandas as pd


def compute_sector_medians(df: pd.DataFrame) -> dict[str, float]:
    """Return {sector: median P/B}. Skips NaN P/Bs."""
    cleaned = df.dropna(subset=["pb"])
    return cleaned.groupby("sector")["pb"].median().to_dict()


def attach_sector_median(events: pd.DataFrame) -> pd.DataFrame:
    """Fill events['pb_sector_median']. Falls back to universe median for unknown sectors."""
    events = events.copy()
    medians = compute_sector_medians(events)
    universe_med = events["pb"].dropna().median() if events["pb"].notna().any() else math.nan
    events["pb_sector_median"] = events["sector"].map(medians).fillna(universe_med)
    return events
```

- [ ] **Step 4: Run — confirm pass**

Run: `pytest tests/pead/test_sector_pb.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add pead_sector_pb.py tests/pead/test_sector_pb.py
git commit -m "feat(pead): sector P/B median helper with universe fallback"
```

---

## Phase 3 — Daily Downloader

### Task 3.1: Universe filter

**Files:**
- Create: `pead_universe.py`
- Test: `tests/pead/test_universe.py`

- [ ] **Step 1: Write failing test**

`tests/pead/test_universe.py`:

```python
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from pead_universe import filter_universe


@patch("pead_universe.yf.Ticker")
def test_filter_universe_keeps_liquid_large(mock_ticker):
    mock_t = MagicMock()
    mock_t.info = {"marketCap": 80_000_00_00_000, "firstTradeDateEpochUtc": 1_000_000_000}
    mock_t.quarterly_earnings = pd.DataFrame(
        {"Earnings": [1, 2, 3, 4, 5]},
        index=pd.to_datetime(["2024-03", "2024-06", "2024-09", "2024-12", "2025-03"]),
    )
    mock_ticker.return_value = mock_t

    kept = filter_universe(["RELIANCE.NS"])
    assert "RELIANCE.NS" in kept


@patch("pead_universe.yf.Ticker")
def test_filter_universe_drops_small_cap(mock_ticker):
    mock_t = MagicMock()
    mock_t.info = {"marketCap": 100_00_00_000, "firstTradeDateEpochUtc": 1_000_000_000}
    mock_t.quarterly_earnings = pd.DataFrame(
        {"Earnings": [1, 2, 3, 4]},
        index=pd.to_datetime(["2024-03", "2024-06", "2024-09", "2024-12"]),
    )
    mock_ticker.return_value = mock_t

    kept = filter_universe(["TINYCAP.NS"], min_mcap_cr=5000)
    assert "TINYCAP.NS" not in kept


@patch("pead_universe.yf.Ticker")
def test_filter_universe_drops_insufficient_history(mock_ticker):
    mock_t = MagicMock()
    mock_t.info = {"marketCap": 80_000_00_00_000, "firstTradeDateEpochUtc": 1_000_000_000}
    mock_t.quarterly_earnings = pd.DataFrame(
        {"Earnings": [1, 2]},
        index=pd.to_datetime(["2025-09", "2025-12"]),
    )
    mock_ticker.return_value = mock_t

    kept = filter_universe(["NEWCO.NS"])
    assert "NEWCO.NS" not in kept
```

- [ ] **Step 2: Run — confirm fail**

Run: `pytest tests/pead/test_universe.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement pead_universe.py**

```python
"""Universe filter for PEAD: large/mid cap, listed >5y, ≥4 q EPS history."""
from __future__ import annotations

import time
from datetime import date, datetime

import pandas as pd
import yfinance as yf

_CR = 1_00_00_000  # 1 crore in rupees


def filter_universe(
    candidates: list[str],
    min_mcap_cr: float = 5_000,
    min_years_listed: int = 5,
    min_quarters_eps: int = 4,
    throttle_sec: float = 0.3,
) -> list[str]:
    """Return tickers passing all filters."""
    kept: list[str] = []
    today = date.today()
    for ticker in candidates:
        try:
            t = yf.Ticker(ticker)
            info = t.info or {}
            mcap = info.get("marketCap") or 0
            if mcap < min_mcap_cr * _CR:
                continue
            first_ts = info.get("firstTradeDateEpochUtc")
            if first_ts:
                first = datetime.utcfromtimestamp(first_ts).date()
                if (today - first).days < min_years_listed * 365:
                    continue
            qe = t.quarterly_earnings
            if qe is None or len(qe) < min_quarters_eps:
                continue
            kept.append(ticker)
        except Exception:
            continue
        time.sleep(throttle_sec)
    return kept
```

- [ ] **Step 4: Run — confirm pass**

Run: `pytest tests/pead/test_universe.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add pead_universe.py tests/pead/test_universe.py
git commit -m "feat(pead): universe filter (mcap, listing age, EPS history)"
```

### Task 3.2: Events persistence layer

**Files:**
- Create: `pead_events_store.py`
- Test: `tests/pead/test_events_store.py`

- [ ] **Step 1: Write failing test**

`tests/pead/test_events_store.py`:

```python
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from pead_events_store import append_events, load_events


def test_append_and_load_events(tmp_path: Path):
    path = tmp_path / "events.parquet"
    rows = [
        {"ticker": "A.NS", "result_date": date(2026, 1, 1), "period_type": "Q",
         "sue": 1.5, "piotroski": 8, "pb": 2.0, "sector": "IT",
         "eps_actual": 10.0, "eps_expected": 8.0,
         "pb_sector_median": 3.0, "sue_decile": 10.0,
         "qualifies_long": True, "qualifies_short": False},
    ]
    append_events(path, rows)
    df = load_events(path)
    assert len(df) == 1
    assert df.iloc[0]["ticker"] == "A.NS"


def test_append_dedup_by_ticker_date_period(tmp_path: Path):
    path = tmp_path / "events.parquet"
    base = {"ticker": "A.NS", "result_date": date(2026, 1, 1), "period_type": "Q",
            "sue": 1.5, "piotroski": 8, "pb": 2.0, "sector": "IT",
            "eps_actual": 10.0, "eps_expected": 8.0,
            "pb_sector_median": 3.0, "sue_decile": 10.0,
            "qualifies_long": True, "qualifies_short": False}
    append_events(path, [base])
    append_events(path, [base])     # duplicate
    df = load_events(path)
    assert len(df) == 1


def test_append_updates_existing(tmp_path: Path):
    path = tmp_path / "events.parquet"
    base = {"ticker": "A.NS", "result_date": date(2026, 1, 1), "period_type": "Q",
            "sue": 1.5, "piotroski": 8, "pb": 2.0, "sector": "IT",
            "eps_actual": 10.0, "eps_expected": 8.0,
            "pb_sector_median": 3.0, "sue_decile": 10.0,
            "qualifies_long": True, "qualifies_short": False}
    append_events(path, [base])
    updated = dict(base, sue=2.0)
    append_events(path, [updated])
    df = load_events(path)
    assert len(df) == 1
    assert df.iloc[0]["sue"] == 2.0
```

- [ ] **Step 2: Run — confirm fail**

Run: `pytest tests/pead/test_events_store.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement pead_events_store.py**

```python
"""Append-only events.parquet store with dedup-update semantics.

Dedup key: (ticker, result_date, period_type). Re-appending overwrites the
existing row (last write wins).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

_KEY_COLS = ["ticker", "result_date", "period_type"]


def load_events(path: Path) -> pd.DataFrame:
    if not Path(path).exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


def append_events(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    new_df = pd.DataFrame(rows)
    path = Path(path)
    if path.exists():
        old = pd.read_parquet(path)
        # drop dups in 'old' that are about to be replaced
        merged = pd.concat([old, new_df], ignore_index=True)
        merged = merged.drop_duplicates(subset=_KEY_COLS, keep="last")
    else:
        merged = new_df.drop_duplicates(subset=_KEY_COLS, keep="last")
        path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_parquet(path, index=False)
```

- [ ] **Step 4: Run — confirm pass**

Run: `pytest tests/pead/test_events_store.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add pead_events_store.py tests/pead/test_events_store.py
git commit -m "feat(pead): events parquet store with dedup-update"
```

### Task 3.3: Downloader orchestrator

**Files:**
- Create: `pead_downloader.py`
- Test: `tests/pead/test_downloader_e2e.py`

- [ ] **Step 1: Write failing E2E test**

`tests/pead/test_downloader_e2e.py`:

```python
import json
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from pead_downloader import run_incremental


def _stub_fetch_announcements(period):
    if period != "Quarterly":
        return []
    return [
        {"symbol": "RELIANCE", "broadcastDate": "21-Apr-2026 18:30:00",
         "fromDate": "01-Jan-2026", "toDate": "31-Mar-2026"},
        {"symbol": "INFY", "broadcastDate": "21-Apr-2026 16:00:00",
         "fromDate": "01-Jan-2026", "toDate": "31-Mar-2026"},
    ]


def _stub_build_event(ticker, result_date, period_type, eps_actual):
    return {
        "ticker": ticker, "sector": "IT",
        "result_date": result_date, "period_type": period_type,
        "eps_actual": eps_actual, "eps_history": [10, 11, 9, 10],
        "eps_expected": 10.0, "sue": 2.5,
        "piotroski": 8.0, "pb": 1.5,
        "price_at_result": 1500.0, "book_value": 1000.0,
        "pb_sector_median": float("nan"),
        "sue_decile": float("nan"),
        "qualifies_long": False, "qualifies_short": False,
    }


def _stub_get_actual_eps(ticker, result_date, period_type):
    return 15.0  # any positive value


@patch("pead_downloader.fetch_announcements", _stub_fetch_announcements)
@patch("pead_downloader.build_event", _stub_build_event)
@patch("pead_downloader.get_actual_eps", _stub_get_actual_eps)
@patch("pead_downloader.filter_universe", lambda c, **kw: c)
def test_run_incremental_writes_files(tmp_path: Path):
    cfg = {
        "events_path": tmp_path / "events.parquet",
        "live_signals_path": tmp_path / "live_signals.csv",
        "raw_dir": tmp_path / "raw",
        "status_path": tmp_path / "last_run_status.json",
        "universe": ["RELIANCE.NS", "INFY.NS"],
        "today": date(2026, 4, 22),
    }
    run_incremental(cfg)

    assert (tmp_path / "events.parquet").exists()
    df = pd.read_parquet(tmp_path / "events.parquet")
    assert len(df) == 2
    assert (tmp_path / "live_signals.csv").exists()
    status = json.loads((tmp_path / "last_run_status.json").read_text())
    assert status["declared_count"] == 2
```

- [ ] **Step 2: Run — confirm fail**

Run: `pytest tests/pead/test_downloader_e2e.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement pead_downloader.py**

```python
"""PEAD daily incremental refresh.

Flow (matches spec §10):
  1. Filter universe.
  2. Fetch today's NSE corp-announce (Quarterly + Annual).
  3. For each declaring ticker in universe: build event row.
  4. Attach sector P/B median.
  5. Compute decile cohort + qualifies flags.
  6. Append to events.parquet (dedup).
  7. Write live_signals.csv (today's qualifies_long).
  8. Write last_run_status.json.
"""
from __future__ import annotations

import json
import math
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from core.nse_announce import (
    fetch_announcements,
    parse_announcements,
    cache_raw,
)
from pead_event_builder import build_event
from pead_universe import filter_universe
from pead_cohort import compute_cohort_deciles, mark_qualifies
from pead_sector_pb import attach_sector_median
from pead_events_store import append_events


def get_actual_eps(ticker: str, result_date: date, period_type: str) -> float:
    """Pull the just-declared EPS from yfinance.

    For quarterly, latest quarterly_earnings row whose index >= result_date - 95d.
    For annual, latest annual earnings row whose index year == result_date.year - 1
    (Indian fiscal year ends Mar — adjust if needed).
    """
    import yfinance as yf
    t = yf.Ticker(ticker)
    if period_type == "Q":
        df = t.quarterly_earnings
        if df is None or df.empty:
            return math.nan
        df = df.sort_index(ascending=False)
        for idx, val in df["Earnings"].items():
            if idx.date() <= result_date:
                return float(val)
        return math.nan
    else:
        df = getattr(t, "earnings", None)
        if df is None or df.empty:
            return math.nan
        df = df.sort_index(ascending=False)
        for idx, val in df["Earnings"].items():
            if idx.year <= result_date.year:
                return float(val)
        return math.nan


def _default_cfg() -> dict[str, Any]:
    base = Path("pead_data")
    return {
        "events_path": base / "events.parquet",
        "live_signals_path": base / "live_signals.csv",
        "raw_dir": base / "nse_announce_raw",
        "status_path": base / "last_run_status.json",
        "universe": None,                              # caller supplies
        "today": date.today(),
    }


def run_incremental(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = {**_default_cfg(), **(cfg or {})}
    today: date = cfg["today"]
    universe: list[str] | None = cfg["universe"]
    if universe is None:
        raise ValueError("cfg['universe'] required (load from build_universe output)")

    universe = filter_universe(universe)

    all_raw: list[dict] = []
    for period in ("Quarterly", "Annual"):
        try:
            raw = fetch_announcements(period=period)
        except RuntimeError as e:
            _write_status(cfg["status_path"], today, error=str(e))
            raise
        cache_raw(raw, cfg["raw_dir"], today)
        all_raw.extend(raw)

    announcements = parse_announcements(all_raw)
    universe_set = set(universe)
    in_universe = [a for a in announcements if a["yf_ticker"] in universe_set]

    rows: list[dict] = []
    for a in in_universe:
        eps_actual = get_actual_eps(a["yf_ticker"], a["result_date"], a["period_type"])
        if math.isnan(eps_actual):
            continue
        ev = build_event(
            ticker=a["yf_ticker"],
            result_date=a["result_date"],
            period_type=a["period_type"],
            eps_actual=eps_actual,
        )
        rows.append(ev)

    if rows:
        df = pd.DataFrame(rows)
        df = attach_sector_median(df)
        df = compute_cohort_deciles(df, window_td=5)
        df = mark_qualifies(df)
        append_events(cfg["events_path"], df.to_dict("records"))

        live = df[df["qualifies_long"]].copy()
        Path(cfg["live_signals_path"]).parent.mkdir(parents=True, exist_ok=True)
        live.to_csv(cfg["live_signals_path"], index=False)
    else:
        Path(cfg["live_signals_path"]).parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame().to_csv(cfg["live_signals_path"], index=False)

    summary = {
        "run_date": today.isoformat(),
        "declared_count": len(in_universe),
        "rows_written": len(rows),
        "qualified_long": int(sum(r.get("qualifies_long", False) for r in rows)),
        "qualified_short": int(sum(r.get("qualifies_short", False) for r in rows)),
        "universe_size": len(universe),
        "error": None,
    }
    _write_status(cfg["status_path"], today, summary=summary)
    return summary


def _write_status(path: Path, today: date, summary: dict | None = None,
                  error: str | None = None) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    payload = summary or {
        "run_date": today.isoformat(),
        "error": error,
    }
    Path(path).write_text(json.dumps(payload, indent=2, default=str))


if __name__ == "__main__":
    import sys
    from pathlib import Path as _P
    universe_csv = _P("data/universe/universe.csv")
    if universe_csv.exists():
        u = pd.read_csv(universe_csv)["yf_ticker"].dropna().tolist()
    else:
        print("ERROR: data/universe/universe.csv missing — run build_universe.py first")
        sys.exit(1)
    summary = run_incremental({"universe": u})
    print(json.dumps(summary, indent=2, default=str))
```

- [ ] **Step 4: Run — confirm pass**

Run: `pytest tests/pead/test_downloader_e2e.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add pead_downloader.py tests/pead/test_downloader_e2e.py
git commit -m "feat(pead): daily incremental downloader orchestrator"
```

---

## Phase 4 — Historical Builder

### Task 4.1: Historical events builder

**Files:**
- Create: `pead_build_history.py`
- Test: `tests/pead/test_build_history.py`

- [ ] **Step 1: Write failing test**

`tests/pead/test_build_history.py`:

```python
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from pead_build_history import build_history


def _stub_yf_earnings_dates(ticker):
    return pd.DataFrame(
        {"EPS Estimate": [10.0, 9.0], "Reported EPS": [12.0, 11.0]},
        index=pd.to_datetime(["2025-10-20 18:00:00", "2025-07-22 18:00:00"]),
    )


@patch("pead_build_history.fetch_announcements_range", lambda s, e, period: [])
@patch("pead_build_history._yf_earnings_dates", _stub_yf_earnings_dates)
@patch("pead_build_history.build_event",
       lambda ticker, result_date, period_type, eps_actual: {
           "ticker": ticker, "sector": "IT", "result_date": result_date,
           "period_type": period_type, "eps_actual": eps_actual,
           "eps_history": [9, 10, 11, 10], "eps_expected": 10.0,
           "sue": 1.5, "piotroski": 7.0, "pb": 1.0,
           "price_at_result": 100.0, "book_value": 100.0,
           "pb_sector_median": float("nan"), "sue_decile": float("nan"),
           "qualifies_long": False, "qualifies_short": False,
       })
def test_build_history_falls_back_to_yfinance(tmp_path: Path):
    out = tmp_path / "historical_events.parquet"
    n = build_history(
        universe=["INFY.NS"],
        start=date(2025, 1, 1),
        end=date(2026, 1, 1),
        output_path=out,
    )
    assert n == 2
    df = pd.read_parquet(out)
    assert len(df) == 2
    assert df["ticker"].iloc[0] == "INFY.NS"
```

- [ ] **Step 2: Run — confirm fail**

Run: `pytest tests/pead/test_build_history.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement pead_build_history.py**

```python
"""One-time historical events backfill.

Strategy:
  1. Pull NSE corp-announce paged by month for [start..end].
  2. For gaps (tickers with no NSE hits in the range), fall back to
     yfinance ticker.earnings_dates which gives ~4yr of historical
     announcement timestamps.
  3. For each (ticker, result_date, period_type) build_event() it.
  4. Attach sector medians, compute deciles, mark qualifies, persist.

CLI:
  python pead_build_history.py --start 2022-01-01 --end 2026-05-25
"""
from __future__ import annotations

import argparse
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

from core.nse_announce import (
    fetch_announcements,
    parse_announcements,
)
from pead_event_builder import build_event
from pead_cohort import compute_cohort_deciles, mark_qualifies
from pead_sector_pb import attach_sector_median


def fetch_announcements_range(start: date, end: date, period: str) -> list[dict]:
    """NSE API doesn't support historical paging cleanly — best-effort current data only.

    Returns whatever it can. Backfill leans on yfinance fallback.
    """
    try:
        return fetch_announcements(period=period)
    except Exception:
        return []


def _yf_earnings_dates(ticker: str) -> pd.DataFrame | None:
    try:
        t = yf.Ticker(ticker)
        return t.earnings_dates
    except Exception:
        return None


def _yf_fallback_events(ticker: str, start: date, end: date) -> list[dict]:
    """Yield (result_date, period_type, eps_actual) tuples from yfinance earnings_dates."""
    df = _yf_earnings_dates(ticker)
    if df is None or df.empty:
        return []
    df = df[df["Reported EPS"].notna()]
    out: list[dict] = []
    for ts, row in df.iterrows():
        rd = ts.date() if hasattr(ts, "date") else ts
        if rd < start or rd > end:
            continue
        out.append(
            {
                "yf_ticker": ticker,
                "result_date": rd,
                "period_type": "Q",   # earnings_dates is quarterly
                "eps_actual": float(row["Reported EPS"]),
            }
        )
    return out


def build_history(
    universe: list[str],
    start: date,
    end: date,
    output_path: Path,
) -> int:
    rows: list[dict] = []

    nse_raw: list[dict] = []
    for period in ("Quarterly", "Annual"):
        nse_raw.extend(fetch_announcements_range(start, end, period))
    nse_events = parse_announcements(nse_raw)
    nse_seen: set[tuple[str, date, str]] = set()
    for a in nse_events:
        if a["yf_ticker"] not in universe:
            continue
        if a["result_date"] < start or a["result_date"] > end:
            continue
        # Need actual EPS — pull from yfinance earnings_dates
        df = _yf_earnings_dates(a["yf_ticker"])
        if df is None or df.empty:
            continue
        match = df[df.index.date == a["result_date"]]
        if match.empty or pd.isna(match["Reported EPS"].iloc[0]):
            continue
        ev = build_event(
            ticker=a["yf_ticker"],
            result_date=a["result_date"],
            period_type=a["period_type"],
            eps_actual=float(match["Reported EPS"].iloc[0]),
        )
        rows.append(ev)
        nse_seen.add((a["yf_ticker"], a["result_date"], a["period_type"]))

    for ticker in universe:
        for fb in _yf_fallback_events(ticker, start, end):
            key = (fb["yf_ticker"], fb["result_date"], fb["period_type"])
            if key in nse_seen:
                continue
            ev = build_event(
                ticker=fb["yf_ticker"],
                result_date=fb["result_date"],
                period_type=fb["period_type"],
                eps_actual=fb["eps_actual"],
            )
            rows.append(ev)
            nse_seen.add(key)

    if not rows:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame().to_parquet(output_path, index=False)
        return 0

    df = pd.DataFrame(rows)
    df = attach_sector_median(df)
    df = compute_cohort_deciles(df, window_td=5)
    df = mark_qualifies(df)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_path, index=False)
    return len(df)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True, type=lambda s: date.fromisoformat(s))
    ap.add_argument("--end", required=True, type=lambda s: date.fromisoformat(s))
    ap.add_argument("--universe-csv", default="data/universe/universe.csv")
    ap.add_argument("--out", default="pead_data/historical_events.parquet")
    args = ap.parse_args()
    u = pd.read_csv(args.universe_csv)["yf_ticker"].dropna().tolist()
    n = build_history(u, args.start, args.end, Path(args.out))
    print(f"Wrote {n} events to {args.out}")
```

- [ ] **Step 4: Run — confirm pass**

Run: `pytest tests/pead/test_build_history.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add pead_build_history.py tests/pead/test_build_history.py
git commit -m "feat(pead): historical events builder with yfinance fallback"
```

---

## Phase 5 — Backtest Engine

### Task 5.1: Portfolio data classes + next-result lookup

**Files:**
- Create: `pead_portfolio.py`
- Test: `tests/pead/test_portfolio.py`

- [ ] **Step 1: Write failing test**

`tests/pead/test_portfolio.py`:

```python
from datetime import date

import pandas as pd

from pead_portfolio import Position, Portfolio, lookup_next_result


def test_portfolio_buy_sell_pnl():
    p = Portfolio(cash=1_000_000)
    p.buy("INFY.NS", entry_date=date(2026, 4, 21), entry_px=1500.0,
          shares=100, exit_due=date(2026, 7, 14), sue=2.5, period_type="Q")
    assert len(p.open) == 1
    assert p.cash == 1_000_000 - 100 * 1500.0
    trade = p.close("INFY.NS", exit_date=date(2026, 7, 14), exit_px=1650.0,
                    reason="60D")
    assert trade["return_pct"] == pytest.approx(10.0, rel=1e-3)
    assert trade["exit_reason"] == "60D"
    assert "INFY.NS" not in p.open


def test_lookup_next_result_returns_first_after():
    events = pd.DataFrame([
        {"ticker": "INFY.NS", "result_date": date(2026, 1, 20), "period_type": "Q"},
        {"ticker": "INFY.NS", "result_date": date(2026, 4, 20), "period_type": "Q"},
        {"ticker": "INFY.NS", "result_date": date(2026, 7, 20), "period_type": "Q"},
    ])
    nxt = lookup_next_result(events, "INFY.NS", after=date(2026, 4, 25))
    assert nxt == date(2026, 7, 20)


def test_lookup_next_result_none_if_no_future():
    events = pd.DataFrame([
        {"ticker": "INFY.NS", "result_date": date(2026, 1, 20), "period_type": "Q"},
    ])
    nxt = lookup_next_result(events, "INFY.NS", after=date(2026, 6, 1))
    assert nxt is None
```

Add `import pytest` at top.

- [ ] **Step 2: Run — confirm fail**

Run: `pytest tests/pead/test_portfolio.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement pead_portfolio.py**

```python
"""Equal-weight portfolio bookkeeping for the PEAD backtest.

YAGNI: no transaction costs / slippage in v1. Spec calls them out as deferrable.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

import pandas as pd


@dataclass
class Position:
    ticker: str
    entry_date: date
    entry_px: float
    shares: int
    exit_due: date
    sue: float
    period_type: str


@dataclass
class Portfolio:
    cash: float
    open: dict[str, Position] = field(default_factory=dict)
    trades: list[dict] = field(default_factory=list)
    equity_curve: list[tuple[date, float]] = field(default_factory=list)

    def buy(self, ticker: str, entry_date: date, entry_px: float, shares: int,
            exit_due: date, sue: float, period_type: str) -> None:
        cost = shares * entry_px
        if cost > self.cash + 1e-6:
            return
        self.cash -= cost
        self.open[ticker] = Position(
            ticker=ticker, entry_date=entry_date, entry_px=entry_px,
            shares=shares, exit_due=exit_due, sue=sue, period_type=period_type,
        )

    def close(self, ticker: str, exit_date: date, exit_px: float, reason: str) -> dict:
        pos = self.open.pop(ticker)
        proceeds = pos.shares * exit_px
        self.cash += proceeds
        ret_pct = (exit_px - pos.entry_px) / pos.entry_px * 100.0
        trade = {
            "ticker": ticker,
            "entry_date": pos.entry_date,
            "entry_price": pos.entry_px,
            "shares": pos.shares,
            "exit_date": exit_date,
            "exit_price": exit_px,
            "return_pct": ret_pct,
            "hold_days": (exit_date - pos.entry_date).days,
            "exit_reason": reason,
            "period_type": pos.period_type,
            "sue": pos.sue,
        }
        self.trades.append(trade)
        return trade


def lookup_next_result(events: pd.DataFrame, ticker: str, after: date) -> date | None:
    rows = events[(events["ticker"] == ticker) & (events["result_date"] > after)]
    if rows.empty:
        return None
    return rows["result_date"].min()
```

- [ ] **Step 4: Run — confirm pass**

Run: `pytest tests/pead/test_portfolio.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add pead_portfolio.py tests/pead/test_portfolio.py
git commit -m "feat(pead): portfolio class + next-result lookup"
```

### Task 5.2: Backtest engine — exits + entries loop

**Files:**
- Create: `pead_backtest.py`
- Test: `tests/pead/test_backtest_exits.py`

- [ ] **Step 1: Write failing test**

`tests/pead/test_backtest_exits.py`:

```python
from datetime import date

import pandas as pd
import pytest

from pead_backtest import run_backtest


def _synth_price_panel():
    dates = pd.bdate_range("2026-01-01", "2026-12-31")
    px = pd.DataFrame(
        {
            "INFY.NS": [1500 + i for i in range(len(dates))],   # rising
            "WIPRO.NS": [400 - i * 0.1 for i in range(len(dates))],  # falling
        },
        index=dates,
    )
    return px


def _synth_events():
    return pd.DataFrame([
        {"ticker": "INFY.NS", "result_date": date(2026, 1, 20), "period_type": "Q",
         "sue": 2.5, "piotroski": 8, "pb": 1.0, "pb_sector_median": 2.0,
         "sue_decile": 10, "qualifies_long": True},
        {"ticker": "INFY.NS", "result_date": date(2026, 4, 20), "period_type": "Q",
         "sue": 0.0, "piotroski": 5, "pb": 1.0, "pb_sector_median": 2.0,
         "sue_decile": 5, "qualifies_long": False},
    ])


def test_run_backtest_basic_60d_exit():
    closes = _synth_price_panel()
    opens = closes.shift(-1).fillna(closes)
    events = _synth_events()
    result = run_backtest(
        events=events, closes=closes, opens=opens,
        start=date(2026, 1, 1), end=date(2026, 6, 30),
        initial_cash=1_000_000,
    )
    trades = result["trades"]
    assert len(trades) == 1
    t = trades.iloc[0]
    assert t["ticker"] == "INFY.NS"
    # Entry day = result_date + 1 trading day = 2026-01-21
    assert t["entry_date"] == pd.Timestamp("2026-01-21").date()
    # Exit day = min(entry+60td, next_result_date-1td) = next_result-1td
    # next_result = 2026-04-20 → exit = 2026-04-17 (last bday before)
    assert t["exit_reason"] == "NEXT_EARNINGS"


def test_run_backtest_no_qualifying_skip():
    closes = _synth_price_panel()
    opens = closes.shift(-1).fillna(closes)
    events = pd.DataFrame([
        {"ticker": "INFY.NS", "result_date": date(2026, 1, 20), "period_type": "Q",
         "sue": 0.0, "piotroski": 5, "pb": 1.0, "pb_sector_median": 2.0,
         "sue_decile": 5, "qualifies_long": False},
    ])
    result = run_backtest(
        events=events, closes=closes, opens=opens,
        start=date(2026, 1, 1), end=date(2026, 6, 30),
        initial_cash=1_000_000,
    )
    assert len(result["trades"]) == 0
```

- [ ] **Step 2: Run — confirm fail**

Run: `pytest tests/pead/test_backtest_exits.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement pead_backtest.py**

```python
"""PEAD historical backtest engine.

Reads events.parquet + price CSVs. Equal-weight, unlimited concurrent positions.
Exits at min(entry+60td, day_before_next_result). Long-only.
"""
from __future__ import annotations

import argparse
import math
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from core.data_io import load_ohlcv
from pead_portfolio import Portfolio, lookup_next_result

HOLD_DAYS = 60   # trading days


def _next_trading_day(idx: pd.DatetimeIndex, d: date) -> date | None:
    after = idx[idx.date > d]
    return after[0].date() if len(after) else None


def _td_offset(idx: pd.DatetimeIndex, d: date, n: int) -> date | None:
    """Return the trading day n positions after d (in idx)."""
    pos = idx.searchsorted(pd.Timestamp(d))
    if pos + n >= len(idx):
        return None
    return idx[pos + n].date()


def _prev_trading_day(idx: pd.DatetimeIndex, d: date) -> date | None:
    before = idx[idx.date < d]
    return before[-1].date() if len(before) else None


def run_backtest(
    events: pd.DataFrame,
    closes: pd.DataFrame,
    opens: pd.DataFrame,
    start: date,
    end: date,
    initial_cash: float = 1_000_000,
) -> dict[str, Any]:
    """Run the PEAD long-only backtest. Returns {trades, equity_curve, portfolio}."""
    events = events.copy()
    events["result_date"] = pd.to_datetime(events["result_date"]).dt.date
    events = events.sort_values("result_date")
    idx = closes.index

    p = Portfolio(cash=initial_cash)

    trading_days = idx[(idx.date >= start) & (idx.date <= end)]

    for ts in trading_days:
        today = ts.date()

        # 1. Exits first
        for tk in list(p.open):
            pos = p.open[tk]
            nxt = lookup_next_result(events, tk, after=pos.entry_date)
            sixty_td = _td_offset(idx, pos.entry_date, HOLD_DAYS)
            candidates = [d for d in [sixty_td] if d is not None]
            if nxt is not None:
                day_before = _prev_trading_day(idx, nxt)
                if day_before is not None and day_before > pos.entry_date:
                    candidates.append(day_before)
            if not candidates:
                continue
            exit_due = min(candidates)
            if today >= exit_due:
                if tk not in closes.columns:
                    continue
                exit_px = closes.loc[ts, tk]
                if pd.isna(exit_px):
                    continue
                reason = "60D" if exit_due == sixty_td else "NEXT_EARNINGS"
                p.close(tk, exit_date=today, exit_px=float(exit_px), reason=reason)

        # 2. Entries — events with result_date == prev trading day
        prev_td = _prev_trading_day(idx, today)
        if prev_td is None:
            continue
        yest_events = events[
            (events["result_date"] == prev_td) & (events["qualifies_long"])
        ]
        if yest_events.empty:
            continue
        total_after = len(p.open) + len(yest_events)
        cash_per_new = p.cash / total_after if total_after > 0 else 0
        for _, ev in yest_events.iterrows():
            tk = ev["ticker"]
            if tk in p.open or tk not in opens.columns:
                continue
            px = opens.loc[ts, tk]
            if pd.isna(px) or px <= 0:
                continue
            shares = int(cash_per_new // float(px))
            if shares == 0:
                continue
            sixty_td = _td_offset(idx, today, HOLD_DAYS) or end
            p.buy(
                ticker=tk, entry_date=today, entry_px=float(px),
                shares=shares, exit_due=sixty_td,
                sue=float(ev["sue"]), period_type=str(ev["period_type"]),
            )

        # 3. Mark to market
        mtm = p.cash
        for tk, pos in p.open.items():
            if tk in closes.columns and not pd.isna(closes.loc[ts, tk]):
                mtm += pos.shares * float(closes.loc[ts, tk])
        p.equity_curve.append((today, mtm))

    return {
        "trades": pd.DataFrame(p.trades),
        "equity_curve": pd.DataFrame(p.equity_curve, columns=["date", "equity"]),
        "portfolio": p,
    }


def _load_price_panels(folder: str = "data") -> tuple[pd.DataFrame, pd.DataFrame]:
    ohlcv, _ = load_ohlcv(folder)
    closes = pd.DataFrame({tk: df["Close"] for tk, df in ohlcv.items()}).sort_index()
    opens = pd.DataFrame({tk: df["Open"] for tk, df in ohlcv.items()}).sort_index()
    return closes, opens


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", default="pead_data/historical_events.parquet")
    ap.add_argument("--start", required=True, type=lambda s: date.fromisoformat(s))
    ap.add_argument("--end", required=True, type=lambda s: date.fromisoformat(s))
    ap.add_argument("--flavor", default="both", choices=["Q", "A", "both"])
    ap.add_argument("--cash", type=float, default=1_000_000)
    ap.add_argument("--trades-out", default="pead_trades.csv")
    ap.add_argument("--equity-out", default="pead_equity.csv")
    args = ap.parse_args()

    events = pd.read_parquet(args.events)
    if args.flavor != "both":
        events = events[events["period_type"] == args.flavor]

    closes, opens = _load_price_panels()
    result = run_backtest(
        events=events, closes=closes, opens=opens,
        start=args.start, end=args.end, initial_cash=args.cash,
    )
    result["trades"].to_csv(args.trades_out, index=False)
    result["equity_curve"].to_csv(args.equity_out, index=False)
    print(f"Wrote {len(result['trades'])} trades to {args.trades_out}")
    print(f"Final equity: {result['equity_curve']['equity'].iloc[-1]:,.0f}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run — confirm pass**

Run: `pytest tests/pead/test_backtest_exits.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add pead_backtest.py tests/pead/test_backtest_exits.py
git commit -m "feat(pead): backtest engine — long-only equal-weight + 60d/next-earnings exits"
```

### Task 5.3: Look-ahead audit

**Files:**
- Create: `pead_lookahead_audit.py`
- Test: `tests/pead/test_backtest_lookahead.py`

- [ ] **Step 1: Write failing test**

`tests/pead/test_backtest_lookahead.py`:

```python
from datetime import date

import pandas as pd
import pytest

from pead_lookahead_audit import audit_trades, LookaheadViolation


def test_audit_trades_passes_when_entry_after_result():
    trades = pd.DataFrame([
        {"ticker": "INFY.NS", "entry_date": date(2026, 4, 21),
         "result_date": date(2026, 4, 20)},
    ])
    audit_trades(trades)  # no exception


def test_audit_trades_raises_on_same_day_entry():
    trades = pd.DataFrame([
        {"ticker": "INFY.NS", "entry_date": date(2026, 4, 20),
         "result_date": date(2026, 4, 20)},
    ])
    with pytest.raises(LookaheadViolation):
        audit_trades(trades)


def test_audit_trades_raises_on_entry_before_result():
    trades = pd.DataFrame([
        {"ticker": "INFY.NS", "entry_date": date(2026, 4, 19),
         "result_date": date(2026, 4, 20)},
    ])
    with pytest.raises(LookaheadViolation):
        audit_trades(trades)
```

- [ ] **Step 2: Run — confirm fail**

Run: `pytest tests/pead/test_backtest_lookahead.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement pead_lookahead_audit.py**

```python
"""Look-ahead bias audit step.

Spec §8 / §11 final step: assert entry_date > result_date for every trade.
Raises LookaheadViolation on any failure.
"""
from __future__ import annotations

import pandas as pd


class LookaheadViolation(Exception):
    pass


def audit_trades(trades: pd.DataFrame) -> None:
    if trades.empty:
        return
    if "entry_date" not in trades.columns or "result_date" not in trades.columns:
        return
    bad = trades[trades["entry_date"] <= trades["result_date"]]
    if not bad.empty:
        first = bad.iloc[0]
        raise LookaheadViolation(
            f"LOOKAHEAD_VIOLATION: {first['ticker']} entry_date={first['entry_date']} "
            f"<= result_date={first['result_date']}"
        )
```

- [ ] **Step 4: Run — confirm pass**

Run: `pytest tests/pead/test_backtest_lookahead.py -v`
Expected: 3 passed.

- [ ] **Step 5: Wire audit into pead_backtest.main()**

Edit `pead_backtest.py` `main()`. Inside, after computing `result`, merge `result_date` from events into trades and call audit:

```python
    # Attach result_date to each trade for the look-ahead audit:
    # per (ticker, entry_date), use the most recent events.result_date < entry_date.
    from pead_lookahead_audit import audit_trades

    if not result["trades"].empty:
        rd_per_ticker = {
            tk: events[events["ticker"] == tk].sort_values("result_date")
            for tk in result["trades"]["ticker"].unique()
        }
        result_dates = []
        for _, t in result["trades"].iterrows():
            tk_events = rd_per_ticker[t["ticker"]]
            prior = tk_events[tk_events["result_date"] < t["entry_date"]]
            result_dates.append(
                prior["result_date"].iloc[-1] if not prior.empty else t["entry_date"]
            )
        result["trades"]["result_date"] = result_dates

    audit_trades(result["trades"])
```

- [ ] **Step 6: Verify integration**

Run: `pytest tests/pead/test_backtest_exits.py -v`
Expected: 2 passed (no regressions).

- [ ] **Step 7: Commit**

```bash
git add pead_lookahead_audit.py tests/pead/test_backtest_lookahead.py pead_backtest.py
git commit -m "feat(pead): look-ahead audit step + wire into backtest main"
```

### Task 5.4: Diagnostics — Sharpe/DD/CAGR + decile-spread

**Files:**
- Create: `pead_diagnostics.py`
- Test: `tests/pead/test_diagnostics.py`

- [ ] **Step 1: Write failing test**

`tests/pead/test_diagnostics.py`:

```python
from datetime import date

import numpy as np
import pandas as pd
import pytest

from pead_diagnostics import compute_kpis, compute_decile_spread


def test_compute_kpis_basic():
    eq = pd.DataFrame({
        "date": pd.bdate_range("2025-01-01", periods=252),
        "equity": [1_000_000 * (1.0008 ** i) for i in range(252)],
    })
    trades = pd.DataFrame([
        {"return_pct": 5.0, "exit_reason": "60D"},
        {"return_pct": -3.0, "exit_reason": "60D"},
        {"return_pct": 8.0, "exit_reason": "NEXT_EARNINGS"},
    ])
    kpi = compute_kpis(eq, trades)
    assert kpi["cagr"] == pytest.approx(0.221, abs=0.02)
    assert kpi["win_rate"] == pytest.approx(2/3, abs=1e-3)
    assert kpi["num_trades"] == 3
    assert kpi["max_dd"] <= 0


def test_compute_decile_spread():
    events = pd.DataFrame([
        {"sue_decile": d, "ticker": f"T{i}.NS",
         "fwd_60d_return": d * 0.5}     # decile 10 -> 5%, decile 1 -> 0.5%
        for d in range(1, 11) for i in range(5)
    ])
    spread = compute_decile_spread(events)
    assert spread.loc[10] > spread.loc[1]
    assert pytest.approx(spread.loc[10], abs=0.01) == 5.0
```

- [ ] **Step 2: Run — confirm fail**

Run: `pytest tests/pead/test_diagnostics.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement pead_diagnostics.py**

```python
"""Backtest KPIs and SUE-decile diagnostic."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd


def _max_drawdown(equity: pd.Series) -> float:
    peak = equity.cummax()
    dd = (equity - peak) / peak
    return float(dd.min())


def compute_kpis(equity_curve: pd.DataFrame, trades: pd.DataFrame) -> dict[str, float]:
    eq = equity_curve["equity"].astype(float)
    days = (equity_curve["date"].iloc[-1] - equity_curve["date"].iloc[0]).days
    years = max(days / 365.25, 1e-6)
    final = eq.iloc[-1]
    initial = eq.iloc[0]
    cagr = (final / initial) ** (1 / years) - 1
    returns = eq.pct_change().dropna()
    sharpe = (returns.mean() / returns.std()) * np.sqrt(252) if returns.std() > 0 else 0
    downside = returns[returns < 0]
    sortino = (returns.mean() / downside.std()) * np.sqrt(252) if len(downside) and downside.std() > 0 else 0
    mdd = _max_drawdown(eq)

    if trades.empty:
        win_rate = 0.0
        avg_win = avg_loss = best = worst = 0.0
        avg_hold = 0
    else:
        wins = trades[trades["return_pct"] > 0]
        losses = trades[trades["return_pct"] <= 0]
        win_rate = len(wins) / len(trades)
        avg_win = float(wins["return_pct"].mean()) if len(wins) else 0.0
        avg_loss = float(losses["return_pct"].mean()) if len(losses) else 0.0
        best = float(trades["return_pct"].max())
        worst = float(trades["return_pct"].min())
        avg_hold = float(trades.get("hold_days", pd.Series([0])).mean())

    return {
        "cagr": float(cagr),
        "sharpe": float(sharpe),
        "sortino": float(sortino),
        "max_dd": float(mdd),
        "win_rate": float(win_rate),
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "best_trade": best,
        "worst_trade": worst,
        "avg_hold_days": avg_hold,
        "num_trades": int(len(trades)),
    }


def compute_decile_spread(events: pd.DataFrame) -> pd.Series:
    """Avg `fwd_60d_return` per SUE decile. Caller pre-computes fwd_60d_return."""
    df = events.dropna(subset=["sue_decile", "fwd_60d_return"])
    return df.groupby("sue_decile")["fwd_60d_return"].mean()


def attach_fwd_60d(events: pd.DataFrame, closes: pd.DataFrame, hold_td: int = 60) -> pd.DataFrame:
    """Append fwd_60d_return column for decile diagnostic.

    For each event, look up close at result_date+1td and result_date+1td+hold_td.
    """
    events = events.copy()
    idx = closes.index
    rets: list[float] = []
    for _, row in events.iterrows():
        tk = row["ticker"]
        if tk not in closes.columns:
            rets.append(math.nan)
            continue
        rd = pd.Timestamp(row["result_date"])
        pos = idx.searchsorted(rd, side="right")
        if pos + hold_td >= len(idx):
            rets.append(math.nan)
            continue
        entry_px = closes.iloc[pos][tk]
        exit_px = closes.iloc[pos + hold_td][tk]
        if pd.isna(entry_px) or pd.isna(exit_px) or entry_px <= 0:
            rets.append(math.nan)
            continue
        rets.append((exit_px - entry_px) / entry_px * 100.0)
    events["fwd_60d_return"] = rets
    return events
```

- [ ] **Step 4: Run — confirm pass**

Run: `pytest tests/pead/test_diagnostics.py -v`
Expected: 2 passed.

- [ ] **Step 5: Wire diagnostics into backtest CLI**

Edit `pead_backtest.py` `main()`, after audit:

```python
    from pead_diagnostics import compute_kpis, compute_decile_spread, attach_fwd_60d
    kpis = compute_kpis(result["equity_curve"], result["trades"])
    print("KPIs:", kpis)
    events_with_fwd = attach_fwd_60d(events, closes)
    spread = compute_decile_spread(events_with_fwd)
    spread.to_csv("pead_decile_spread.csv")
    pd.Series(kpis).to_csv("pead_kpis.csv")
```

- [ ] **Step 6: Commit**

```bash
git add pead_diagnostics.py tests/pead/test_diagnostics.py pead_backtest.py
git commit -m "feat(pead): KPI + SUE-decile-spread diagnostics in backtest"
```

---

## Phase 6 — Dashboard

### Task 6.1: pead_dashboard.py skeleton + render()

**Files:**
- Create: `pead_dashboard.py`

- [ ] **Step 1: Create skeleton**

```python
"""Streamlit page for PEAD strategy. Registered by master_dashboard.py."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import streamlit as st


DATA = Path("pead_data")


def render() -> None:
    st.title("📊 PEAD Strategy")
    st.caption(
        "Post-Earnings-Announcement Drift — long top-decile SUE filtered for quality."
    )

    _glossary_expander()
    _refresh_strip()

    tab1, tab2, tab3, tab4 = st.tabs(
        ["Live + Open", "Backtest", "Calendar + Heatmap", "Screener"]
    )
    with tab1:
        _tab_live_open()
    with tab2:
        _tab_backtest()
    with tab3:
        _tab_calendar_heatmap()
    with tab4:
        _tab_screener()


def _glossary_expander() -> None:
    with st.expander("📖 Glossary"):
        st.markdown(
            "- **SUE (Standardised Unexpected Earnings):** "
            "How many standard deviations the latest EPS is above the average of the "
            "last 4 same-period EPS. Higher = bigger positive surprise.\n"
            "- **Piotroski F-Score (0–9):** Nine yes/no questions about profitability, "
            "leverage, and efficiency. ≥7 = strong balance sheet.\n"
            "- **P/B (Price-to-Book):** Stock price ÷ book value per share. "
            "Lower than sector median ≈ relatively cheap.\n"
            "- **Decile:** Stocks ranked into 10 buckets by SUE within a rolling cohort. "
            "Decile 10 = top 10% surprises.\n"
            "- **PEAD drift:** Tendency of beats/misses to keep drifting for ~60 days."
        )


def _refresh_strip() -> None:
    status_path = DATA / "last_run_status.json"
    cols = st.columns([3, 1])
    with cols[0]:
        if status_path.exists():
            s = json.loads(status_path.read_text())
            st.caption(
                f"Last refresh: {s.get('run_date')} · "
                f"{s.get('rows_written', 0)} events · "
                f"{s.get('qualified_long', 0)} qualified long"
            )
        else:
            st.caption("No refresh data — run pead_downloader.py")
    with cols[1]:
        if st.button("🔄 Run incremental refresh"):
            with st.spinner("Refreshing fundamentals…"):
                proc = subprocess.run(
                    [sys.executable, "pead_downloader.py"],
                    capture_output=True, text=True, timeout=600,
                )
            st.code(proc.stdout[-2000:] or proc.stderr[-2000:])


def _tab_live_open() -> None:
    st.subheader("Live Signals — tomorrow's qualifying entries")
    live = DATA / "live_signals.csv"
    if not live.exists():
        st.info("No live_signals.csv yet — run the downloader.")
    else:
        df = pd.read_csv(live)
        st.dataframe(
            df[["ticker", "sector", "sue", "sue_decile", "eps_actual",
                "eps_expected", "piotroski", "pb", "pb_sector_median",
                "result_date", "period_type"]],
            use_container_width=True,
        )
        st.download_button(
            "Download CSV", df.to_csv(index=False), file_name="live_signals.csv"
        )

    st.subheader("Open Positions")
    op = DATA / "open_positions.parquet"
    if not op.exists():
        st.info("No open positions yet.")
        return
    df = pd.read_parquet(op)
    st.dataframe(df, use_container_width=True)


def _tab_backtest() -> None:
    st.subheader("Backtest Results")
    eq_path = Path("pead_equity.csv")
    tr_path = Path("pead_trades.csv")
    kpi_path = Path("pead_kpis.csv")
    spread_path = Path("pead_decile_spread.csv")

    if not eq_path.exists():
        st.warning("No backtest results — run `python pead_backtest.py --start … --end …`")
        return

    eq = pd.read_csv(eq_path, parse_dates=["date"])
    st.line_chart(eq.set_index("date")["equity"])

    if kpi_path.exists():
        kpis = pd.read_csv(kpi_path, index_col=0).iloc[:, 0]
        cols = st.columns(4)
        cols[0].metric("CAGR", f"{kpis['cagr']*100:.1f}%")
        cols[1].metric("Max DD", f"{kpis['max_dd']*100:.1f}%")
        cols[2].metric("Sharpe", f"{kpis['sharpe']:.2f}")
        cols[3].metric("Win Rate", f"{kpis['win_rate']*100:.1f}%")

    if spread_path.exists():
        st.subheader("SUE Decile Performance (60d fwd return)")
        spread = pd.read_csv(spread_path, index_col=0).iloc[:, 0]
        st.bar_chart(spread)

    if tr_path.exists():
        st.subheader("Trades")
        trades = pd.read_csv(tr_path)
        st.dataframe(trades, use_container_width=True)


def _tab_calendar_heatmap() -> None:
    st.subheader("Earnings Calendar — next 30 days")
    rd = DATA / "result_dates.parquet"
    if rd.exists():
        df = pd.read_parquet(rd)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No forward calendar yet.")

    st.subheader("EPS Surprise Heatmap — last 8 quarters")
    ev_path = DATA / "events.parquet"
    if not ev_path.exists():
        st.info("No events yet.")
        return
    ev = pd.read_parquet(ev_path)
    ev["quarter"] = pd.to_datetime(ev["result_date"]).dt.to_period("Q").astype(str)
    pivot = ev.pivot_table(
        index="sector", columns="quarter", values="sue", aggfunc="mean"
    )
    st.dataframe(
        pivot.style.background_gradient(cmap="RdYlGn", axis=None),
        use_container_width=True,
    )


def _tab_screener() -> None:
    st.subheader("Piotroski / P-B / SUE Screener")
    ev_path = DATA / "events.parquet"
    if not ev_path.exists():
        st.info("No events yet — run the downloader.")
        return
    ev = pd.read_parquet(ev_path)
    c1, c2, c3, c4 = st.columns(4)
    sue_min = c1.slider("SUE min", -5.0, 5.0, -3.0, 0.1)
    pio_min = c2.slider("Piotroski min", 0, 9, 5)
    pb_max = c3.number_input("P/B max", value=10.0)
    sectors = c4.multiselect("Sector", sorted(ev["sector"].dropna().unique().tolist()))

    df = ev[(ev["sue"] >= sue_min) & (ev["piotroski"] >= pio_min) & (ev["pb"] <= pb_max)]
    if sectors:
        df = df[df["sector"].isin(sectors)]
    st.dataframe(df, use_container_width=True)
    st.download_button("Download CSV", df.to_csv(index=False), file_name="pead_screener.csv")
```

- [ ] **Step 2: Smoke test — page imports**

Run: `python -c "import pead_dashboard; print('OK')"`
Expected: `OK`.

- [ ] **Step 3: Commit**

```bash
git add pead_dashboard.py
git commit -m "feat(pead): pead_dashboard.py — 4 tabs (Live+Open, Backtest, Calendar, Screener)"
```

### Task 6.2: Wire PEAD page into master_dashboard.py

**Files:**
- Modify: `master_dashboard.py`

- [ ] **Step 1: Inspect current sidebar block**

Run: `grep -n "sidebar" master_dashboard.py | head -20`
Identify line where strategies are listed.

- [ ] **Step 2: Add PEAD entry**

Find the sidebar radio/selectbox block. Add `"📊 PEAD Strategy"` as a new option. After the existing dispatch (e.g. `elif page == "IPO Edge":`), add:

```python
elif page == "📊 PEAD Strategy":
    import pead_dashboard
    pead_dashboard.render()
```

(Use exact pattern from the existing dispatch — do NOT invent. Read the file first.)

- [ ] **Step 3: Smoke test**

Run: `streamlit run master_dashboard.py --server.headless true &`
Wait 5s, then `curl -s http://localhost:8501/healthz`.
Stop server.
Expected: server starts without import errors.

- [ ] **Step 4: Commit**

```bash
git add master_dashboard.py
git commit -m "feat(pead): register PEAD page in master_dashboard sidebar"
```

---

## Phase 7 — Operations Wiring

### Task 7.1: Add pead_downloader to refresh_data.bat + run_all.py

**Files:**
- Modify: `refresh_data.bat`
- Modify: `run_all.py`

- [ ] **Step 1: Read both files first**

```bash
cat refresh_data.bat
cat run_all.py
```

- [ ] **Step 2: Append PEAD step to refresh_data.bat**

After the last `python` line in `refresh_data.bat`, add:

```bat
echo === PEAD daily refresh ===
python pead_downloader.py
if errorlevel 1 echo PEAD downloader failed
```

- [ ] **Step 3: Append PEAD step to run_all.py**

Find the existing step list (e.g. list of strategies the script iterates). Append a PEAD entry following the existing pattern. If `run_all.py` uses a `STEPS` list/dict, add `("PEAD downloader", "pead_downloader.py")` in the same shape.

(Read the file first — match the existing pattern exactly.)

- [ ] **Step 4: Smoke run**

Run: `python run_all.py --dry-run` (if supported) OR `python -c "import run_all; print('OK')"`
Expected: no syntax errors.

- [ ] **Step 5: Commit**

```bash
git add refresh_data.bat run_all.py
git commit -m "ops(pead): wire pead_downloader into refresh_data.bat + run_all.py"
```

### Task 7.2: Update MEMORY.md + project_overview.md

**Files:**
- Modify: `C:/Users/User/.claude/projects/C--Users-User-Documents-Stocks-Nifty-Momentum-Rotation-Stratergy/memory/MEMORY.md`
- Modify: `C:/Users/User/.claude/projects/C--Users-User-Documents-Stocks-Nifty-Momentum-Rotation-Stratergy/memory/project_overview.md`

- [ ] **Step 1: Add pointer to MEMORY.md**

Append after the existing index entries:

```markdown
- [PEAD Strategy](pead_strategy.md) — Strategy #4: SUE-based post-earnings-drift, quarterly + annual, long-only
```

- [ ] **Step 2: Create pead_strategy.md**

Create new file `C:/Users/User/.claude/projects/C--Users-User-Documents-Stocks-Nifty-Momentum-Rotation-Stratergy/memory/pead_strategy.md`:

```markdown
---
name: pead-strategy
description: Strategy #4 — Post-Earnings-Announcement Drift. SUE deciles + Piotroski + P/B filter, long-only, 60d hold or next-earnings.
metadata:
  type: project
---

# PEAD Strategy (Strategy #4)

**Goal:** Trade post-earnings-announcement drift on Nifty 200-ish universe.

**Mechanic:** Long top-decile SUE AND Piotroski ≥ 7 AND P/B ≤ sector median. Exit at min(60td, day-before-next-earnings).

**Data source:** yfinance (fundamentals) + NSE `/api/corporates-financial-results` (exact declared dates).

**Files:**
- `core/{sue, piotroski, nse_announce, fundamentals}.py` — primitives
- `pead_downloader.py` — daily incremental
- `pead_backtest.py` — historical engine
- `pead_dashboard.py` — Streamlit page (4 tabs)
- `pead_data/` — events.parquet, live_signals.csv, etc.

**Spec:** `docs/superpowers/specs/2026-05-25-pead-strategy-design.md`
**Plan:** `docs/superpowers/plans/2026-05-25-pead-strategy.md`

**Why:** Adds an earnings-event-driven strategy uncorrelated with the existing momentum/IPO/Edge approaches. Indian retail cash → long-only; paper long-short tracked as diagnostic.
**How to apply:** When suggesting next steps, check [[pending_work]] before recommending re-runs. PEAD universe filter handled at runtime — don't rebuild build_universe.py.
```

- [ ] **Step 3: Update project_overview.md**

In the existing file, change "## 3 Strategies" heading to "## 4 Strategies" and append a new subsection:

```markdown
### 4. PEAD (`pead_backtest.py` / `pead_dashboard.py`)
- Long top-decile SUE filtered for Piotroski≥7 + P/B≤sector median
- Both quarterly + annual flavors
- Exit at min(60td, day-before-next-earnings)
- **Status: NEW — implementation in progress per `docs/superpowers/plans/2026-05-25-pead-strategy.md`**
```

- [ ] **Step 4: Commit (memory files are outside repo — no git op needed)**

Memory files live in `~/.claude/projects/...` not the repo. No commit. Verify files exist:

```bash
ls "C:/Users/User/.claude/projects/C--Users-User-Documents-Stocks-Nifty-Momentum-Rotation-Stratergy/memory/"
```

Expected: includes `pead_strategy.md`.

### Task 7.3: Final integration smoke test

**Files:** none (verification only)

- [ ] **Step 1: Full test suite**

Run: `pytest tests/pead/ -v --cov=core --cov=pead_downloader --cov=pead_backtest --cov-report=term`
Expected: all pass, coverage ≥ 80%.

- [ ] **Step 2: Build universe (if not already built)**

Run: `ls data/universe/ 2>&1 | head`
If empty: `python build_universe.py`.

- [ ] **Step 3: Historical build (smoke — narrow window)**

Run: `python pead_build_history.py --start 2024-01-01 --end 2026-05-25`
Expected: writes `pead_data/historical_events.parquet` with >0 rows.

- [ ] **Step 4: Backtest run**

Run: `python pead_backtest.py --start 2024-06-01 --end 2026-05-25 --flavor both`
Expected: writes `pead_trades.csv`, `pead_equity.csv`, `pead_kpis.csv`, `pead_decile_spread.csv`. No `LOOKAHEAD_VIOLATION`.

- [ ] **Step 5: Inspect decile spread**

Run: `python -c "import pandas as pd; print(pd.read_csv('pead_decile_spread.csv'))"`
Expected: decile 10 > decile 1 (edge sanity).

- [ ] **Step 6: Daily downloader smoke**

Run: `python pead_downloader.py`
Expected: writes `pead_data/last_run_status.json` with `error: null`. Likely 0 declared if not result-season — that's fine.

- [ ] **Step 7: Dashboard render**

Run: `streamlit run master_dashboard.py`
Manually navigate to PEAD page. Verify each of 4 tabs renders without exceptions.

- [ ] **Step 8: Commit final state**

```bash
git add pead_data/ pead_trades.csv pead_equity.csv pead_kpis.csv pead_decile_spread.csv
git commit -m "feat(pead): initial backtest results + live downloader smoke output"
```

---

## Acceptance Criteria (from spec §19)

- [ ] Unit tests pass with ≥80% coverage; SUE/Piotroski/look-ahead at 100%.
- [ ] `pead_downloader.py` runs daily, <2 min, writes live_signals.csv + events.parquet.
- [ ] `pead_backtest.py --flavor both` produces equity, trades, diagnostics with no look-ahead violations.
- [ ] SUE-decile-spread chart shows monotonic-ish upward slope.
- [ ] Dashboard 4 tabs render < 3s.
- [ ] `master_dashboard.py` PEAD page registered.
- [ ] MEMORY.md updated.
