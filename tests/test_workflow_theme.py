"""The component must register with each runtime, including after a rerun."""
from streamlit.testing.v1 import AppTest


def test_native_theme_survives_rerun():
    app = AppTest.from_string(
        "import streamlit as st\n"
        "from core.workflow_ui import native_theme\n"
        "native_theme()\n"
        "st.button('Rerun')\n",
        default_timeout=20,
    ).run()
    assert not app.exception
    app.button[0].click().run()
    assert not app.exception
