import { describe, it, expect } from "vitest";
import { computePositionSizing } from "@/lib/position-sizing";

describe("computePositionSizing", () => {
  it("computes shares so a stop-out loses exactly the risk budget (floored)", () => {
    // capital 500k, risk 2% -> budget 10k; entry 1000, stop 10% -> risk/share 100
    const r = computePositionSizing({ capital: 500_000, riskPct: 2, entry: 1000, stopPct: 10 });
    expect(r.stopPrice).toBe(900);
    expect(r.riskPerShare).toBe(100);
    expect(r.riskBudget).toBe(10_000);
    expect(r.shares).toBe(100); // floor(10000/100)
    expect(r.positionSize).toBe(100_000);
    expect(r.positionPct).toBeCloseTo(20);
    expect(r.maxLoss).toBe(10_000); // never exceeds budget
  });

  it("floors fractional shares (max loss stays under budget)", () => {
    // budget 10k, risk/share 150 -> 66.6 -> 66 shares
    const r = computePositionSizing({ capital: 500_000, riskPct: 2, entry: 1000, stopPct: 15 });
    expect(r.shares).toBe(66);
    expect(r.maxLoss).toBeLessThanOrEqual(r.riskBudget);
    expect(r.maxLoss).toBeCloseTo(66 * 150);
  });

  it("computes 2:1 and 3:1 targets from the stop distance", () => {
    const r = computePositionSizing({ capital: 100_000, riskPct: 1, entry: 200, stopPct: 5 });
    expect(r.target2R).toBeCloseTo(200 * 1.1); // +10%
    expect(r.target3R).toBeCloseTo(200 * 1.15); // +15%
  });

  it("returns zero shares when risk/share is non-positive (entry <= stop)", () => {
    const r = computePositionSizing({ capital: 100_000, riskPct: 2, entry: 100, stopPct: 0 });
    expect(r.riskPerShare).toBe(0);
    expect(r.shares).toBe(0);
    expect(r.positionSize).toBe(0);
    expect(r.maxLoss).toBe(0);
  });

  it("guards divide-by-zero capital for positionPct", () => {
    const r = computePositionSizing({ capital: 0, riskPct: 2, entry: 1000, stopPct: 10 });
    expect(r.positionPct).toBe(0);
    expect(r.shares).toBe(0); // budget 0
  });
});
