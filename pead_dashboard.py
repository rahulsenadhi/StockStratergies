"""Streamlit page for PEAD strategy. Registered by master_dashboard.py."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import math
import statistics

import pandas as pd
import streamlit as st


from core.workflow_ui import TRENDLYNE_CHECKS, research_notice, workflow_style, section_help

BASE = Path(__file__).resolve().parent
DATA = BASE / "pead_data"

COLUMN_LABELS = {
    "ticker": "Company / ticker", "sector": "Industry", "result_date": "Result date",
    "period_type": "Reporting period", "sue": "Earnings strength (SUE)",
    "sue_decile": "Earnings group (1–10)", "eps_actual": "Latest profit per share",
    "eps_expected": "Previous-four average", "piotroski": "Financial checks passed (0–9)",
    "pb": "Price / book value", "pb_sector_median": "Industry middle P/B",
    "qualifies_long": "Eligible in saved run", "entry_date": "Entry date",
    "exit_date": "Exit date", "entry_price": "Entry price", "exit_price": "Exit price",
    "return_pct": "Gain / loss (%)", "hold_days": "Calendar days held", "shares": "Number of shares",
    "exit_reason": "Reason for exit",
}


def _show_table(frame, **kwargs) -> None:
    display = frame.copy()
    if "period_type" in display:
        display["period_type"] = display["period_type"].map(_period)
    st.dataframe(display.rename(columns=COLUMN_LABELS), hide_index=True, width="stretch", **kwargs)


def _period(value) -> str:
    return {"Q": "Quarterly", "A": "Annual", "Y": "Annual"}.get(str(value), str(value) if pd.notna(value) else "Not recorded")


def _coverage(frame: pd.DataFrame) -> str:
    if "result_date" not in frame:
        return "Dates not recorded"
    dates = pd.to_datetime(frame["result_date"], errors="coerce").dropna()
    return f"{dates.min():%d %b %Y} to {dates.max():%d %b %Y}" if not dates.empty else "Dates not recorded"


def _go_find() -> None:
    st.session_state["pead_section"] = "Find companies"


def _read_frame(path: Path, **kwargs) -> pd.DataFrame:
    """Missing and headerless feeds are empty states, not page failures."""
    if not path.exists():
        return pd.DataFrame()
    try:
        if path.suffix == ".parquet":
            return pd.read_parquet(path)
        return pd.read_csv(path, **kwargs)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()
    except (OSError, ValueError, pd.errors.ParserError) as exc:
        st.warning("Some saved information could not be opened. Other sections may still be available.")
        with st.expander("Details of the unavailable information"):
            st.code(f"{path.name}: {exc}")
        return pd.DataFrame()


def _number(value) -> float | None:
    try:
        n = float(value)
        return n if math.isfinite(n) else None
    except (TypeError, ValueError):
        return None


def _fmt(value) -> str:
    n = _number(value)
    return f"{n:,.2f}" if n is not None else "Not recorded"


def qualification_checks(row) -> list[dict]:
    """Explain stored inputs; do not regenerate historical eligibility."""
    result = []
    for label, value, threshold, comparison in [
        ("Earnings rank: decile 10", row.get("sue_decile"), 10, "eq"),
        ("Piotroski: at least 7 / 9", row.get("piotroski"), 7, "ge"),
        ("P/B: at or below sector median", row.get("pb"), row.get("pb_sector_median"), "le"),
    ]:
        n, limit = _number(value), _number(threshold)
        state = "Missing"
        if n is not None and limit is not None:
            passed = n == limit if comparison == "eq" else n >= limit if comparison == "ge" else n <= limit
            state = "Pass" if passed else "Fail"
        result.append({"Rule": label, "Value": _fmt(value), "Benchmark": _fmt(threshold), "State": state})
    return result


def render() -> None:
    workflow_style()
    st.title("After earnings: find companies to research")
    st.caption("PEAD · Post-Earnings-Announcement Drift")
    st.write("Look for unusually strong company earnings, then check financial strength and price "
             "compared with book value. A match is a starting point for research.")
    _refresh_strip()
    overview, find, signals, past, calendar = st.tabs(
        ["Overview", "Find companies", "Saved signals", "Past performance", "Results calendar"],
        key="pead_section", on_change="rerun",
    )
    with overview:
        _overview()
    with find:
        _tab_screener()
    with signals:
        _tab_live_open()
    with past:
        _tab_backtest()
    with calendar:
        _tab_calendar_heatmap()


def _overview() -> None:
    st.subheader("Start here")
    st.write("Companies report how much they earned. Sometimes their share prices keep moving after "
             "those results. This strategy studies that pattern; it cannot predict the next price move.")
    for col, title, body in zip(st.columns(3),
        ["1 · Find a company", "2 · Understand its results", "3 · Review the evidence"],
        ["Explore saved company results. Adjust filters only when you understand what they measure.",
         "Choose a result to compare earnings with recent history and see why each rule passes or fails.",
         "Check the dates and missing information before making your own decision. This app does not place orders."]):
        with col, st.container(border=True):
            st.markdown(f"**{title}**")
            st.write(body)
    st.button("Find companies to review", type="primary", on_click=_go_find)
    ev = _read_frame(DATA / "events.parquet")
    st.subheader("What information is available?")
    if ev.empty:
        st.info("No earnings events saved. Use Update earnings data to request company results.")
    else:
        if "ticker" in ev:
            count = ev['ticker'].nunique()
            st.write(f"**{len(ev):,} company results** across **{count:,} {'company' if count == 1 else 'companies'}**.")
        else:
            st.write(f"**{len(ev):,} company results**; company identifiers are missing.")
        st.caption(f"Saved results: {_coverage(ev)}. One company may have several quarterly results.")
        st.caption("These are previously saved results, not a list confirmed for today.")
    section_help("How a company meets the strategy rules",
                 "The saved strategy uses three checks together. The exploratory filters on Find companies "
                 "are broader, so appearing in that list does not mean all three rules passed.")
    st.markdown("1. **Strong earnings:** in the highest of ten earnings-strength groups.\n"
                "2. **Financial strength:** at least 7 of 9 accounting checks passed.\n"
                "3. **Relative price:** price-to-book at or below the middle value for its industry.")
    _glossary_expander()


def _glossary_expander() -> None:
    with st.expander("A plain-English guide to the numbers"):
        st.markdown(
            "- **Profit per share (EPS):** company profit allocated to each share. Negative means a loss per share.\n"
            "- **Earnings strength (SUE):** how far the latest profit per share is above or below its "
            "previous-four-period average, allowing for how variable those earnings were. Zero means near "
            "the average; positive is above; negative is below. This is not percentage growth or a comparison with analyst forecasts.\n"
            "- **Financial strength (Piotroski):** how many of nine accounting checks passed. This strategy "
            "requires at least seven. A high score does not make a stock safe.\n"
            "- **Price / book value (P/B):** share price divided by accounting value per share. "
            "The strategy compares it with the middle value among industry peers. Lower alone does not mean a good investment.\n"
            "- **Earnings group (decile):** one of ten ranked groups; 10 is the strongest in the saved comparison set.\n"
            "- **Holding rule:** the model uses up to 60 trading days. The saved trade table reports elapsed calendar days, "
            "including weekends. A best holding period has not been established."
        )


def _refresh_strip() -> None:
    status_path = DATA / "last_run_status.json"
    cols = st.columns([3, 1])
    feedback = None
    # Run a requested update before reading its outcome, so the same render
    # cannot retain an earlier failure next to newly saved results.
    with cols[1]:
        if st.button("Update earnings data", width="stretch"):
            try:
                with st.spinner("Requesting company results…"):
                    proc = subprocess.run(
                        [sys.executable, "pead_downloader.py"],
                        capture_output=True, text=True, timeout=600, cwd=BASE,
                    )
                feedback = (proc.returncode != 0, proc.stdout[-2000:] or proc.stderr[-2000:] or "No details returned.")
            except (OSError, subprocess.TimeoutExpired) as exc:
                feedback = (True, str(exc))
    with cols[0]:
        if status_path.exists():
            try:
                s = json.loads(status_path.read_text())
                if not isinstance(s, dict):
                    raise ValueError("Expected a refresh status object")
            except (ValueError, OSError):
                s = {}
                st.warning("Saved refresh status is unreadable. The last update outcome is unknown.")
            if s.get("error"):
                st.warning("The last update failed. You can still explore previously saved results.")
                with st.expander("Why the update failed"):
                    st.write("The data provider could not supply an update. Your previously saved results are still available.")
                    st.code(str(s["error"]))
            if s:
                st.caption(f"Last update attempt: {s.get('run_date') or 'Date not recorded'}")
                if not s.get("error"):
                    counts = []
                    for key, label in [("rows_written", "company results saved"), ("qualified_long", "marked eligible")]:
                        if _number(s.get(key)) is not None:
                            counts.append(f"{s[key]} {label}")
                    st.caption(" · ".join(counts) if counts else "Update outcome and result counts were not recorded.")
        else:
            st.caption("No update history available. Saved results, if any, can still be explored.")
        if feedback:
            failed, details = feedback
            if failed:
                st.error("The update could not finish. Previously saved results remain available.")
            else:
                st.caption("Update process finished. Its saved outcome is shown above; process completion alone does not confirm new data.")
            with st.expander("Update details"):
                st.code(details)


def _tab_live_open() -> None:
    st.subheader("Candidates from a previous run")
    section_help("What this shows", "Companies the strategy previously marked for review. These are saved signals, "
                 "not recommendations confirmed today. Check the result dates and update status.")
    live = DATA / "live_signals.csv"
    if not live.exists():
        st.info("No saved candidates available. Use Update earnings data to request new results.")
    else:
        df = _read_frame(live)
        if df.empty:
            st.info("No saved candidates available. The feed is empty; this does not establish that no stocks qualify today.")
        else:
            st.caption(f"Result dates in this list: {_coverage(df)}")
            _show_table(
            df.reindex(columns=["ticker", "sector", "sue", "sue_decile", "eps_actual",
                "eps_expected", "piotroski", "pb", "pb_sector_median",
                "result_date", "period_type"]),
            )
        st.download_button(
            "Download CSV", df.to_csv(index=False), file_name="live_signals.csv"
        )

    st.subheader("Positions in the simulation")
    st.write("These are purchases held by the historical model. They are not purchases recorded in your brokerage account.")
    op = DATA / "open_positions.parquet"
    if not op.exists():
        st.info("No simulated open positions are saved.")
        return
    df = _read_frame(op)
    _show_table(df)


def _tab_backtest() -> None:
    st.subheader("What happened in past tests?")
    section_help("What this shows", "The rules applied to previously saved market data. This is a historical simulation, "
                 "not your account balance or a forecast. Costs and testing on unseen periods are not verified.")
    research_notice()
    eq_path = BASE / "pead_equity.csv"
    tr_path = BASE / "pead_trades.csv"
    kpi_path = BASE / "pead_kpis.csv"
    spread_path = BASE / "pead_decile_spread.csv"

    if not eq_path.exists():
        st.info("No historical test is saved yet. Company results can still be explored in Find companies.")
        return

    eq = _read_frame(eq_path)
    if eq.empty or not {"date", "equity"}.issubset(eq.columns):
        st.info("No usable simulated account history is saved.")
        return
    eq["date"] = pd.to_datetime(eq["date"], errors="coerce")
    st.markdown("**Simulated account value over time**")
    st.caption("Read left to right for time; the vertical axis is the saved account value. A falling line means the model lost value.")
    st.line_chart(eq.dropna(subset=["date"]).set_index("date")["equity"].rename("Simulated account value"))

    if kpi_path.exists():
        frame = _read_frame(kpi_path, index_col=0)
        if frame.empty or not len(frame.columns):
            st.info("No usable performance metrics saved.")
        else:
            kpis = frame.iloc[:, 0]
            for col, label, key, percent in zip(
                st.columns(4), ("Annualized growth", "Largest fall from a peak", "Return / variability", "Profitable trades"),
                ("cagr", "max_dd", "sharpe", "win_rate"), (True, True, False, True),
            ):
                value = _number(kpis.get(key))
                formatted = "Not recorded" if value is None else f"{value*100:.1f}%" if percent else f"{value:.2f}"
                col.metric(label, formatted)
    with st.expander("How to read the performance numbers"):
        st.markdown("- **Annualized growth (CAGR):** the steady yearly rate that would give the same start-to-end change.\n"
                    "- **Largest fall from a peak (max drawdown):** the biggest decline below an earlier high. Recovery is not guaranteed.\n"
                    "- **Return / variability (Sharpe):** return compared with how much returns fluctuate. Higher alone does not prove safety.\n"
                    "- **Profitable trades (win rate):** the share of completed simulated trades that made money. This is not the probability the next trade wins.")

    if spread_path.exists():
        st.subheader("Returns after results, by earnings-strength group")
        st.write("The horizontal axis groups earnings strength from 1 (lowest) to 10 (highest). "
                 "The bars show average saved returns over the following 60 trading days. Compare groups; "
                 "a higher earnings score does not guarantee a higher return.")
        spread = _read_frame(spread_path, index_col=0)
        if spread.empty or not len(spread.columns):
            st.info("No decile performance saved.")
        else:
            st.bar_chart(spread.iloc[:, 0].rename("Average return (%)").rename_axis("Earnings-strength group"))

    if tr_path.exists():
        st.subheader("Simulated trade history")
        st.caption("Entry is the model's purchase; exit is its sale. The saved duration counts calendar days, including weekends. "
                   "This differs from the strategy's 60-trading-day rule. Gain/loss measures the saved result.")
        trades = _read_frame(tr_path)
        st.caption(f"Saved sample: {len(trades):,} trades. Small samples can give misleading performance figures.")
        _show_table(trades)
    with st.expander("Holding-period research and calculation details"):
        st.write("The existing model holds for up to 60 trading days or exits before the next earnings result. "
                 "Whether that future result date was known at the time still needs validation. No best holding period is established.")
        rec_path = BASE / "exit_recommendations.json"
        try:
            rec = json.loads(rec_path.read_text()).get("pead", {}).get("ALL") if rec_path.exists() else None
        except (ValueError, OSError, AttributeError):
            rec = None
        if rec:
            st.caption("Exploratory saved output; not a validated recommendation for how long to hold.")
            st.json(rec, expanded=False)


def _tab_calendar_heatmap() -> None:
    st.subheader("Saved company result dates")
    st.write("Use these saved dates to see when companies report. Coverage and freshness depend on the saved source; "
             "this is not a confirmed calendar of upcoming announcements.")
    rd = DATA / "result_dates.parquet"
    if rd.exists():
        df = _read_frame(rd)
        _show_table(df)
    else:
        st.info("No result calendar is saved. You can still explore past reported results below.")

    st.subheader("Earnings strength by industry")
    st.write("Rows are industries; columns are calendar quarters when results were reported. Each number is the "
             "average earnings-strength score (SUE). Green means higher and red lower relative to recent earnings history, "
             "not better or worse investments. Blank cells mean no usable saved observations.")
    ev_path = DATA / "events.parquet"
    if not ev_path.exists():
        st.info("No events yet.")
        return
    ev = _read_frame(ev_path)
    if ev.empty or not {"result_date", "sector", "sue"}.issubset(ev.columns):
        st.info("No usable earnings history for the heatmap.")
        return
    st.caption("Grouped by announcement calendar quarter, not issuer fiscal quarter.")
    ev = ev.copy()
    ev["quarter"] = pd.to_datetime(ev["result_date"], errors="coerce").dt.to_period("Q")
    ev["sue"] = pd.to_numeric(ev["sue"], errors="coerce")
    ev = ev.dropna(subset=["quarter", "sector", "sue"])
    if ev.empty:
        st.info("No dated earnings history with numeric SUE for the heatmap.")
        return
    ev["quarter"] = ev["quarter"].astype(str)
    pivot = ev.pivot_table(
        index="sector", columns="quarter", values="sue", aggfunc="mean"
    )
    st.dataframe(
        pivot.rename_axis("Industry").style.format("{:.2f}", na_rep="Not recorded").background_gradient(cmap="RdYlGn", axis=None),
        width="stretch",
    )


def _tab_screener() -> None:
    st.subheader("Find companies to review")
    section_help("What this shows", "A list of saved company results matching your filters. One company can appear more than once. "
                 "Choose a result below to understand it; matching these filters is different from passing all three strategy rules.")
    ev = _read_frame(DATA / "events.parquet")
    required = {"ticker", "sector", "sue", "piotroski", "pb", "result_date"}
    if ev.empty:
        st.info("No earnings events saved. Refresh fundamentals to populate this screen.")
        return
    if not required.issubset(ev.columns):
        st.warning("Incomplete event file. Missing fields: " + ", ".join(sorted(required - set(ev.columns))))
        return
    ev = ev.copy()
    for col in ("sue", "piotroski", "pb"):
        ev[col] = pd.to_numeric(ev[col], errors="coerce")
    date_range = _coverage(ev)
    st.caption(f"Saved results: {date_range} | {len(ev):,} company results. The exact announcement time is not recorded.")
    with st.expander("Adjust filters · optional"):
        st.write("Use these controls to explore. Their starting values are broader than the strategy's eligibility rules.")
        c1, c2, c3, c4 = st.columns(4)
        sue_min = c1.slider("Minimum earnings strength (SUE)", -5.0, 5.0, -3.0, 0.1,
                            help="Above zero means profit per share is above its recent average. Not percentage growth.", key="pead_sue")
        pio_min = c2.slider("Minimum financial checks passed", 0, 9, 5, help="Piotroski: number of nine accounting checks passed. Strategy requires 7.", key="pead_pio")
        pb_max = c3.number_input("Maximum price / book value", value=10.0, help="P/B compares price with accounting value per share. Lower alone does not mean a good investment.", key="pead_pb")
        sectors = c4.multiselect("Industry", sorted(ev["sector"].dropna().unique().tolist()), key="pead_sectors")
    st.caption(f"Active filters: earnings strength ≥ {sue_min:g} · financial checks ≥ {pio_min}/9 · price/book ≤ {pb_max:g} · "
               + (", ".join(sectors) if sectors else "all industries"))
    df = ev[(ev["sue"] >= sue_min) & (ev["piotroski"] >= pio_min) & (ev["pb"] <= pb_max)]
    if sectors:
        df = df[df["sector"].isin(sectors)]
    c1, c2, c3 = st.columns(3)
    c1.metric("Matching company results", len(df))
    c2.metric("Results with missing inputs", int(ev[["sue", "piotroski", "pb"]].isna().any(axis=1).sum()),
              help="Across saved events; these rows cannot pass the current numeric filters.")
    c3.metric("Marked eligible in saved run", int(df["qualifies_long"].eq(True).sum()) if "qualifies_long" in df else "Not recorded",
              help="Stored qualification flag; not recomputed or validated point-in-time.")
    if df.empty:
        st.info("No events match these filters. Lower a threshold or clear the sector selection.")
        return
    df = df.sort_values(["result_date", "ticker"], ascending=[False, True]).reset_index(drop=True)
    display = df.reindex(columns=["ticker", "result_date", "period_type", "sector", "sue", "sue_decile", "piotroski", "pb", "pb_sector_median"])
    display["Why shown"] = f"SUE >= {sue_min:g}; Piotroski >= {pio_min}; P/B <= {pb_max:g}"
    _show_table(display)
    st.download_button("Export matching events", df.to_csv(index=False), file_name="pead_screener.csv")
    st.subheader("Understand a company's results")
    st.caption("Select a company and result date. The explanation below updates to match your selection.")
    selected = st.selectbox("Choose a company result", range(len(df)), key="pead_event",
        format_func=lambda i: f"{df.iloc[i]['ticker']} | {df.iloc[i]['result_date']} | {_period(df.iloc[i].get('period_type', 'Period not recorded'))}")
    _event_detail(df.iloc[selected])


def _event_detail(row) -> None:
    with st.container(border=True):
        st.subheader(str(row.get("ticker", "Stock")))
        st.caption(f"Result date: {row.get('result_date', 'Not recorded')} | {_period(row.get('period_type', 'Period not recorded'))} | Saved evidence")
        checks = qualification_checks(row)
        counts = {state: sum(c["State"] == state for c in checks) for state in ("Pass", "Fail", "Missing")}
        actual, expected = _number(row.get("eps_actual")), _number(row.get("eps_expected"))
        if actual is not None and expected is not None:
            comparison = "above" if actual > expected else "below" if actual < expected else "equal to"
            st.write(f"Profit per share was **{actual:,.2f}**, {comparison} the previous-four-period average of **{expected:,.2f}**.")
        else:
            st.info("The latest profit per share or its previous-four average is missing, so that comparison is unavailable.")
        st.write(f"**Meets {counts['Pass']} of 3 displayed rules** · {counts['Fail']} do not meet the rule · {counts['Missing']} have missing information.")
        st.markdown("**Why each rule passes or fails**")
        names = ["Strong earnings", "Financial strength", "Price compared with industry"]
        explanations = ["Requires the highest earnings group: 10 out of 10.",
                        "Requires at least 7 of 9 accounting checks to pass.",
                        "Requires price/book at or below the industry's middle value."]
        states = {"Pass": "Meets rule", "Fail": "Does not meet rule", "Missing": "Information missing"}
        for check, name, explanation in zip(checks, names, explanations):
            with st.container(border=True):
                st.markdown(f"**{name} — {states[check['State']]}**")
                st.write(f"{explanation} Saved value: **{check['Value']}**. Comparison value: **{check['Benchmark']}**.")
        st.caption("These checks explain saved values. A past match does not confirm eligibility today; the saved eligibility flag is separate.")
        st.markdown("**Profit per share compared with recent history**")
        st.caption("Profit per share (EPS) allocates company profit to each share. Negative means a loss. Earnings strength is a score, not percentage growth.")
        cols = st.columns(3)
        for col, label, key in zip(cols, ("Latest profit per share", "Previous-four average", "Earnings strength (SUE)"), ("eps_actual", "eps_expected", "sue")):
            col.metric(label, _fmt(row.get(key)))
        history = row.get("eps_history")
        if isinstance(history, (list, tuple)) or hasattr(history, "tolist"):
            values = list(history)
            with st.expander("See the previous earnings and calculation"):
                st.dataframe(pd.DataFrame({"Prior period (newest first)": range(1, len(values)+1), "Profit per share": values}), hide_index=True, width="stretch")
                st.write("The score subtracts the previous-four average from the latest profit per share, then divides by the sample standard deviation "
                         "(how much those four values varied). The reference spreadsheet uses a different standard deviation convention.")
            clean = [_number(v) for v in values]
            if len(clean) == 4 and all(v is not None for v in clean):
                with st.expander("Exact formula values"):
                    st.caption(f"Sample standard deviation: {statistics.stdev(clean):.4f}. Formula: (latest EPS - previous-four mean) / sample SD.")
        else:
            st.info("The four prior EPS inputs were not saved for this event.")
        st.caption("Missing context: exact fiscal-quarter names, announcement time, and whether figures cover only the company or its wider group. "
                   "We cannot establish the earliest valid purchase time from this record.")
        st.markdown("**Extra checks from Trendlyne**")
        st.info("No dated Trendlyne scores or checklist answers are saved for this result. Missing information is not a failed check.")
        with st.expander("What the Trendlyne scores and 23 checks mean"):
            st.write("Durability describes financial strength; Valuation assesses price; Momentum describes recent price strength. "
                     "Scores range from 0 to 100. No score is available here.")
            rows = []
            for group, labels in TRENDLYNE_CHECKS.items():
                start = len(rows)
                rows.extend({"#": start+i+1, "Group": group, "Check": label, "State": "Not recorded"} for i, label in enumerate(labels))
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
            st.caption("Checklist labels come from the local reference screenshots. Screenshot pass/fail values are not evidence for this event.")
        with st.expander("All saved event fields"):
            st.dataframe(pd.DataFrame({"Field": row.index, "Saved value": [str(v) for v in row.values]}), hide_index=True, width="stretch")
        st.markdown("**What to review next**")
        st.write("Check that the earnings are current, investigate missing information and review the risks before deciding. "
                 "Passing these checks does not predict a profit.")
        st.caption("No purchase or review decision is saved here. Stocks to review (Suggestions) uses separate strategies and does not include PEAD.")
