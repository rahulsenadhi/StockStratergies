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
  env: NodeJS.ProcessEnv,
  cwd: string,
): { bin: string; args: string[]; cwd: string } {
  return {
    bin: env.PYTHON_BIN ?? "python",
    args: ["-m", "core.leaderboard"],
    cwd: path.resolve(cwd, env.DATA_DIR ?? ".."),
  };
}
