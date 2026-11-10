import { NextResponse } from "next/server";
import { SYMBOL_PATTERN, loadMomentumChart } from "@/lib/desk/momentum-chart";

export const dynamic = "force-dynamic";

const NO_STORE = { "Cache-Control": "no-store" };
const reply = (body: object, status: number) => NextResponse.json(body, { status, headers: NO_STORE });

/** GET ?symbol=: the saved indicator chart for one stock. Reads a fixed folder only; the symbol is validated first. */
export async function GET(request: Request) {
  const symbol = new URL(request.url).searchParams.get("symbol");
  if (!symbol) return reply({ ok: false, error: "symbol is required" }, 404);
  if (!SYMBOL_PATTERN.test(symbol)) return reply({ ok: false, error: "invalid symbol" }, 400);
  const res = await loadMomentumChart(symbol);
  if (res.ok) return reply(res.chart, 200);
  if (res.reason === "missing") return reply({ ok: false, error: "no saved chart" }, 404);
  return reply({ ok: false, error: `saved chart is ${res.reason}` }, 500);
}
