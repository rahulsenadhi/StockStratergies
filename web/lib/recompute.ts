import path from "node:path";

export type RecomputeResult =
  | { ok: true; durationMs: number }
  | { ok: false; error: string };

/** Minimal shape of a spawned child that runRecompute needs (real child_process.spawn matches it). */
export interface SpawnedChild {
  stderr: { on(event: "data", listener: (chunk: unknown) => void): void };
  on(event: "exit", listener: (code: number | null) => void): void;
  on(event: "error", listener: (err: Error) => void): void;
  kill(): void;
}

export type SpawnFn = (bin: string, args: string[], opts: { cwd: string }) => SpawnedChild;

/** Resolve the command to run from the server environment. No request input is involved. */
export function resolveRecompute(
  env: { PYTHON_BIN?: string; DATA_DIR?: string; [key: string]: string | undefined },
  cwd: string,
): { bin: string; args: string[]; cwd: string } {
  return {
    bin: env.PYTHON_BIN ?? "python",
    args: ["-m", "core.leaderboard"],
    cwd: path.resolve(cwd, env.DATA_DIR ?? ".."),
  };
}

const errMsg = (e: unknown): string => (e instanceof Error ? e.message : String(e));

/**
 * Run the recompute subprocess and map its outcome to an HTTP status + body.
 * spawnFn is injected so this is unit-testable without a real Python process.
 */
export function runRecompute(
  spawnFn: SpawnFn,
  opts: { bin: string; args: string[]; cwd: string; timeoutMs: number },
): Promise<{ status: number; body: RecomputeResult }> {
  return new Promise((resolve) => {
    const start = Date.now();
    let settled = false;
    let stderr = "";
    let child: SpawnedChild | undefined;

    const done = (status: number, body: RecomputeResult) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve({ status, body });
    };

    const timer = setTimeout(() => {
      try {
        child?.kill();
      } catch {
        // ignore kill failure; we're already timing out
      }
      done(504, { ok: false, error: "Recompute timed out" });
    }, opts.timeoutMs);

    try {
      child = spawnFn(opts.bin, opts.args, { cwd: opts.cwd });
    } catch (e) {
      done(500, { ok: false, error: errMsg(e) });
      return;
    }

    child.stderr.on("data", (c) => {
      stderr += String(c);
    });
    child.on("error", (e) => done(500, { ok: false, error: errMsg(e) }));
    child.on("exit", (code) => {
      if (code === 0) done(200, { ok: true, durationMs: Date.now() - start });
      else done(500, { ok: false, error: stderr.trim() || `exit ${code}` });
    });
  });
}

/**
 * Resolve a strategy's declarative backtest argv (from the trusted index, NOT the request)
 * to a spawn command. Validates defensively: repo-relative .py first arg, no absolute path,
 * no ".." traversal, no shell metacharacters anywhere. Throws on invalid/missing argv.
 */
export function resolveBacktest(
  argv: string[] | null,
  repoRoot: string,
  env: { PYTHON_BIN?: string },
): { bin: string; args: string[]; cwd: string } {
  if (!argv || argv.length === 0) throw new Error("no backtest command configured");
  const script = argv[0];
  if (
    script.startsWith("/") ||
    /^[a-zA-Z]:/.test(script) || // windows absolute (C:\...)
    script.includes("..") ||
    !script.endsWith(".py") ||
    /[;&|`$<>\n]/.test(argv.join(" ")) // shell metacharacters anywhere
  ) {
    throw new Error(`unsafe backtest command: ${script}`);
  }
  return {
    bin: env.PYTHON_BIN ?? "python",
    args: argv,
    cwd: repoRoot,
  };
}
