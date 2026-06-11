import { describe, it, expect } from "vitest";
import path from "node:path";
import os from "node:os";
import { promises as fsp } from "node:fs";
import { getExitPlaybook } from "@/lib/data/strategies";

async function seed(): Promise<string> {
  const dir = await fsp.mkdtemp(path.join(os.tmpdir(), "exit-"));
  await fsp.writeFile(path.join(dir, "exit_recommendations.json"), JSON.stringify({
    momentum_edge: { ALL: {
      strategy: "momentum_edge", bucket: "ALL", hold_days: 79,
      hold_median_return: 57.17, hold_win_rate: 0.94,
      targets: [{ pct: 41.6, book_pct: 40, hit_rate: 0.59 }, { pct: 75.5, book_pct: 35, hit_rate: 0.34 }, { pct: 161.7, book_pct: 25, hit_rate: 0.16 }],
      stop_pct: -8.4, sample_size: 32, data_quality: "ohlcv",
      curve: [{ day: 1, median: 2.1 }, { day: 2, median: 3.4 }],
    } },
  }));
  return dir;
}

describe("getExitPlaybook", () => {
  it("returns the ALL bucket recommendation, camelCased", async () => {
    const dir = await seed();
    const r = await getExitPlaybook("momentum_edge", dir);
    expect(r).not.toBeNull();
    expect(r!.holdDays).toBe(79);
    expect(r!.holdWinRate).toBeCloseTo(0.94);
    expect(r!.targets).toHaveLength(3);
    expect(r!.targets[0]).toEqual({ pct: 41.6, bookPct: 40, hitRate: 0.59 });
    expect(r!.stopPct).toBeCloseTo(-8.4);
    expect(r!.sampleSize).toBe(32);
    expect(r!.dataQuality).toBe("ohlcv");
    expect(r!.curve.map((c) => c.median)).toEqual([2.1, 3.4]);
  });
  it("returns null for an unknown strategy", async () => {
    const dir = await seed();
    expect(await getExitPlaybook("nope", dir)).toBeNull();
  });
  it("returns null when the file is missing", async () => {
    const dir = await fsp.mkdtemp(path.join(os.tmpdir(), "exit-empty-"));
    expect(await getExitPlaybook("momentum_edge", dir)).toBeNull();
  });
});
