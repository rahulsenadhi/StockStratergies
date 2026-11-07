import { describe, expect, test } from "vitest";
import { NAV, navHref, STREAMLIT_URL, strategyPageHref } from "@/lib/desk/nav";
import { formatPlain } from "@/lib/desk/format";

describe("desk nav", () => {
  test("labels, groups and order are verbatim from Streamlit", () => {
    expect(NAV.map((g) => [g.group, g.items.map((i) => i.label)])).toEqual([
      ["", ["Home"]],
      ["STRATEGIES", ["Browse strategies", "Create a strategy"]],
      ["FIND STOCKS", ["Monthly stock rotation", "Newly listed stocks (IPO)", "Price strength (Momentum)",
        "After earnings (PEAD)", "Stocks to review"]],
      ["EVALUATE", ["Understand past trades", "Compare past results"]],
    ]);
  });

  test("Home is built; unbuilt pages open the Streamlit app", () => {
    expect(STREAMLIT_URL).toBe("http://localhost:8500");
    expect(navHref(NAV[0].items[0])).toEqual({ href: "/", external: false });
    expect(navHref(NAV[1].items[0])).toEqual({ href: STREAMLIT_URL, external: true });
  });

  test("candidate and strategy rows map to their strategy page, falling back to Streamlit", () => {
    for (const key of ["Monthly", "IPO", "Momentum", "PEAD", "monthly_rotation", "ipo_edge", "momentum_edge", "pead"]) {
      expect(strategyPageHref(key, "BAJFINANCE")).toEqual({ href: STREAMLIT_URL, external: true });
    }
    expect(strategyPageHref("unknown_custom_id")).toEqual({ href: STREAMLIT_URL, external: true });
  });
});

describe("formatPlain", () => {
  test("matches Python '{:,}' for 2-decimal floats", () => {
    expect(formatPlain(25030.35)).toBe("25,030.35");
    expect(formatPlain(23264.1)).toBe("23,264.1");
    expect(formatPlain(24000)).toBe("24,000");
  });
});
