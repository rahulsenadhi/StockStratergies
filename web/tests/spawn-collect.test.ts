import { describe, it, expect } from "vitest";
import { EventEmitter } from "node:events";
import { collectJob, parseDryrunJson, type SpawnedChild } from "@/lib/spawn-collect";

function makeFakeChild() {
  const child = new EventEmitter() as EventEmitter & {
    stdout: EventEmitter; stderr: EventEmitter; kill: () => void; killed: boolean;
  };
  child.stdout = new EventEmitter();
  child.stderr = new EventEmitter();
  child.killed = false;
  child.kill = () => { child.killed = true; };
  return child;
}

describe("collectJob", () => {
  it("exit 0 -> 200 with collected stdout", async () => {
    const child = makeFakeChild();
    const p = collectJob(() => child as unknown as SpawnedChild, {
      bin: "python", args: [], cwd: ".", timeoutMs: 1000,
    });
    child.stdout.emit("data", '{"ok":');
    child.stdout.emit("data", "true}\n");
    child.emit("exit", 0);
    const r = await p;
    expect(r.status).toBe(200);
    if (r.status === 200) expect(r.stdout).toBe('{"ok":true}\n');
  });

  it("nonzero exit -> 500 with stderr text", async () => {
    const child = makeFakeChild();
    const p = collectJob(() => child as unknown as SpawnedChild, {
      bin: "python", args: [], cwd: ".", timeoutMs: 1000,
    });
    child.stderr.emit("data", "Traceback: boom");
    child.emit("exit", 1);
    const r = await p;
    expect(r.status).toBe(500);
    if (r.status !== 200) expect(r.error).toBe("Traceback: boom");
  });

  it("timeout -> 504 and kills the child", async () => {
    const child = makeFakeChild();
    const r = await collectJob(() => child as unknown as SpawnedChild, {
      bin: "python", args: [], cwd: ".", timeoutMs: 10,
    });
    expect(r.status).toBe(504);
    expect(child.killed).toBe(true);
  });

  it("throwing spawnFn -> 500", async () => {
    const r = await collectJob(() => { throw new Error("cannot spawn"); }, {
      bin: "python", args: [], cwd: ".", timeoutMs: 1000,
    });
    expect(r.status).toBe(500);
    if (r.status !== 200) expect(r.error).toBe("cannot spawn");
  });
});

describe("parseDryrunJson", () => {
  it("parses the last JSON object line, ignoring leading noise", () => {
    const out = "Loaded 157 tickers\n[features]\n{\"ok\":true,\"today\":{\"count\":3}}\n";
    expect(parseDryrunJson(out)).toEqual({ ok: true, today: { count: 3 } });
  });
  it("returns null when no JSON object is present", () => {
    expect(parseDryrunJson("just logs\nno json here\n")).toBeNull();
  });
  it("returns null on malformed JSON", () => {
    expect(parseDryrunJson("{not valid}")).toBeNull();
  });
  it("returns null when the only JSON is an array", () => {
    expect(parseDryrunJson("[1,2,3]\n")).toBeNull();
  });
});
