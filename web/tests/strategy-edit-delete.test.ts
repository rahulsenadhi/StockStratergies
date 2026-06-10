import { describe, it, expect } from "vitest";
import path from "node:path";
import os from "node:os";
import { promises as fsp } from "node:fs";
import { getStrategySpec } from "@/lib/data/strategies";

async function tmpDir(prefix: string): Promise<string> {
  return fsp.mkdtemp(path.join(os.tmpdir(), prefix));
}

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
