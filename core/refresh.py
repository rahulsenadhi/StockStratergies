# core/refresh.py
"""Per-strategy incremental refresh orchestration (S0b).

refresh_strategy(name): fetch gaps -> sync Parquet store (S0a) -> run precompute.
Designed to be driven from a dashboard "Update now" button or the CLI.
"""
from __future__ import annotations

import datetime as dt
import subprocess
import sys
from pathlib import Path

from core import incremental

PY = sys.executable
_REPO_ROOT = Path(__file__).resolve().parent.parent


def _universe_from_folder(folder: str):
    """All ticker CSVs in a folder, excluding benchmark (^) files."""
    return [p.stem for p in Path(folder).glob("*.csv") if not p.name.startswith("^")]


STRATEGY_CFG: dict[str, dict] = {
    "nifty50": {
        "folder": "data",
        "dataset": None,                         # Nifty-50 stays CSV (per S0a deferral)
        "tickers_fn": lambda: _universe_from_folder("data"),
        "precompute": [],
    },
    "momentum": {
        "folder": "momentum_edge_data",
        "dataset": "momentum_edge_data",
        "tickers_fn": lambda: _universe_from_folder("momentum_edge_data"),
        "precompute": ["precompute_momentum_signals.py", "precompute_exit_recommendations.py"],
    },
    "ipo": {
        "folder": "ipo_data",
        "dataset": "ipo_data",
        "tickers_fn": lambda: _universe_from_folder("ipo_data"),
        "precompute": [],
    },
    "nse_bse": {
        "folder": "data/nse_bse",
        "dataset": "nse_bse",
        "tickers_fn": lambda: _universe_from_folder("data/nse_bse"),
        "precompute": [],
    },
}


def refresh_strategy(name: str, st_status=None) -> dict[str, str]:
    """Run gap fetch + Parquet sync + precompute for one strategy. Returns status map.

    `st_status` (optional Streamlit st.status handle) receives progress lines.
    """
    cfg = STRATEGY_CFG[name]   # KeyError on unknown name is intentional

    def log(msg: str):
        if st_status is not None:
            st_status.write(msg)

    tickers = cfg["tickers_fn"]()
    log(f"Fetching gaps for {len(tickers)} tickers…")
    status = incremental.refresh_tickers(
        tickers, cfg["folder"], dt.date.today(), incremental.yf_fetch)

    updated = sum(1 for v in status.values() if v.startswith(("gap_appended", "full")))
    skipped = sum(1 for v in status.values() if v == "skipped")
    failed = sum(1 for v in status.values() if v.startswith("failed"))
    log(f"{updated} updated · {skipped} already current · {failed} failed.")

    if failed and updated == 0 and skipped == 0:
        raise RuntimeError(f"All {failed} tickers failed — likely network/Yahoo. Data unchanged.")

    if cfg.get("dataset"):
        log("Syncing Parquet store…")
        subprocess.run([PY, str(_REPO_ROOT / "convert_to_parquet.py"), "--sync", cfg["dataset"]], check=True)

    for script in cfg.get("precompute", []):
        log(f"Precomputing ({script})…")
        subprocess.run([PY, str(_REPO_ROOT / script)], check=True)

    return status
