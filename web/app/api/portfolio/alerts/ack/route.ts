import { NextResponse } from "next/server";
import {
  guardPost, lastJsonLine, MAX_TEXT, readJsonBody, runMonitor, withPortfolioLock,
} from "@/lib/desk/portfolio";

export const dynamic = "force-dynamic";

/**
 * POST { alert_id }: acknowledge an alert. This only writes alerts.json (through Python) and is
 * deliberately separate from recording a sale: it never creates or changes a transaction.
 * The page's ui_portfolio.json picks the acknowledgement up on the next monitor run.
 */
export async function POST(request: Request) {
  const refused = guardPost(request);
  if (refused) return refused;
  const body = await readJsonBody(request);
  if (!body.ok) return body.response;
  const id = (body.value as { alert_id?: unknown } | null)?.alert_id;
  if (typeof id !== "string" || !id || id.length > MAX_TEXT) {
    return NextResponse.json({ ok: false, error: "alert_id is required" }, { status: 400 });
  }
  return withPortfolioLock(async () => {
    const r = await runMonitor(["--ack", id]);
    const out = lastJsonLine(r.stdout);
    if (r.code === 0 && out?.ok === true) return NextResponse.json({ ok: true });
    const errors = Array.isArray(out?.errors) ? out.errors : [r.stderr.trim().slice(-300) || "could not acknowledge"];
    return NextResponse.json({ ok: false, errors }, { status: r.code === 2 ? 404 : 500 });
  });
}
