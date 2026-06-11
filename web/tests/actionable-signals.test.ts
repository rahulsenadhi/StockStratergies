import { describe, it, expect } from "vitest";
import path from "node:path";
import os from "node:os";
import { promises as fsp } from "node:fs";
import { getActionableSignals } from "@/lib/data/strategies";

async function seed(): Promise<string> {
  const dir = await fsp.mkdtemp(path.join(os.tmpdir(), "act-"));
  await fsp.writeFile(
    path.join(dir, "sig.csv"),
    "Ticker,Company,Signal,Close,ATH (₹),Dist ATH%,Entry Type,Chart Qual,Choppiness,Recovery,220 EMA,52W High,vs High%,Vol Ratio,Score\n" +
      "ABC,ABC Ltd,Breakout Today,100,110,-9.1,52W High,Clean ✅,40,Fast 🟢,90,110,-9.1,1.2,55\n" +
      "XYZ,XYZ Ltd,Watch Zone,200,260,-23,52W High,Clean ✅,50,Slow,180,260,-23,0.5,40\n",
  );
  return dir;
}

describe("getActionableSignals", () => {
  it("maps Signal→Action, derives Stop ₹ at -15%, parses cols", async () => {
    const dir = await seed();
    const rows = await getActionableSignals("sig.csv", dir);
    expect(rows).toHaveLength(2);
    const a = rows[0];
    expect(a.ticker).toBe("ABC");
    expect(a.action).toBe("BUY NOW");
    expect(a.close).toBeCloseTo(100);
    expect(a.stopPrice).toBeCloseTo(85);
    expect(a.stopPct).toBe(-15);
    expect(a.score).toBeCloseTo(55);
    expect(a.entryType).toBe("52W High");
    expect(rows[1].action).toBe("FORMING");
  });
  it("returns [] when the file is missing", async () => {
    const dir = await fsp.mkdtemp(path.join(os.tmpdir(), "act-empty-"));
    expect(await getActionableSignals("nope.csv", dir)).toEqual([]);
  });
});
