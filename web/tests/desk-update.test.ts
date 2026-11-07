import { afterEach, describe, expect, test } from "vitest";
import { EventEmitter } from "node:events";
import { execFileSync } from "node:child_process";
import path from "node:path";
import { type SpawnFn, type SpawnedChild } from "@/lib/recompute";
import { BUSY_MESSAGE, parseUpdateTarget, runUpdate } from "@/lib/desk/run-update";
import { errorHeadline } from "@/lib/desk/format";
import { UPDATE_STEPS, UPDATE_STRATEGIES } from "@/lib/desk/update-steps";
import { release, tryAcquire } from "@/lib/job-lock";
import { POST } from "@/app/api/update/route";

type Outcome = { code: number; stderr?: string; stdout?: string };

/** One scripted child per spawn, in order; records each script name. */
function scriptedSpawn(fail: Record<string, Outcome>): { fn: SpawnFn; calls: string[] } {
  const calls: string[] = [];
  const fn: SpawnFn = (_bin, args) => {
    const script = args[0] ?? "";
    calls.push(script);
    const outcome = fail[script] ?? { code: 0 };
    const child = new EventEmitter() as EventEmitter & { stderr: EventEmitter; stdout: EventEmitter; kill: () => void };
    child.stderr = new EventEmitter();
    child.stdout = new EventEmitter();
    child.kill = () => {};
    queueMicrotask(() => {
      if (outcome.stdout) child.stdout.emit("data", outcome.stdout);
      if (outcome.stderr) child.stderr.emit("data", outcome.stderr);
      child.emit("exit", outcome.code);
    });
    return child as unknown as SpawnedChild;
  };
  return { fn, calls };
}

const opts = { cwd: "/repo", pythonBin: "python", stepTimeoutMs: 1000 };

describe("runUpdate", () => {
  test("a failed strategy stops at its failing step; the others still run", async () => {
    const { fn, calls } = scriptedSpawn({ "ipo_edge_downloader.py": { code: 1, stderr: "boom" } });
    const r = await runUpdate(fn, { ...opts, strategies: [...UPDATE_STRATEGIES] });
    expect(r.body.ok).toBe(false);
    expect(r.body.results).toEqual([
      { strategy: "Monthly", ok: true },
      { strategy: "IPO", ok: false, failedStep: "ipo_edge_downloader.py", errorTail: "boom" },
      { strategy: "Momentum", ok: true },
      { strategy: "PEAD", ok: true },
    ]);
    const expected = [
      ...UPDATE_STEPS.Monthly.map((s) => s[0]),
      "ipo_edge_downloader.py",
      ...UPDATE_STEPS.Momentum.map((s) => s[0]),
      ...UPDATE_STEPS.PEAD.map((s) => s[0]),
    ];
    expect(calls).toEqual(expected);
  });

  test("a script that prints its error to stdout and exits 1 shows that message, not 'exit 1'", async () => {
    const { fn } = scriptedSpawn({
      "nse_bse_downloader.py": { code: 1, stdout: "Downloading 1227 symbols\nERROR: no internet connection\n" },
    });
    const r = await runUpdate(fn, { ...opts, strategies: ["Momentum"] });
    expect(r.body.results[0].errorTail).toBe("Downloading 1227 symbols\nERROR: no internet connection");
  });

  test("error tail keeps the last 800 characters", async () => {
    const long = "x".repeat(900) + "END";
    const { fn } = scriptedSpawn({ "pead_downloader.py": { code: 1, stderr: long } });
    const r = await runUpdate(fn, { ...opts, strategies: ["PEAD"] });
    expect(r.body.results[0].errorTail).toHaveLength(800);
    expect(r.body.results[0].errorTail?.endsWith("END")).toBe(true);
  });
});

describe("errorHeadline", () => {
  test("one short line: the last non-empty line of the error, capped at 120 characters", () => {
    const tb = "Traceback (most recent call last):\n  File \"x.py\", line 3\nConnectionError: no internet\n\n";
    expect(errorHeadline(tb)).toBe("ConnectionError: no internet");
    expect(errorHeadline("x".repeat(200))).toBe(`${"x".repeat(119)}…`);
    expect(errorHeadline(undefined)).toBe("no error message");
  });
});

describe("parseUpdateTarget", () => {
  test("accepts all or one known strategy only", () => {
    expect(parseUpdateTarget({ strategy: "all" })).toEqual(["Monthly", "IPO", "Momentum", "PEAD"]);
    expect(parseUpdateTarget({ strategy: "PEAD" })).toEqual(["PEAD"]);
    expect(parseUpdateTarget({ strategy: "rm -rf" })).toBeNull();
    expect(parseUpdateTarget({})).toBeNull();
    expect(parseUpdateTarget(null)).toBeNull();
  });
});

describe("POST /api/update", () => {
  afterEach(() => release());
  const req = (body: unknown, headers: Record<string, string> = { "content-type": "application/json" }) =>
    new Request("http://x/api/update", { method: "POST", body: JSON.stringify(body), headers });

  test("415 unless the request is JSON (a plain cross-site form post cannot start an update)", async () => {
    const res = await POST(req({ strategy: "all" }, { "content-type": "text/plain" }));
    expect(res.status).toBe(415);
  });

  test("403 for a request the browser marks as cross-site", async () => {
    const res = await POST(req({ strategy: "all" }, { "content-type": "application/json", "sec-fetch-site": "cross-site" }));
    expect(res.status).toBe(403);
  });

  test("409 with a clear message while another update runs", async () => {
    expect(tryAcquire()).toBe(true);
    const res = await POST(req({ strategy: "all" }));
    expect(res.status).toBe(409);
    expect(await res.json()).toEqual({ ok: false, error: BUSY_MESSAGE });
  });

  test("400 for an unknown strategy", async () => {
    const res = await POST(req({ strategy: "rm -rf" }));
    expect(res.status).toBe(400);
  });
});

// Integration: the step lists must equal Streamlit's _PIPELINES + _PRECOMPUTE_FOR.
const PY = process.env.PYTHON_BIN;
describe.skipIf(!PY)("UPDATE_STEPS parity with master_dashboard.py", () => {
  test("same steps, same order", () => {
    const cwd = path.resolve(process.cwd(), process.env.DATA_DIR ?? "..");
    const code =
      "import json,logging; logging.disable(logging.WARNING); import master_dashboard as m; " +
      "print(json.dumps({k: m._PIPELINES[k] + [[s] for s in m._PRECOMPUTE_FOR.get(k, [])] for k in m._PIPELINES}))";
    const out = execFileSync(path.resolve(process.cwd(), PY!), ["-c", code], {
      cwd, encoding: "utf-8", env: { ...process.env, PYTHONIOENCODING: "utf-8" }, stdio: ["ignore", "pipe", "ignore"],
    });
    const last = out.trim().split(/\r?\n/).pop() ?? "{}";
    expect(JSON.parse(last)).toEqual(UPDATE_STEPS);
  }, 120_000);
});
