import { describe, expect, test } from "vitest";
import { formatChange, formatNumber, freshnessLabel, freshnessTone } from "@/lib/desk/format";

// Values must match core/ui_components.py change_pill / freshness_label / freshness_tone.
describe("desk format", () => {
  test("formatChange copies Python change_pill", () => {
    expect(formatChange(15.828988)).toEqual({ text: "↗ 15.83%", direction: "up" });
    expect(formatChange(-4.93)).toEqual({ text: "↘ 4.93%", direction: "down" });
    expect(formatChange(0)).toEqual({ text: "0.00%", direction: "flat" });
    expect(formatChange(null)).toEqual({ text: "—", direction: "flat" });
    expect(formatChange(Number.NaN)).toEqual({ text: "—", direction: "flat" });
    expect(formatChange(72.94, 1).text).toBe("↗ 72.9%");
  });

  test("freshness label and tone copy Python", () => {
    expect([null, 0, 1, 7, 8, 21, 22].map(freshnessLabel)).toEqual([
      "no saved file", "updated today", "1 day old", "7 days old", "8 days old", "21 days old", "22 days old",
    ]);
    expect([null, 0, 7, 8, 21, 22].map(freshnessTone)).toEqual(["muted", "gain", "gain", "warn", "warn", "loss"]);
  });

  test("formatNumber matches Python {:,.2f}", () => {
    expect(formatNumber(25030.35)).toBe("25,030.35");
    expect(formatNumber(1234.5, 1)).toBe("1,234.5");
  });
});
