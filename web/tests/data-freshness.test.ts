import { describe, it, expect } from "vitest";
import path from "node:path";
import os from "node:os";
import { promises as fsp } from "node:fs";
import { getDataFreshness, freshnessTier } from "@/lib/data/strategies";

describe("freshnessTier", () => {
  it("classifies by age thresholds", () => {
    expect(freshnessTier(null)).toEqual({ label: "No data", tone: "none" });
    expect(freshnessTier(3.2)).toEqual({ label: "3.2h ago", tone: "fresh" });
    expect(freshnessTier(48)).toEqual({ label: "48h ago", tone: "stale" });
    expect(freshnessTier(120)).toEqual({ label: "5d ago", tone: "old" });
  });
});

describe("getDataFreshness", () => {
  it("returns latest bar + age from the newest probe file", async () => {
    const dir = await fsp.mkdtemp(path.join(os.tmpdir(), "fresh-"));
    const folder = path.join(dir, "data", "nse_bse");
    await fsp.mkdir(folder, { recursive: true });
    await fsp.writeFile(
      path.join(folder, "RELIANCE.NS.csv"),
      "Date,Open,Close\n2026-06-08,1,2\n2026-06-09,1,2\n",
    );
    const now = Date.now();
    const f = await getDataFreshness(dir, now);
    expect(f.latestBar).toBe("2026-06-09");
    expect(f.sourceFile).toBe("data/nse_bse/RELIANCE.NS.csv");
    expect(f.ageHours).not.toBeNull();
    expect(f.ageHours!).toBeGreaterThanOrEqual(0);
    expect(f.ageHours!).toBeLessThan(1);
  });

  it("picks the maximum bar date across folders", async () => {
    const dir = await fsp.mkdtemp(path.join(os.tmpdir(), "fresh2-"));
    const a = path.join(dir, "data", "nse_bse");
    const b = path.join(dir, "data");
    await fsp.mkdir(a, { recursive: true });
    await fsp.writeFile(path.join(a, "RELIANCE.NS.csv"), "Date,Close\n2026-06-01,1\n");
    await fsp.writeFile(path.join(b, "RELIANCE.NS.csv"), "Date,Close\n2026-06-15,1\n");
    const f = await getDataFreshness(dir, Date.now());
    expect(f.latestBar).toBe("2026-06-15");
  });

  it("returns nulls when no probe files exist", async () => {
    const dir = await fsp.mkdtemp(path.join(os.tmpdir(), "fresh-empty-"));
    const f = await getDataFreshness(dir, Date.now());
    expect(f).toEqual({ latestBar: null, ageHours: null, sourceFile: null });
  });
});
