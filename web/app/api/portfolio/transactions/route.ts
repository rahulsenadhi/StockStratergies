import { NextResponse } from "next/server";
import {
  guardPost, lastJsonLine, prefilterTransaction, readJsonBody, readLedger,
  runMonitor, withPortfolioLock, withTempJson,
} from "@/lib/desk/portfolio";
import { release, tryAcquire } from "@/lib/job-lock";

export const dynamic = "force-dynamic";

export async function GET() {
  const ledger = await readLedger();
  if (!ledger.ok) return NextResponse.json({ ok: false, error: ledger.error }, { status: 500 });
  return NextResponse.json({ ok: true, transactions: ledger.transactions });
}

/**
 * POST one BUY / SELL / VOID. Python (`portfolio_monitor.py --append`) validates and is the
 * only ledger writer; afterwards the monitor re-runs so ui_portfolio.json reflects the change.
 * Only ever called from a user action: transactions are never created automatically.
 */
export async function POST(request: Request) {
  const refused = guardPost(request);
  if (refused) return refused;
  const body = await readJsonBody(request);
  if (!body.ok) return body.response;
  const shape = prefilterTransaction(body.value);
  if (shape.length) return NextResponse.json({ ok: false, errors: shape }, { status: 400 });

  return withPortfolioLock(async () => {
    const appended = await withTempJson(body.value, (file) => runMonitor(["--append", file]));
    const out = lastJsonLine(appended.stdout);
    if (appended.code === 0 && out?.ok === true) {
      const monitor = await refreshMonitor();
      return NextResponse.json({ ok: true, transaction: out.transaction, monitor }, { status: 201 });
    }
    const errors = Array.isArray(out?.errors)
      ? out.errors
      : [appended.stderr.trim().slice(-300) || "could not record transaction"];
    // exit 2 = Python rejected the transaction; anything else (corrupt ledger, crash) is a server problem.
    return NextResponse.json({ ok: false, errors }, { status: appended.code === 2 ? 400 : 500 });
  });
}

/** Re-run the monitor unless a heavy job holds the shared lock; never fails the recorded write. */
async function refreshMonitor(): Promise<{ ran: boolean; ok: boolean; note?: string }> {
  if (!tryAcquire()) return { ran: false, ok: false, note: "another job is running; use Check now later" };
  try {
    const r = await runMonitor([]);
    if (r.code === 0) return { ran: true, ok: true };
    return { ran: true, ok: false, note: r.stderr.trim().slice(-300) || `exit ${r.code}` };
  } finally {
    release();
  }
}
