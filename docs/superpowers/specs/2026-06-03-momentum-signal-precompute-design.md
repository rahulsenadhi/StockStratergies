# Momentum Signal Precompute — Design

**Date:** 2026-06-03
**Problem:** Master dashboard (`:8500`) never finishes first render — stuck on Streamlit skeleton, "no data shown".

## Root cause (measured)

`main()` eagerly calls `load_monthly()` + `load_ipo()` + `load_momentum()` on **every** page load, inside a spinner, before rendering any page.

| Loader | Time |
|---|---|
| `load_monthly` | 0.1s |
| `load_ipo` | 0.4s |
| **`load_momentum`** | **52.5s** |

`load_momentum` runs two full-universe scans: `_compute_momentum_signals()` (~15.7s) + `_scan_recent_breakouts()` (~36s). With `@st.cache_data(ttl=3600)`, this recomputes hourly. Streamlit aborts the script when the browser disconnects before the 52s finishes → result never caches → permanent skeleton for any visitor who doesn't wait ~1 min.

## Decision

**Precompute momentum live-signals during the pipeline; dashboard only reads them.** (User-approved "proper fix".)

Reuse the dashboard's existing compute functions verbatim (no code move — they are spec-aligned and intricate) to guarantee byte-identical render output.

## Components

### 1. `precompute_momentum_signals.py` (new)
- Stub `streamlit` (cache decorators → passthrough; `set_page_config`/`markdown` → no-op) so `master_dashboard` imports without a Streamlit runtime.
- Import `master_dashboard` as `md`.
- Call `md._compute_momentum_signals()` → `(signals_df, funnel_dict)` and `md._scan_recent_breakouts()` → `breakouts_df`.
- Persist:
  - `momentum_edge_signals.csv` — signals_df
  - `momentum_edge_funnel.json` — funnel dict
  - `momentum_edge_recent_breakouts.csv` — breakouts_df
- Print a one-line summary (counts).

### 2. `master_dashboard.py::load_momentum` (edit, ~10 lines)
- New helper `_read_precomputed_momentum()` reads the 3 files.
- `load_momentum`: if precomputed signals file exists and is non-empty → use precomputed `signals` + `funnel` + `recent_breakouts` (skip the 52s compute). Else → fall back to current live compute (unchanged behavior). Equity/trades CSV reads stay as-is.
- No other dashboard logic changes; render code consumes the same `out` dict shape.

### 3. Pipeline + docs
- Add `python precompute_momentum_signals.py` after `momentum_edge_backtest.py` in `HOW_TO_RUN.md` "Run Everything" block.
- (Pipeline runner is the manual block in HOW_TO_RUN.md; no separate orchestrator file.)

### 4. Cleanup
- Kill the `:3000` Next landing process (user: "no use"). Leave `frontend/` files in place (no deletion without request).

## Data flow

```
momentum_edge_backtest.py  →  data/indicator_cache/*.parquet (+ equity/trades csv)
precompute_momentum_signals.py  →  momentum_edge_signals.csv / _funnel.json / _recent_breakouts.csv
master_dashboard.load_momentum  →  reads those (≈0.1s)  →  render
                                   (fallback: live compute if files absent)
```

## Error handling
- Precompute reads/writes wrapped; on failure leaves old CSVs (dashboard fallback still works).
- `load_momentum` fallback preserves the original 52s path so a missing/corrupt precompute never breaks the page — only makes it slow.

## Testing / verification
- Run precompute → confirm 3 output files non-empty.
- Restart `:8500` → headless Chrome screenshot after warm-up → confirm content (KPIs/tables) renders, not skeleton.
- Confirm `load_momentum` returns in <1s via the standalone timer harness.

## Out of scope
- No restyle: the fintech theme already exists and renders once the page paints.
- No move/refactor of the compute functions.
- No change to monthly/IPO/PEAD loaders (already fast).
