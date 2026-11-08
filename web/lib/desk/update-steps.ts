/**
 * Update steps per strategy — the same list Streamlit's _run_refresh_steps runs:
 * master_dashboard._PIPELINES[k] followed by _PRECOMPUTE_FOR[k] as single steps.
 * tests/desk-update.test.ts checks this copy against Python (parity test).
 * Script names come only from here, never from a request.
 */
export const UPDATE_STRATEGIES = ["Monthly", "IPO", "Momentum", "PEAD"] as const;
export type UpdateStrategy = (typeof UPDATE_STRATEGIES)[number];

export const UPDATE_STEPS: Record<UpdateStrategy, string[][]> = {
  Monthly: [
    ["step1_download_data.py"],
    ["step2_backtest_momentum.py"],
    ["step3_dashboard.py"],
    ["precompute_suggestions.py"],
    ["precompute_insights.py"],
    ["precompute_ui_home.py"],
    ["precompute_ui_monthly.py"],
  ],
  IPO: [
    ["ipo_edge_downloader.py"],
    ["convert_to_parquet.py", "--sync", "ipo_data"],
    ["ipo_edge_backtest.py"],
    ["precompute_exit_recommendations.py"],
    ["precompute_suggestions.py"],
    ["precompute_insights.py"],
    ["precompute_ui_home.py"],
    ["precompute_ui_monthly.py"],
    ["precompute_ui_momentum.py"],
    ["precompute_ui_ipo.py"],
  ],
  Momentum: [
    ["build_universe.py"],
    ["nse_bse_downloader.py"],
    ["convert_to_parquet.py", "--sync", "nse_bse"],
    ["momentum_edge_backtest.py"],
    ["precompute_momentum_signals.py"],
    ["precompute_exit_recommendations.py"],
    ["precompute_suggestions.py"],
    ["precompute_insights.py"],
    ["precompute_ui_home.py"],
    ["precompute_ui_monthly.py"],
    ["precompute_ui_momentum.py"],
    ["precompute_ui_ipo.py"],
    ["precompute_ui_momentum_charts.py"],
  ],
  PEAD: [
    ["pead_downloader.py"],
    ["precompute_pead_screener.py"],
    ["precompute_insights.py"],
    ["precompute_ui_home.py"],
  ],
};
