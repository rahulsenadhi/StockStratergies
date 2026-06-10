import { describe, it, expect } from "vitest";
import { deriveStrategyId, summarizeExits } from "@/lib/data/strategies";

describe("deriveStrategyId", () => {
  it("lowercases and replaces spaces/hyphens with underscore", () => {
    expect(deriveStrategyId("My Cool Strat")).toBe("my_cool_strat");
    expect(deriveStrategyId("RSI-Breakout")).toBe("rsi_breakout");
  });
  it("trims surrounding whitespace", () => {
    expect(deriveStrategyId("  Edge  ")).toBe("edge");
  });
  it("leaves an all-symbol name as something the route regex will reject", () => {
    expect(/^[a-z0-9_]+$/.test(deriveStrategyId("@@@"))).toBe(false);
    expect(/^[a-z0-9_]+$/.test(deriveStrategyId("Good Name 2"))).toBe(true);
  });
});

describe("summarizeExits", () => {
  it("joins enabled exits", () => {
    expect(
      summarizeExits({
        time_enabled: true, time_days: 30,
        hard_stop_enabled: true, hard_stop_pct: 8,
        trail_enabled: true, trail_pct: 12,
      }),
    ).toBe("hold 30d · hard stop 8% · trail 12%");
  });
  it("omits disabled exits", () => {
    expect(
      summarizeExits({ time_enabled: true, time_days: 60, hard_stop_enabled: false, trail_enabled: false }),
    ).toBe("hold 60d");
  });
  it("returns em dash when none enabled", () => {
    expect(summarizeExits({})).toBe("—");
  });
});
