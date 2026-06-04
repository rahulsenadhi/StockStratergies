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

    try:
        _p = Path(__file__).resolve().parent / 'exit_recommendations.json'
        _pead = json.loads(_p.read_text()).get('pead', {}).get('ALL') if _p.exists() else None
    except Exception:
        _pead = None
    if _pead:
        st.markdown('#### Exit Playbook - PEAD')
        st.write(f"Recommended hold **{_pead['hold_days']} days** - "
                 f"targets +{_pead['targets'][0]['pct']:.0f}/"
                 f"+{_pead['targets'][1]['pct']:.0f}/"
                 f"+{_pead['targets'][2]['pct']:.0f}% - "
                 f"stop {_pead['stop_pct']:.0f}% - "
                 f"sample {_pead['sample_size']} trades")
    else:
        st.info('Exit Playbook: insufficient PEAD trade history yet.')

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
