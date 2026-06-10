import { describe, it, expect } from "vitest";
import path from "node:path";
import os from "node:os";
import { promises as fsp } from "node:fs";
import { getStrategySpec, updateStrategyIndexEntry, deleteStrategy, validateStrategyFields } from "@/lib/data/strategies";

async function tmpDir(prefix: string): Promise<string> {
  return fsp.mkdtemp(path.join(os.tmpdir(), prefix));
}

describe("updateStrategyIndexEntry", () => {
  async function seed(): Promise<string> {
    const dir = await tmpDir("idx-");
    await fsp.writeFile(
      path.join(dir, "strategies_index.json"),
      JSON.stringify({ strategies: [
        { id: "a", name: "A", status: "Live" },
        { id: "b", name: "B", status: "Live" },
      ] }, null, 2),
    );
    return dir;
  }
  it("shallow-merges the patch into the matching entry, leaving others untouched", async () => {
    const dir = await seed();
    await updateStrategyIndexEntry("a", { status: "Research", entry_rule: "x > 1" }, dir);
    const idx = JSON.parse(await fsp.readFile(path.join(dir, "strategies_index.json"), "utf-8"));
    expect(idx.strategies[0]).toMatchObject({ id: "a", name: "A", status: "Research", entry_rule: "x > 1" });
    expect(idx.strategies[1]).toEqual({ id: "b", name: "B", status: "Live" });
  });
  it("throws when the id is absent", async () => {
    const dir = await seed();
    await expect(updateStrategyIndexEntry("nope", { status: "X" }, dir)).rejects.toThrow(/not found/);
  });
});

describe("getStrategySpec", () => {
  it("returns the parsed spec object when the file exists", async () => {
    const dir = await tmpDir("spec-");
    await fsp.mkdir(path.join(dir, "strategies"), { recursive: true });
    const spec = { name: "X", entry_formula: "a AND b", exits: {}, sizing: {} };
    await fsp.writeFile(path.join(dir, "strategies", "x.json"), JSON.stringify(spec));
    expect(await getStrategySpec("x", dir)).toEqual(spec);
  });
  it("returns null when the spec file is absent", async () => {
    const dir = await tmpDir("spec-");
    expect(await getStrategySpec("missing", dir)).toBeNull();
  });
  it("returns null when the spec file is unparseable", async () => {
    const dir = await tmpDir("spec-");
    await fsp.mkdir(path.join(dir, "strategies"), { recursive: true });
    await fsp.writeFile(path.join(dir, "strategies", "bad.json"), "{not json");
    expect(await getStrategySpec("bad", dir)).toBeNull();
  });
});

describe("deleteStrategy", () => {
  async function seed(): Promise<string> {
    const dir = await tmpDir("del-");
    await fsp.mkdir(path.join(dir, "strategies"), { recursive: true });
    await fsp.writeFile(path.join(dir, "strategies", "doomed.json"), JSON.stringify({ name: "Doomed" }));
    await fsp.writeFile(path.join(dir, "strategies", "doomed_kpis.csv"), "k,v\n1,2");
    await fsp.writeFile(path.join(dir, "doomed_trades.csv"), "h\n1");
    await fsp.writeFile(path.join(dir, "doomed_equity.csv"), "h\n1");
    await fsp.writeFile(
      path.join(dir, "strategies_index.json"),
      JSON.stringify({ strategies: [
        { id: "doomed", name: "Doomed", trades_csv: "doomed_trades.csv", equity_csv: "doomed_equity.csv" },
        { id: "keep", name: "Keep" },
      ] }, null, 2),
    );
    return dir;
  }
  it("removes the entry, spec file, and CSVs; returns true", async () => {
    const dir = await seed();
    expect(await deleteStrategy("doomed", dir)).toBe(true);
    const idx = JSON.parse(await fsp.readFile(path.join(dir, "strategies_index.json"), "utf-8"));
    expect(idx.strategies.map((s: { id: string }) => s.id)).toEqual(["keep"]);
    await expect(fsp.access(path.join(dir, "strategies", "doomed.json"))).rejects.toThrow();
    await expect(fsp.access(path.join(dir, "strategies", "doomed_kpis.csv"))).rejects.toThrow();
    await expect(fsp.access(path.join(dir, "doomed_trades.csv"))).rejects.toThrow();
    await expect(fsp.access(path.join(dir, "doomed_equity.csv"))).rejects.toThrow();
  });
  it("returns false and leaves the index intact when the id is absent", async () => {
    const dir = await seed();
    expect(await deleteStrategy("ghost", dir)).toBe(false);
    const idx = JSON.parse(await fsp.readFile(path.join(dir, "strategies_index.json"), "utf-8"));
    expect(idx.strategies).toHaveLength(2);
  });
  it("tolerates already-missing spec/CSV files (no throw)", async () => {
    const dir = await seed();
    await fsp.rm(path.join(dir, "strategies", "doomed.json"));
    await fsp.rm(path.join(dir, "doomed_trades.csv"));
    expect(await deleteStrategy("doomed", dir)).toBe(true);
  });
});

describe("validateStrategyFields", () => {
  const ok = {
    entry_formula: "rsi_14 > 70",
    exits: { time_enabled: true, time_days: 30 },
    sizing: { max_positions: 5, initial_cash: 1_000_000 },
  };
  it("accepts a valid body", () => {
    expect(validateStrategyFields(ok)).toEqual({ ok: true });
  });
  it("rejects an empty entry_formula", () => {
    expect(validateStrategyFields({ ...ok, entry_formula: "  " })).toEqual({
      ok: false, error: "entry formula is required",
    });
  });
  it("rejects when no exit is enabled", () => {
    expect(validateStrategyFields({ ...ok, exits: {} })).toEqual({
      ok: false, error: "enable at least one exit rule",
    });
  });
  it("rejects non-positive sizing", () => {
    expect(validateStrategyFields({ ...ok, sizing: { max_positions: 0, initial_cash: 1 } })).toEqual({
      ok: false, error: "max positions and initial cash must be positive numbers",
    });
  });
});
