"""Clickable research table (presentation only).

Renders HTML built by ``core.ui_components.data_table`` and reports which row
the user clicked or activated with the keyboard. Uses Streamlit's built-in
``st.components.v2`` API (already used by core/workflow_ui.py), so no extra
dependency is needed. Selection is kept in ``st.session_state`` so the chosen
row stays highlighted across reruns.
"""
from __future__ import annotations

import streamlit as st

_JS = """export default function({ parentElement, data, setTriggerValue }) {
    parentElement.innerHTML = data || '';
    const rows = parentElement.querySelectorAll('tr[data-row]');
    rows.forEach((tr) => {
        const pick = () => setTriggerValue('row', tr.getAttribute('data-row'));
        tr.addEventListener('click', pick);
        tr.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); pick(); }
        });
    });
}"""

_table = st.components.v2.component("rd_research_table", js=_JS, isolate_styles=False)


def selected_row(state_key: str) -> str | None:
    """Row id the user last picked in the table rendered with this key."""
    return st.session_state.get(f"{state_key}__selected")


def clickable_table(html: str, *, key: str, on_select=None) -> str | None:
    """Show ``html`` (from ui_components.data_table) and return the selected row id, if any.

    The selection is stored before the rerun, so callers can build the table
    with ``selected=selected_row(key)`` and the highlight matches the click.
    ``on_select(row_id)`` runs as a widget callback (before the rerun), so it
    may change other widget state such as the sidebar page.
    """
    def _remember() -> None:
        value = st.session_state.get(key)
        row = getattr(value, "row", None) if value is not None else None
        if row is None and isinstance(value, dict):
            row = value.get("row")
        if row is not None:
            st.session_state[f"{key}__selected"] = row
            if on_select is not None:
                on_select(row)

    _table(key=key, data=html, on_row_change=_remember)
    return selected_row(key)
