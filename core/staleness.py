# core/staleness.py
"""Report how many trading days behind a dataset's local CSVs are (S0b banner)."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from core.incremental import last_stored_date, trading_days_between

# Tickers refresh together, so staleness is uniform; sampling a few files is
# accurate and avoids reading thousands of CSVs on every page load.
DEFAULT_SAMPLE = 25


def dataset_staleness(folder, today: dt.date | None = None, sample: int = DEFAULT_SAMPLE) -> dict:
    """Return {"latest_date": date|None, "days_behind": int|None}.

    Skips benchmark files (names starting with '^'). Reads up to `sample` files.
    """
    today = today or dt.date.today()
    folder = Path(folder)
    csvs = [p for p in sorted(folder.glob("*.csv")) if not p.name.startswith("^")]
    if sample:
        csvs = csvs[:sample]

    latest = None
    for p in csvs:
        d = last_stored_date(p)
        if d and (latest is None or d > latest):
            latest = d

    if latest is None:
        return {"latest_date": None, "days_behind": None}
    return {"latest_date": latest, "days_behind": trading_days_between(latest, today)}
