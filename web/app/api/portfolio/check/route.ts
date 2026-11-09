import { NextResponse } from "next/server";
import { guardPost, runMonitor, withPortfolioLock } from "@/lib/desk/portfolio";
import { BUSY_MESSAGE } from "@/lib/desk/run-update";
import { release, tryAcquire } from "@/lib/job-lock";

export const dynamic = "force-dynamic";

/** POST: "Check now" - re-evaluate every holding and rewrite ui_portfolio.json. 409 when a job is running. */
export async function POST(request: Request) {
  const refused = guardPost(request);
  if (refused) return refused;
  if (!tryAcquire()) return NextResponse.json({ ok: false, error: BUSY_MESSAGE }, { status: 409 });
  try {
    const r = await withPortfolioLock(() => runMonitor([]));
    if (r.code === 0) return NextResponse.json({ ok: true, output: r.stdout.trim().slice(-300) });
    return NextResponse.json(
      { ok: false, error: r.stderr.trim().slice(-300) || r.stdout.trim().slice(-300) || `exit ${r.code}` },
      { status: 500 },
    );
  } finally {
    release();
  }
}
