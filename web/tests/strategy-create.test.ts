import { describe, it, expect } from "vitest";
import path from "node:path";
import os from "node:os";
import { promises as fsp } from "node:fs";
import { deriveStrategyId, summarizeExits, writeStrategySpec, appendStrategyStub, type StrategyStub } from "@/lib/data/strategies";

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

function makeStub(id: string): StrategyStub {
  return {
    id, name: id, type: "Custom", status: "Research", description: "d",
    universe: "Nifty 50", entry_rule: "x > 1", exit_rule: "hold 30d",
    sizing: { method: "Equal weight (capped)", max_positions: 5, initial_cash: 1000000 },
    trades_csv: "", equity_csv: "", kpis_inline: {},
    last_run: "2026-06-10T00:00:00.000Z", created: "2026-06-10T00:00:00.000Z",
    page_key: "Library",
  };
}

describe("writeStrategySpec", () => {
  it("writes strategies/{sid}.json with the exact object", async () => {
    const dir = await fsp.mkdtemp(path.join(os.tmpdir(), "spec-"));
    const spec = { name: "X", entry_formula: "a AND b", exits: {}, sizing: {} };
    await writeStrategySpec("my_strat", spec, dir);
    const written = JSON.parse(
      await fsp.readFile(path.join(dir, "strategies", "my_strat.json"), "utf-8"),
    );
    expect(written).toEqual(spec);
  });
});

describe("appendStrategyStub", () => {
  async function seed(): Promise<string> {
    const dir = await fsp.mkdtemp(path.join(os.tmpdir(), "idx-"));
    await fsp.writeFile(
      path.join(dir, "strategies_index.json"),
      JSON.stringify({ strategies: [{ id: "existing", name: "Existing" }] }, null, 2),
    );
    return dir;
  }
  it("appends a stub to the index", async () => {
    const dir = await seed();
    await appendStrategyStub(makeStub("new_one"), dir);
    const idx = JSON.parse(await fsp.readFile(path.join(dir, "strategies_index.json"), "utf-8"));
    expect(idx.strategies.map((s: { id: string }) => s.id)).toEqual(["existing", "new_one"]);
    expect(idx.strategies[1].status).toBe("Research");
  });
  it("throws on duplicate id", async () => {
    const dir = await seed();
    await expect(appendStrategyStub(makeStub("existing"), dir)).rejects.toThrow(/already exists/);
  });
});
