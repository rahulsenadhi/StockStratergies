# core/refresh_ui.py
"""Streamlit staleness banner (S0b). Import lazily inside pages.

The Update button moved to the Next.js app (web/) so only one app writes the data
files at a time; this banner now points there instead.
"""
from __future__ import annotations

import streamlit as st

from core.staleness import dataset_staleness
from core.workflow_ui import UPDATES_MOVED_NOTE


def render_staleness_banner(strategy_name: str, dataset_folder: str) -> None:
    """Show a data-freshness banner and, when behind, where to update.

    strategy_name is kept for callers; it is a key in core.refresh.STRATEGY_CFG.
    """
    info = dataset_staleness(dataset_folder)
    days_behind = info["days_behind"]
    latest = info["latest_date"]

    if days_behind is None:
        st.warning("No local data found for this strategy.")
    elif days_behind <= 0:
        st.success(f"✓ Data up to date ({latest})")
        return
    else:
        plural = "day" if days_behind == 1 else "days"
        st.warning(f"⚠ Data {days_behind} trading {plural} behind (latest: {latest}).")
    st.caption(UPDATES_MOVED_NOTE)
