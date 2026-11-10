import { NextResponse } from "next/server";
import { isValidSymbol, loadMomentumChart } from "@/lib/desk/momentum-chart";

export const dynamic = "force-dynamic";

const NO_STORE = { "Cache-Control": "no-store" };
const reply = (body: object, status: number) => NextResponse.json(body, { status, headers: NO_STORE });

/** GET ?symbol=: the saved indicator chart for one stock. Reads a fixed folder only; the symbol is validated first. */
export async function GET(request: Request) {
  const symbol = new URL(request.url).searchParams.get("symbol");
  if (!symbol) return reply({ ok: false, error: "symbol is required" }, 404);
  if (!isValidSymbol(symbol)) return reply({ ok: false, error: "invalid symbol" }, 400);
  const res = await loadMomentumChart(symbol);
  if (res.ok) return reply(res.chart, 200);
  // A missing, old-version or unreadable file all mean "no usable chart": the page shows its empty state.
  return reply({ ok: false, reason: res.reason, error: "no usable saved chart" }, 404);
}
