import { describe, it, expect } from "vitest";
import path from "node:path";
import { resolveRecompute } from "@/lib/recompute";

describe("resolveRecompute", () => {
  it("defaults bin to python and args to the module invocation", () => {
    const r = resolveRecompute({}, "/repo/web");
    expect(r.bin).toBe("python");
    expect(r.args).toEqual(["-m", "core.leaderboard"]);
  });
  it("honors PYTHON_BIN override", () => {
    expect(resolveRecompute({ PYTHON_BIN: "python3" }, "/repo/web").bin).toBe("python3");
  });
  it("resolves cwd from DATA_DIR (default '..') against the passed cwd", () => {
    expect(resolveRecompute({}, "/repo/web").cwd).toBe(path.resolve("/repo/web", ".."));
    expect(resolveRecompute({ DATA_DIR: "../data-root" }, "/repo/web").cwd).toBe(
      path.resolve("/repo/web", "../data-root"),
    );
  });
});
