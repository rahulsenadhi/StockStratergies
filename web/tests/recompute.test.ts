import { describe, it, expect } from "vitest";
import { EventEmitter } from "node:events";
import path from "node:path";
import { resolveRecompute, runRecompute, type SpawnedChild } from "@/lib/recompute";

function makeFakeChild() {
  const child = new EventEmitter() as EventEmitter & {
    stderr: EventEmitter;
    kill: () => void;
    killed: boolean;
  };
  child.stderr = new EventEmitter();
  (child as unknown as { stdout: EventEmitter }).stdout = new EventEmitter();
  child.killed = false;
  child.kill = () => {
    child.killed = true;
  };
  return child;
}

describe("runRecompute", () => {
  it("exit 0 -> 200 ok with numeric durationMs", async () => {
    const child = makeFakeChild();
    const p = runRecompute(() => child as unknown as SpawnedChild, {
      bin: "python", args: [], cwd: ".", timeoutMs: 1000,
    });
    child.emit("exit", 0);
    const r = await p;
    expect(r.status).toBe(200);
    expect(r.body).toMatchObject({ ok: true });
    if (r.body.ok) expect(typeof r.body.durationMs).toBe("number");
  });

  it("nonzero exit -> 500 with stderr text", async () => {
    const child = makeFakeChild();
    const p = runRecompute(() => child as unknown as SpawnedChild, {
      bin: "python", args: [], cwd: ".", timeoutMs: 1000,
    });
    child.stderr.emit("data", "recompute failed: boom");
    child.emit("exit", 1);
    const r = await p;
    expect(r.status).toBe(500);
    expect(r.body).toEqual({ ok: false, error: "recompute failed: boom" });
  });

  it("timeout -> 504 and kills the child", async () => {
    const child = makeFakeChild();
    const p = runRecompute(() => child as unknown as SpawnedChild, {
      bin: "python", args: [], cwd: ".", timeoutMs: 10,
    });
    const r = await p;
    expect(r.status).toBe(504);
    expect(r.body).toMatchObject({ ok: false });
    expect(child.killed).toBe(true);
  });

  it("spawn error event -> 500", async () => {
    const child = makeFakeChild();
    const p = runRecompute(() => child as unknown as SpawnedChild, {
      bin: "python", args: [], cwd: ".", timeoutMs: 1000,
    });
    child.emit("error", new Error("spawn ENOENT"));
    const r = await p;
    expect(r.status).toBe(500);
    expect(r.body).toEqual({ ok: false, error: "spawn ENOENT" });
  });

  it("throwing spawnFn -> 500", async () => {
    const r = await runRecompute(
      () => {
        throw new Error("cannot spawn");
      },
      { bin: "python", args: [], cwd: ".", timeoutMs: 1000 },
    );
    expect(r.status).toBe(500);
    expect(r.body).toEqual({ ok: false, error: "cannot spawn" });
  });
});

describe("runRecompute onLine", () => {
  it("emits complete stdout lines, splitting on \\n and \\r, buffering partials", async () => {
    const child = makeFakeChild();
    const stdout = (child as unknown as { stdout: EventEmitter }).stdout;
    const lines: string[] = [];
    const p = runRecompute(() => child as unknown as SpawnedChild, {
      bin: "python", args: [], cwd: ".", timeoutMs: 1000,
      onLine: (l) => lines.push(l),
    });
    stdout.emit("data", "Loading\n[1/5] x\rVali");
    stdout.emit("data", "dated 200\n");
    child.emit("exit", 0);
    await p;
    expect(lines).toEqual(["Loading", "[1/5] x", "Validated 200"]);
  });

  it("does not throw when the child has no stdout (back-compat)", async () => {
    const child = makeFakeChild();
    delete (child as unknown as { stdout?: unknown }).stdout;
    const p = runRecompute(() => child as unknown as SpawnedChild, {
      bin: "python", args: [], cwd: ".", timeoutMs: 1000, onLine: () => {},
    });
    child.emit("exit", 0);
    const r = await p;
    expect(r.status).toBe(200);
  });
});

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
