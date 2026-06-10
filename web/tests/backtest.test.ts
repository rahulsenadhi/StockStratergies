import { describe, it, expect, beforeEach } from "vitest";
import { tryAcquire, release, isHeld } from "@/lib/job-lock";
import { resolveBacktest } from "@/lib/recompute";

describe("job-lock", () => {
  beforeEach(() => release()); // singleton module — reset between tests

  it("acquires when free, refuses while held", () => {
    expect(isHeld()).toBe(false);
    expect(tryAcquire()).toBe(true);
    expect(isHeld()).toBe(true);
    expect(tryAcquire()).toBe(false); // already held
  });

  it("release frees the lock", () => {
    expect(tryAcquire()).toBe(true);
    release();
    expect(isHeld()).toBe(false);
    expect(tryAcquire()).toBe(true);
  });
});

describe("resolveBacktest", () => {
  it("resolves a valid argv to bin/args/cwd", () => {
    const r = resolveBacktest(["momentum_edge_backtest.py"], "/repo", {});
    expect(r).toEqual({ bin: "python", args: ["momentum_edge_backtest.py"], cwd: "/repo" });
  });
  it("honors PYTHON_BIN", () => {
    expect(resolveBacktest(["x.py"], "/repo", { PYTHON_BIN: "python3" }).bin).toBe("python3");
  });
  it("passes through extra argv elements", () => {
    expect(resolveBacktest(["a.py", "--flag", "v"], "/repo", {}).args).toEqual(["a.py", "--flag", "v"]);
  });
  it("throws when not configured (null/empty)", () => {
    expect(() => resolveBacktest(null, "/repo", {})).toThrow();
    expect(() => resolveBacktest([], "/repo", {})).toThrow();
  });
  it("rejects absolute paths", () => {
    expect(() => resolveBacktest(["/etc/x.py"], "/repo", {})).toThrow();
    expect(() => resolveBacktest(["C:\\x.py"], "/repo", {})).toThrow();
  });
  it("rejects .. traversal", () => {
    expect(() => resolveBacktest(["../x.py"], "/repo", {})).toThrow();
  });
  it("rejects a non-.py first arg", () => {
    expect(() => resolveBacktest(["momentum_edge_backtest"], "/repo", {})).toThrow();
  });
  it("rejects shell metacharacters anywhere in argv", () => {
    expect(() => resolveBacktest(["x.py", "; rm -rf /"], "/repo", {})).toThrow();
  });
});
