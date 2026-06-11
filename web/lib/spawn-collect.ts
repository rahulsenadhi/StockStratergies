/** Spawn a short-lived subprocess, collect its full stdout, and map the outcome
 *  to an HTTP status. Unlike runRecompute (SSE/line-streaming), this buffers the
 *  whole output for one-shot JSON parsing. spawnFn is injected for testability. */

export interface SpawnedChild {
  stdout?: { on(event: "data", listener: (chunk: unknown) => void): void };
  stderr: { on(event: "data", listener: (chunk: unknown) => void): void };
  on(event: "exit", listener: (code: number | null) => void): void;
  on(event: "error", listener: (err: Error) => void): void;
  kill(): void;
}

export type SpawnFn = (bin: string, args: string[], opts: { cwd: string }) => SpawnedChild;

export type CollectOutcome =
  | { status: 200; stdout: string }
  | { status: number; error: string };

const errMsg = (e: unknown): string => (e instanceof Error ? e.message : String(e));

export function collectJob(
  spawnFn: SpawnFn,
  opts: { bin: string; args: string[]; cwd: string; timeoutMs: number; label?: string },
): Promise<CollectOutcome> {
  return new Promise((resolve) => {
    let settled = false;
    let stdout = "";
    let stderr = "";
    let child: SpawnedChild | undefined;

    const done = (o: CollectOutcome) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve(o);
    };

    const timer = setTimeout(() => {
      try { child?.kill(); } catch { /* already timing out */ }
      done({ status: 504, error: `${opts.label ?? "Job"} timed out` });
    }, opts.timeoutMs);

    try {
      child = spawnFn(opts.bin, opts.args, { cwd: opts.cwd });
    } catch (e) {
      done({ status: 500, error: errMsg(e) });
      return;
    }

    child.stdout?.on("data", (c) => { stdout += String(c); });
    child.stderr.on("data", (c) => { stderr += String(c); });
    child.on("error", (e) => done({ status: 500, error: errMsg(e) }));
    child.on("exit", (code) => {
      if (code === 0) done({ status: 200, stdout });
      else done({ status: 500, error: stderr.trim() || `exit ${code}` });
    });
  });
}

/** Scan subprocess stdout for the dry-run JSON blob. The Python tool may print
 *  data-loading noise before the JSON, so we take the last line that parses to a
 *  JSON object. Returns null if none parses. */
export function parseDryrunJson(stdout: string): Record<string, unknown> | null {
  const lines = stdout.split(/\r\n|\r|\n/);
  for (let i = lines.length - 1; i >= 0; i--) {
    const line = lines[i].trim();
    if (!line.startsWith("{")) continue;
    try {
      const parsed = JSON.parse(line);
      if (parsed && typeof parsed === "object") return parsed as Record<string, unknown>;
    } catch { /* try the previous line */ }
  }
  return null;
}
