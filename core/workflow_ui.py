"""Small, theme-aware presentation helpers for the Streamlit workflow."""
from __future__ import annotations

import streamlit as st


def _theme_bridge():
    """Register in the current runtime; native Settings owns the theme."""
    return st.components.v2.component(
        "workflow_native_theme",
        html='<span id="theme-probe" aria-hidden="true"></span>',
        css='#theme-probe { position:absolute; width:0; height:0; background:var(--st-background-color); }',
        js="""export default function({parentElement, setStateValue}) {
            const probe = parentElement.querySelector('#theme-probe');
            let previous;
            function sync() {
                const rgb = getComputedStyle(probe).backgroundColor.match(/[\\d.]+/g);
                if (!rgb || rgb.length < 3) return;
                const brightness = .2126 * +rgb[0] + .7152 * +rgb[1] + .0722 * +rgb[2];
                const theme = brightness > 128 ? 'light' : 'dark';
                document.documentElement.dataset.theme = theme;
                document.body.dataset.theme = theme;
                if (theme !== previous) {
                    previous = theme;
                    setStateValue('theme', theme);
                }
            }
            sync();
            const timer = setInterval(sync, 500);
            return () => clearInterval(timer);
        }""",
    )


def native_theme() -> None:
    result = _theme_bridge()(key="workflow_theme", on_theme_change=lambda: None)
    if result.theme in ("light", "dark"):
        st.session_state["_native_theme"] = result.theme


def section_help(title: str, explanation: str) -> None:
    """Keep the meaning next to the section, without requiring glossary knowledge."""
    st.markdown(f"**{title}**")
    st.write(explanation)


def workflow_style() -> None:
    st.markdown("""<style>
    [data-testid="stMainBlockContainer"] { padding-top: 2rem; }
    [data-testid="stMetric"] { font-variant-numeric: tabular-nums; }
    [data-testid="stMetricLabel"] { font-weight: 500; }
    [data-testid="stMetric"] { box-shadow: none !important; }
    [data-testid="stMetricValue"] { font-size: 1.6rem !important; }
    [data-testid="stMain"] h1 { font-size: 1.9rem !important; line-height: 1.25 !important; }
    [data-testid="stMain"] h2 { font-size: 1.4rem !important; }
    [data-testid="stMain"] h3 { font-size: 1.15rem !important; }
    [data-testid="stVerticalBlockBorderWrapper"] { border-radius: 12px; }
    [data-testid="stTabs"] button { font-weight: 600; }
    [data-testid="stDataFrame"] { border-radius: 8px; }
    [data-testid="stSidebar"] .stButton button {
        padding: 0.35rem 0.4rem; min-height: 2.5rem;
    }
    [data-testid="stSidebar"] .stButton button p {
        white-space: nowrap; font-size: 12px;
    }
    [data-theme="light"] [data-testid="stHeader"] {
        background: var(--background, #fff);
        color: var(--foreground, #171717);
    }
    @media (max-width: 700px) {
        [data-testid="stMainBlockContainer"] { padding: 1rem !important; }
        [data-testid="stHorizontalBlock"] { flex-wrap: wrap !important; gap: 1rem !important; }
        [data-testid="stColumn"] { min-width: min(100%, 260px) !important; flex: 1 1 260px !important; }
        [data-testid="stMain"] h1 { font-size: 1.5rem !important; }
    }
    </style>""", unsafe_allow_html=True)


def research_notice() -> None:
    st.caption(
        "Historical simulation • These are model results, not your account performance. "
        "Trading costs and performance on previously unseen periods are not verified for this report. "
        "A best holding period has not yet been established."
    )


TRENDLYNE_CHECKS = {
    "Financials": [
        "Company has seen consistent profit growth in the last eight quarters?",
        "Company has seen consistent sales growth in the last eight quarters?",
        "Company has high Trendlyne Durability Score?",
        "Company has high Piotroski Score?",
        "Company has Low Debt?",
        "Shareholder Value: Company has Strong ROE?",
        "Company has Positive Net Cash Flow?",
        "Company is generating increasing cash from operations?",
    ],
    "Ownership": [
        "FII/FPI or DIIs are buying the stock?",
        "Promoters are buying the stock or ownership is stable?",
        "Promoter pledge is low and not increasing?",
        "Insiders have not sold stock in the past 3 months?",
    ],
    "Peer comparison": [
        "Company is giving better long term returns than the industry?",
        "Company's sales growth is better than the industry median?",
        "Company's profit growth is better than the industry median?",
    ],
    "Value and momentum": [
        "The stock is in the Buy Zone according to its historical P/E?",
        "The stock is in the Buy Zone according to its historical P/BV?",
        "Company's valuation score signals overall affordability?",
        "Trendlyne Momentum Score shows bullishness?",
        "Stock is trading above all short term SMAs?",
        "Stock is trading above all long term SMAs?",
        "Stock has bullish candlesticks?",
        "Stock has active positive breakouts?",
    ],
}
