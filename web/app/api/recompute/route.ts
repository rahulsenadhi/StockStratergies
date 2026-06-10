import { NextResponse } from "next/server";
import { spawn } from "node:child_process";
import { resolveRecompute, runRecompute, type SpawnedChild } from "@/lib/recompute";
import { tryAcquire, release } from "@/lib/job-lock";

export const dynamic = "force-dynamic";

const TIMEOUT_MS = 120_000;

export async function POST() {
  if (!tryAcquire()) {
    return NextResponse.json(
      { ok: false, error: "A job is already running" },
      { status: 409 },
    );
  }
  try {
    const { bin, args, cwd } = resolveRecompute(process.env, process.cwd());
    const { status, body } = await runRecompute(
      (b, a, o) => spawn(b, a, o) as unknown as SpawnedChild,
      { bin, args, cwd, timeoutMs: TIMEOUT_MS },
    );
    return NextResponse.json(body, { status });
  } finally {
    release();
  }
}
