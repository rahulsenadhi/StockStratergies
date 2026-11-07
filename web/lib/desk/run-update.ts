import { runRecompute, type SpawnFn } from "@/lib/recompute";
import { UPDATE_STEPS, UPDATE_STRATEGIES, type UpdateStrategy } from "@/lib/desk/update-steps";

export const BUSY_MESSAGE = "An update is already running.";
const ERROR_TAIL_CHARS = 800; // Streamlit shows the last 800 characters of a failed step

export interface UpdateResult {
  strategy: UpdateStrategy;
  ok: boolean;
  failedStep?: string;
  errorTail?: string;
}

export interface UpdateBody {
  ok: boolean;
  results: UpdateResult[];
}

/** Request body -> strategies to run; null for anything not "all" or a known strategy. */
export function parseUpdateTarget(body: unknown): UpdateStrategy[] | null {
  if (typeof body !== "object" || body === null) return null;
  const target = (body as { strategy?: unknown }).strategy;
  if (target === "all") return [...UPDATE_STRATEGIES];
  return (UPDATE_STRATEGIES as readonly unknown[]).includes(target) ? [target as UpdateStrategy] : null;
}

/**
 * Run each strategy's steps in order (like Streamlit's _refresh_all): a strategy stops at its
 * first failing step, then the next strategy still runs. spawnFn is injected for tests.
 */
export async function runUpdate(
  spawnFn: SpawnFn,
  opts: { strategies: UpdateStrategy[]; cwd: string; pythonBin: string; stepTimeoutMs: number; onLine?: (line: string) => void },
): Promise<{ status: number; body: UpdateBody }> {
  const results: UpdateResult[] = [];
  for (const strategy of opts.strategies) {
    opts.onLine?.(`▶ Updating ${strategy}`);
    let failure: UpdateResult | null = null;
    for (const step of UPDATE_STEPS[strategy]) {
      const name = step.find((part) => part.endsWith(".py")) ?? step[0];
      opts.onLine?.(`▸ ${name}`);
      // Keep this step's printed output: several scripts print their error to stdout and
      // exit 1, which runRecompute reports only as "exit 1" (Streamlit used stdout then).
      const printed: string[] = [];
      const run = await runRecompute(spawnFn, {
        bin: opts.pythonBin, args: step, cwd: opts.cwd, timeoutMs: opts.stepTimeoutMs, label: name,
        onLine: (line) => {
          printed.push(line);
          if (printed.length > 200) printed.shift();
          opts.onLine?.(line);
        },
      });
      if (run.status !== 200) {
        const reported = run.body.ok ? "" : run.body.error;
        const error = /^exit -?\d+$/.test(reported) && printed.length ? printed.join("\n") : reported;
        failure = { strategy, ok: false, failedStep: name, errorTail: error.slice(-ERROR_TAIL_CHARS) };
        break;
      }
    }
    results.push(failure ?? { strategy, ok: true });
    opts.onLine?.(failure ? `✗ ${strategy} failed at ${failure.failedStep}` : `✓ ${strategy} updated`);
  }
  return { status: 200, body: { ok: results.every((r) => r.ok), results } };
}
