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

describe("axis formatters", () => {
  it("abbreviates large volume values Indian style", async () => {
    const { abbreviateIndian, priceAxisText } = await import("@/lib/desk/format");
    expect(abbreviateIndian(200000000)).toBe("20.0 Cr");
    expect(abbreviateIndian(20000000)).toBe("2.0 Cr");
    expect(abbreviateIndian(4530000)).toBe("45.3 L");
    expect(abbreviateIndian(12500)).toBe("12.5 K");
    expect(abbreviateIndian(-4530000)).toBe("-45.3 L");
    expect(abbreviateIndian(55.123)).toBe("55.12");
    expect(priceAxisText(2450.6)).toBe("₹2451");
    expect(priceAxisText(99.5)).toBe("₹99.50");
  });
});
