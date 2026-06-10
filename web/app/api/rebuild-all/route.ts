import { NextResponse } from "next/server";
import { spawn } from "node:child_process";
import path from "node:path";
import { resolveRecompute, type SpawnedChild } from "@/lib/recompute";
import { runRebuildAll } from "@/lib/rebuild-all";
import { getStrategies } from "@/lib/data/strategies";
import { tryAcquire, release } from "@/lib/job-lock";

export const dynamic = "force-dynamic";

// momentum_edge runs ~563s standalone and exceeds 600s under Rebuild All contention; 20min gives margin
const BACKTEST_TIMEOUT_MS = 1_200_000;
const RECOMPUTE_TIMEOUT_MS = 120_000;

const spawnChild = (b: string, a: string[], o: { cwd: string }) =>
  spawn(b, a, o) as unknown as SpawnedChild;

export async function POST() {
  if (!tryAcquire()) {
    return NextResponse.json(
      { ok: false, error: "A job is already running" },
      { status: 409 },
    );
  }
  try {
    const repoRoot = path.resolve(process.cwd(), process.env.DATA_DIR ?? "..");
    const strategies = await getStrategies();
    const backtests = strategies
      .filter((s) => s.backtest)
      .map((s) => ({ id: s.id, argv: s.backtest as string[] }));
    const recompute = resolveRecompute(process.env, process.cwd());

    const result = await runRebuildAll(spawnChild, {
      backtests,
      repoRoot,
      env: { PYTHON_BIN: process.env.PYTHON_BIN },
      recompute,
      backtestTimeoutMs: BACKTEST_TIMEOUT_MS,
      recomputeTimeoutMs: RECOMPUTE_TIMEOUT_MS,
    });
    return NextResponse.json(result.body, { status: result.status });
  } finally {
    release();
  }
}
