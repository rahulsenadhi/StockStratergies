import { createElement as h } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { IndicatorChartView, type ChartState } from "@/components/desk/momentum/indicator-chart";
import { CHART_EMPTY } from "@/lib/desk/momentum-chart-map";

const noop = () => {};
const render = (state: ChartState) =>
  renderToStaticMarkup(h(IndicatorChartView, {
    state, period: "1Y", onPeriod: noop, toggles: { bb: true, rsi: true, macd: true, vol: true }, onToggle: noop,
  }));

describe("IndicatorChartView", () => {
  it("shows the empty state for a missing file", () => {
    const html = render({ status: "empty", reason: null });
    expect(html).toContain(CHART_EMPTY.title);
    expect(html).not.toContain("aria-label=\"Price chart");
  });
  it("tells the user to run a data update when the saved file is unusable", () => {
    expect(render({ status: "empty", reason: null })).toContain(CHART_EMPTY.reason);
  });
  it("shows the saved note as the reason", () => {
    expect(render({ status: "empty", reason: "Too few bars" })).toContain("Too few bars");
  });
  it("shows an error message when the fetch failed", () => {
    expect(render({ status: "error" })).toContain("could not be loaded");
  });
  it("leaks no NaN, null or undefined", () => {
    const text = render({ status: "empty", reason: null }).replace(/<[^>]*>/g, " ");
    expect(text).not.toMatch(/NaN|null|undefined/);
  });
});
