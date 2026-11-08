import { createElement as h } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { MomentumDesk } from "@/components/desk/momentum/momentum-desk";
import { EMPTY_NO_SIGNALS, RAIL_PLACEHOLDER, type Health, type UiMomentum } from "@/lib/desk/momentum-text";

const health: Health = {
  n_trades: 0, win_rate: 0, avg_pnl: 0, median_pnl: 0, median_hold: 0, safe_20d_pct: 0,
  universe: "u", verdict_text: "v", top_lift: "t", best_combo: "b", verdict_tone: "muted",
};
const view = { health, counts: { breakout: 0, near: 0, watch: 0, ath: 0, clean: 0, fast: 0 }, signal_ids: [], trade_ids: [] };
const EMPTY: UiMomentum = {
  version: 1, generated_at: "2026-11-08T00:00:00", colour: "#7c9cff", summary: null, chart: null,
  views: { all: view, ath: view }, signals: [], tabs: { All: [], "BUY NOW": [], WATCH: [], FORMING: [] }, recent: [],
  funnel: null, details: {}, trades: [], trade_filters: { periods: {}, years: [], strict: [] }, exit_rec: null,
};

describe("MomentumDesk with nothing saved", () => {
  const html = renderToStaticMarkup(h(MomentumDesk, { data: EMPTY, ticker: undefined }));
  it("shows the three empty states", () => {
    expect(html).toContain(EMPTY_NO_SIGNALS.title);
    expect(html).toContain(RAIL_PLACEHOLDER.title);
    expect(html).toContain("No momentum simulation is saved");
  });
  it("leaks no NaN, null or undefined into the visible text", () => {
    const text = html.replace(/<[^>]*>/g, " ");
    expect(text).not.toMatch(/NaN|null|undefined/);
  });
});
