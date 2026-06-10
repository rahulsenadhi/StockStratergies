import { describe, it, expect } from "vitest";
import path from "node:path";
import os from "node:os";
import { promises as fsp } from "node:fs";
import { getStrategySpec, updateStrategyIndexEntry } from "@/lib/data/strategies";

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
