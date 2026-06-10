import { resolveBacktest, runRecompute, type SpawnFn } from "@/lib/recompute";

export type RebuildBacktest = { id: string; argv: string[] };

export interface RebuildAllBody {
  ok: boolean;
  ran: string[];
  failed: { id: string; error: string }[];
  recompute: { status: number; error?: string };
}

const errMsg = (e: unknown): string => (e instanceof Error ? e.message : String(e));

/**
 * Serially run each backtest (best-effort), then recompute once.
 * spawnFn is injected so this is unit-testable without real Python processes.
 * argv comes only from the trusted server-side index — never request input.
 */
export async function runRebuildAll(
  spawnFn: SpawnFn,
  opts: {
    backtests: RebuildBacktest[];
    repoRoot: string;
    env: { PYTHON_BIN?: string };
    recompute: { bin: string; args: string[]; cwd: string };
    backtestTimeoutMs: number;
    recomputeTimeoutMs: number;
  },
): Promise<{ status: number; body: RebuildAllBody }> {
  const ran: string[] = [];
  const failed: { id: string; error: string }[] = [];

  for (const bt of opts.backtests) {
    let cmd: { bin: string; args: string[]; cwd: string };
    try {
      cmd = resolveBacktest(bt.argv, opts.repoRoot, opts.env);
    } catch (e) {
      failed.push({ id: bt.id, error: errMsg(e) });
      continue;
    }
    const run = await runRecompute(spawnFn, {
      ...cmd,
      timeoutMs: opts.backtestTimeoutMs,
      label: `Backtest ${bt.id}`,
    });
    if (run.status === 200) {
      ran.push(bt.id);
    } else {
      failed.push({ id: bt.id, error: run.body.ok ? "" : run.body.error });
    }
  }

  const rc = await runRecompute(spawnFn, {
    ...opts.recompute,
    timeoutMs: opts.recomputeTimeoutMs,
    label: "Recompute",
  });
  const recompute =
    rc.status === 200
      ? { status: rc.status }
      : { status: rc.status, error: rc.body.ok ? undefined : rc.body.error };

  const ok = failed.length === 0 && recompute.status === 200;
  return { status: 200, body: { ok, ran, failed, recompute } };
}
