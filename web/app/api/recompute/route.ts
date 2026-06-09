import { NextResponse } from "next/server";
import { spawn } from "node:child_process";
import { resolveRecompute, runRecompute, type SpawnedChild } from "@/lib/recompute";

export const dynamic = "force-dynamic";

const TIMEOUT_MS = 120_000;
let running = false; // module-level in-flight lock (single-process local server)

export async function POST() {
  if (running) {
    return NextResponse.json(
      { ok: false, error: "Recompute already running" },
      { status: 409 },
    );
  }
  running = true;
  try {
    const { bin, args, cwd } = resolveRecompute(process.env, process.cwd());
    const { status, body } = await runRecompute(
      (b, a, o) => spawn(b, a, o) as unknown as SpawnedChild,
      { bin, args, cwd, timeoutMs: TIMEOUT_MS },
    );
    return NextResponse.json(body, { status });
  } finally {
    running = false;
  }
}
