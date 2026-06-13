import { describe, it, expect } from "vitest";
import path from "node:path";
import os from "node:os";
import { promises as fsp } from "node:fs";
import { getSuggestions } from "@/lib/data/strategies";

const FEED = {
  regime: {
    status: "Bear",
    barsSinceFlip: 65,
    close: 265.6,
    sma50: 268.62,
    sma200: 282.28,
    high52: 297.55,
    pctFromHigh: -10.74,
    date: "2026-06-04",
  },
  summary: { picks: 2, avgConfidence: 44.5, totalAllocation: 18, cashReserve: 82 },
  picks: [
    {
      rank: 1,
      ticker: "ZYDUSWELL",
      company: "Zydus Wellness",
      strategy: "Momentum Edge",
      strategyId: "momentum_edge",
      signal: "Watch Zone",
      close: 509.15,
      stop: 446.97,
      target: 636.44,
      rr: 2.05,
      confidence: 28.9,
      avgPnl: 11.89,
      nHist: 38,
      positionPct: 6,
      edgeScore: 81.4,
      rationale: "Entry: 52W_HIGH_FALLBACK - Recovery: Fast.",
    },
    {
      rank: 2,
      ticker: "ZEEL",
      company: "Zee",
      strategy: "Monthly Rotation",
      strategyId: "monthly_rotation",
      signal: "Strong BUY",
      close: 100,
      stop: 92,
      target: 110,
      rr: 2.25,
      confidence: 60,
      avgPnl: 1.8,
      nHist: 700,
      positionPct: 10,
      edgeScore: 73,
      rationale: "Top-1 RS pick.",
    },
  ],
};

async function seed(feed: unknown = FEED): Promise<string> {
  const dir = await fsp.mkdtemp(path.join(os.tmpdir(), "sugg-"));
  await fsp.writeFile(path.join(dir, "suggestions.json"), JSON.stringify(feed));
  return dir;
}

describe("getSuggestions", () => {
  it("reads the feed with regime, summary, and ranked picks", async () => {
    const dir = await seed();
    const feed = await getSuggestions(dir);
    expect(feed).not.toBeNull();
    expect(feed!.regime.status).toBe("Bear");
    expect(feed!.summary.picks).toBe(2);
    expect(feed!.picks).toHaveLength(2);
    expect(feed!.picks[0].ticker).toBe("ZYDUSWELL");
    expect(feed!.picks[0].strategyId).toBe("momentum_edge");
    expect(feed!.picks[0].rr).toBeCloseTo(2.05);
  });

  it("returns null when the file is missing", async () => {
    const dir = await fsp.mkdtemp(path.join(os.tmpdir(), "sugg-empty-"));
    expect(await getSuggestions(dir)).toBeNull();
  });

  it("returns null on malformed JSON (no picks array)", async () => {
    const dir = await seed({ regime: { status: "Bull" }, summary: {} });
    expect(await getSuggestions(dir)).toBeNull();
  });

  it("returns null on non-object root", async () => {
    const dir = await seed([1, 2, 3]);
    expect(await getSuggestions(dir)).toBeNull();
  });
});
