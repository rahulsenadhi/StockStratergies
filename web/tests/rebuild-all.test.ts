import { describe, it, expect } from "vitest";
import { EventEmitter } from "node:events";
import { runRebuildAll } from "@/lib/rebuild-all";
import { type SpawnFn, type SpawnedChild } from "@/lib/recompute";

type Outcome = { code: number; stderr?: string };

// Returns a SpawnFn that yields one scripted child per call (in order), each
// emitting its stderr then exit on a microtask so serial runRecompute calls settle.
// Records the script (argv[0]) of every spawn for order assertions.
function scriptedSpawn(outcomes: Outcome[]): { fn: SpawnFn; calls: string[] } {
  let i = 0;
  const calls: string[] = [];
  const fn: SpawnFn = (_bin, args) => {
    calls.push(args[0] ?? "");
    const outcome = outcomes[i++] ?? { code: 0 };
    const child = new EventEmitter() as EventEmitter & {
      stderr: EventEmitter;
      kill: () => void;
    };
    child.stderr = new EventEmitter();
    child.kill = () => {};
    queueMicrotask(() => {
      if (outcome.stderr) child.stderr.emit("data", outcome.stderr);
      child.emit("exit", outcome.code);
    });
    return child as unknown as SpawnedChild;
  };
  return { fn, calls };
}

const baseOpts = {
  repoRoot: "/repo",
  env: {},
  recompute: { bin: "python", args: ["-m", "core.leaderboard"], cwd: "/repo" },
  backtestTimeoutMs: 1000,
  recomputeTimeoutMs: 1000,
};

describe("runRebuildAll", () => {
  it("all backtests succeed -> ran has all ids, failed empty, recompute 200, ok true", async () => {
    const { fn } = scriptedSpawn([{ code: 0 }, { code: 0 }, { code: 0 }]);
    const r = await runRebuildAll(fn, {
      ...baseOpts,
      backtests: [
        { id: "a", argv: ["a.py"] },
        { id: "b", argv: ["b.py"] },
      ],
    });
    expect(r.status).toBe(200);
    expect(r.body.ran).toEqual(["a", "b"]);
    expect(r.body.failed).toEqual([]);
    expect(r.body.recompute.status).toBe(200);
    expect(r.body.ok).toBe(true);
  });

  it("runs backtests in array order, recompute last", async () => {
    const { fn, calls } = scriptedSpawn([{ code: 0 }, { code: 0 }, { code: 0 }]);
    await runRebuildAll(fn, {
      ...baseOpts,
      backtests: [
        { id: "a", argv: ["a.py"] },
        { id: "b", argv: ["b.py"] },
      ],
    });
    expect(calls).toEqual(["a.py", "b.py", "-m"]);
  });

  it("one backtest fails -> it lands in failed, others ran, recompute still runs, ok false", async () => {
    const { fn } = scriptedSpawn([
      { code: 1, stderr: "boom" },
      { code: 0 },
      { code: 0 },
    ]);
    const r = await runRebuildAll(fn, {
      ...baseOpts,
      backtests: [
        { id: "a", argv: ["a.py"] },
        { id: "b", argv: ["b.py"] },
      ],
    });
    expect(r.body.ran).toEqual(["b"]);
    expect(r.body.failed).toEqual([{ id: "a", error: "boom" }]);
    expect(r.body.recompute.status).toBe(200);
    expect(r.body.ok).toBe(false);
  });

  it("unsafe argv -> resolveBacktest throw captured as failed, loop continues, no spawn for it", async () => {
    const { fn, calls } = scriptedSpawn([{ code: 0 }, { code: 0 }]);
    const r = await runRebuildAll(fn, {
      ...baseOpts,
      backtests: [
        { id: "bad", argv: ["../evil.py"] },
        { id: "b", argv: ["b.py"] },
      ],
    });
    expect(r.body.ran).toEqual(["b"]);
    expect(r.body.failed).toHaveLength(1);
    expect(r.body.failed[0].id).toBe("bad");
    expect(calls).toEqual(["b.py", "-m"]); // bad never spawned
    expect(r.body.ok).toBe(false);
  });

  it("recompute fails -> recompute.status reflects it, ok false", async () => {
    const { fn } = scriptedSpawn([{ code: 0 }, { code: 1, stderr: "rc boom" }]);
    const r = await runRebuildAll(fn, {
      ...baseOpts,
      backtests: [{ id: "a", argv: ["a.py"] }],
    });
    expect(r.body.ran).toEqual(["a"]);
    expect(r.body.recompute.status).toBe(500);
    expect(r.body.recompute.error).toBe("rc boom");
    expect(r.body.ok).toBe(false);
  });

  it("empty backtests -> recompute still runs, ran/failed empty, ok true", async () => {
    const { fn, calls } = scriptedSpawn([{ code: 0 }]);
    const r = await runRebuildAll(fn, { ...baseOpts, backtests: [] });
    expect(r.body.ran).toEqual([]);
    expect(r.body.failed).toEqual([]);
    expect(r.body.recompute.status).toBe(200);
    expect(r.body.ok).toBe(true);
    expect(calls).toEqual(["-m"]); // only recompute
  });
});

describe("runRebuildAll onLine", () => {
  it("emits a '▶ running <id>' header before each backtest and threads onLine", async () => {
    const { fn } = scriptedSpawn([{ code: 0 }, { code: 0 }, { code: 0 }]);
    const lines: string[] = [];
    await runRebuildAll(fn, {
      ...baseOpts,
      backtests: [
        { id: "a", argv: ["a.py"] },
        { id: "b", argv: ["b.py"] },
      ],
      onLine: (l) => lines.push(l),
    });
    expect(lines).toContain("▶ running a");
    expect(lines).toContain("▶ running b");
    expect(lines).toContain("▶ recompute");
    expect(lines.indexOf("▶ running a")).toBeLessThan(lines.indexOf("▶ running b"));
  });
});
