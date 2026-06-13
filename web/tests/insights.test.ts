import { describe, it, expect } from "vitest";
import path from "node:path";
import os from "node:os";
import { promises as fsp } from "node:fs";
import { getInsights } from "@/lib/data/strategies";

const REPORT = {
  momentum_edge: {
    overall: { n: 136, winRate: 31.6, avgPnl: 4.2, medianPnl: -1.1 },
    byEntryType: [{ group: "ATH", count: 80, winRate: 35, avgPnl: 6, medianPnl: 0 }],
  },
  ipo_edge: { overall: { n: 71, winRate: 56.3, avgPnl: 8, medianPnl: 3 } },
};

async function seed(data: unknown = REPORT): Promise<string> {
  const dir = await fsp.mkdtemp(path.join(os.tmpdir(), "insights-"));
  await fsp.writeFile(path.join(dir, "insights.json"), JSON.stringify(data));
  return dir;
}

describe("getInsights", () => {
  it("reads the per-strategy report", async () => {
    const dir = await seed();
    const r = await getInsights(dir);
    expect(r).not.toBeNull();
    expect(r!.momentum_edge.overall!.n).toBe(136);
    expect(r!.momentum_edge.byEntryType![0].group).toBe("ATH");
    expect(r!.ipo_edge.overall!.winRate).toBe(56.3);
  });

  it("returns null when missing", async () => {
    const dir = await fsp.mkdtemp(path.join(os.tmpdir(), "insights-empty-"));
    expect(await getInsights(dir)).toBeNull();
  });

  it("returns null on array root", async () => {
    const dir = await seed([1, 2]);
    expect(await getInsights(dir)).toBeNull();
  });
});
