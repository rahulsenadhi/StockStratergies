# core/refresh_ui.py
"""Streamlit staleness banner + Update button (S0b). Import lazily inside pages."""
from __future__ import annotations

import streamlit as st

from core.refresh import refresh_strategy
from core.staleness import dataset_staleness


def render_staleness_banner(strategy_name: str, dataset_folder: str) -> None:
    """Show a data-freshness banner; if behind, offer an Update button.

    strategy_name must be a key in core.refresh.STRATEGY_CFG.
    """
    info = dataset_staleness(dataset_folder)
    days_behind = info["days_behind"]
    latest = info["latest_date"]

    if days_behind is None:
        st.warning("No local data found for this strategy. Click **Update now** to download.")
    elif days_behind <= 0:
        st.success(f"✓ Data up to date ({latest})")
        return
    else:
        plural = "day" if days_behind == 1 else "days"
        st.warning(f"⚠ Data {days_behind} trading {plural} behind (latest: {latest}).")

    busy_key = f"_refreshing_{strategy_name}"
    busy = st.session_state.get(busy_key, False)

    if st.button("Update now", key=f"upd_{strategy_name}", disabled=busy):
        st.session_state[busy_key] = True
        try:
            with st.status(f"Updating {strategy_name}…", expanded=True) as status_box:
                refresh_strategy(strategy_name, st_status=status_box)
                status_box.update(label="Update complete", state="complete")
            st.cache_data.clear()
            st.rerun()
        except Exception as exc:                       # surface, keep data intact
            st.error(f"Update failed: {exc}")
        finally:
            st.session_state[busy_key] = False
