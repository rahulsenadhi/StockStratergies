import { NextResponse } from "next/server";
import { spawn } from "node:child_process";
import path from "node:path";
import { runRecompute, type SpawnedChild } from "@/lib/recompute";
import {
  getStrategy,
  deriveStrategyId,
  summarizeExits,
  writeStrategySpec,
  appendStrategyStub,
  type ExitsSpec,
  type StrategyStub,
} from "@/lib/data/strategies";
import { tryAcquire, release } from "@/lib/job-lock";
import { streamJob } from "@/lib/job-stream";

export const dynamic = "force-dynamic";

const CREATE_TIMEOUT_MS = 600_000;
const SID_RE = /^[a-z0-9_]+$/;

const spawnChild = (b: string, a: string[], o: { cwd: string }) =>
  spawn(b, a, o) as unknown as SpawnedChild;

type CreateBody = {
  name?: unknown; description?: unknown; type?: unknown; universe?: unknown;
  entry_formula?: unknown; exits?: ExitsSpec; sizing?: Record<string, unknown>;
};

function bad(error: string) {
  return NextResponse.json({ ok: false, error }, { status: 400 });
}

export async function POST(request: Request) {
  const body = (await request.json().catch(() => ({}))) as CreateBody;

  const name = typeof body.name === "string" ? body.name.trim() : "";
  if (!name) return bad("name is required");
  if (name.length > 80) return bad("name is too long (max 80 characters)");
  const sid = deriveStrategyId(name);
  if (!SID_RE.test(sid)) return bad("name must contain letters, numbers, spaces or hyphens");

  const entryFormula = typeof body.entry_formula === "string" ? body.entry_formula.trim() : "";
  if (!entryFormula) return bad("entry formula is required");

  const exits: ExitsSpec = body.exits ?? {};
  if (!exits.time_enabled && !exits.hard_stop_enabled && !exits.trail_enabled) {
    return bad("enable at least one exit rule");
  }

  const sizing = body.sizing ?? {};
  const maxPositions = Number(sizing.max_positions);
  const initialCash = Number(sizing.initial_cash);
  if (!(maxPositions > 0) || !(initialCash > 0)) {
    return bad("max positions and initial cash must be positive numbers");
  }

  if (await getStrategy(sid)) {
    return NextResponse.json(
      { ok: false, error: "A strategy with that name already exists" },
      { status: 409 },
    );
  }

  if (!tryAcquire()) {
    return NextResponse.json(
      { ok: false, error: "A job is already running" },
      { status: 409 },
    );
  }
  return streamJob(async (onLine) => {
    try {
      const description = typeof body.description === "string" ? body.description : "";
      const type = typeof body.type === "string" && body.type ? body.type : "Custom";
      const universe = typeof body.universe === "string" && body.universe ? body.universe : "Nifty 50";

      const spec = {
        name, description, type, universe,
        entry_mode: "Formula DSL",
        entry_formula: entryFormula,
        exits,
        sizing,
      };

      const now = new Date().toISOString();
      const stub: StrategyStub = {
        id: sid, name, type, status: "Research", description, universe,
        entry_rule: entryFormula, exit_rule: summarizeExits(exits),
        sizing, trades_csv: "", equity_csv: "", kpis_inline: {},
        last_run: now, created: now, page_key: "Library",
      };

      try {
        await writeStrategySpec(sid, spec);
        await appendStrategyStub(stub);
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        const status = msg.includes("already exists") ? 409 : 500;
        return { status, body: { ok: false, error: msg } };
      }

      const repoRoot = path.resolve(process.cwd(), process.env.DATA_DIR ?? "..");
      const run = await runRecompute(spawnChild, {
        bin: process.env.PYTHON_BIN ?? "python",
        args: ["generic_backtest.py", "--spec", `strategies/${sid}.json`],
        cwd: repoRoot,
        timeoutMs: CREATE_TIMEOUT_MS,
        label: "Backtest",
        onLine,
      });
      if (run.status !== 200) {
        return { status: run.status, body: run.body };
      }
      return { status: 200, body: { ok: true, sid } };
    } finally {
      release();
    }
  });
}
