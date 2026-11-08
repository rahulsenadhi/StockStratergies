"""Print the strings Streamlit's Monthly page builds from the current saved files, as JSON.

Run with cwd = project root. The Next.js parity test compares these with its own mappers.
Gap named on purpose: the benchmark return and CAGR are computed inline inside
render_monthly (no function to call), so the formula is copied here from there.
"""
import html
import json
import logging
import os
import sys
import re

sys.path.insert(0, os.getcwd())  # run with cwd = project root
logging.disable(logging.WARNING)

import master_dashboard as md  # noqa: E402
from core import ui_components as ui  # noqa: E402

TAG = re.compile(r"<[^>]+>")


def strip(markup: str) -> str:
    return html.unescape(TAG.sub("", markup))


def bar(markup: str) -> list:
    m = re.search(r'rd-bar--(\w+)"><span>(.*?)</span><span class="rd-bar__val">(.*?)</span>', markup)
    return [html.unescape(m.group(2)), html.unescape(m.group(3)), m.group(1)]


def big(markup: str) -> dict:
    m = re.match(r'<span[^>]*>([^<]*)(?:<span[^>]*>([^<]*)</span>)?</span>', markup)
    return {"head": html.unescape(m.group(1)), "dec": html.unescape(m.group(2)) if m.group(2) else None}


def summary(m: dict) -> dict:
    eq, reb = m.get("equity"), m.get("rebalance")
    if eq is None:
        return {}
    mx = md._equity_metrics(eq, "Portfolio_Value", "Portfolio_Value")
    b_ret = b_cagr = 0.0
    if "Benchmark_Value" in eq.columns:  # inline formula copied from render_monthly
        bv = eq["Benchmark_Value"].dropna()
        b_ret = (bv.iloc[-1] / bv.iloc[0] - 1) * 100
        b_yrs = (bv.index[-1] - bv.index[0]).days / 365.25
        b_cagr = ((bv.iloc[-1] / bv.iloc[0]) ** (1 / max(b_yrs, 0.01)) - 1) * 100
    n_months = len(reb) if reb is not None and not reb.empty else None
    alpha = mx["cagr"] - b_cagr if mx else 0
    bars = (ui.stat_bar("Extra vs Nifty", f"{alpha:+.1f}% / yr", "gain" if alpha >= 0 else "loss")
            + ui.stat_bar("Total return", f"{mx['total_ret']:+.1f}%" if mx else "—", "info")
            + ui.stat_bar("Nifty total", f"{b_ret:+.1f}%", "muted")
            + ui.stat_bar("Worst fall from a peak", f"{mx['max_dd']:.1f}%" if mx else "—", "loss")
            + ui.stat_bar("Sample", f"{n_months} monthly rebalances" if n_months else "—", "muted"))
    return {
        "big": big(ui.big_value(f"{mx['cagr']:+.1f}%" if mx else "—", tone="gain" if mx and mx["cagr"] >= 0 else "loss")),
        "sub": f"vs Nifty {b_cagr:+.1f}% per year, same period",
        "bars": [bar(b) for b in re.findall(r'<div class="rd-bar.*?</div>', bars)],
    }


def ranking(ranks) -> list:
    out = []
    for _, r in ranks.sort_values("Rank", kind="stable").iterrows():
        rank = int(r["Rank"])
        out.append([
            f"{rank}", r["Company"],
            str(r["Ticker"]).replace(".NS", "") + (" · top 5 candidate" if rank <= 5 else ""),
            f"₹{r['Current_Price']:,.2f}", strip(ui.change_pill(float(r["Return_%"]))),
            f"{r['RS_Score']:+.2f}%", md._monthly_label(r["Signal"]),
        ])
    return out


def rebalances(reb) -> list:
    if reb is None or reb.empty:
        return []
    return [[str(r["Date"])[:10], md._monthly_tickers(r["Top5_Stocks"]), md._monthly_tickers(r["Stocks_Bought"]),
             md._monthly_tickers(r["Stocks_Sold"]), f"₹{r['Portfolio_Value']:,.0f}"]
            for _, r in reb.tail(12).iloc[::-1].iterrows()]


if __name__ == "__main__":
    data = md.load_monthly()
    print(json.dumps({"summary": summary(data), "ranking": ranking(data["rankings"]),
                      "rebalances": rebalances(data.get("rebalance"))}, ensure_ascii=False))
