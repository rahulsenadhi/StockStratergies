import { NextResponse } from "next/server";
import { portfolioPaths } from "@/lib/desk/portfolio";
import { loadUniverse, searchUniverse, universeCsvPath } from "@/lib/desk/portfolio-universe";

export const dynamic = "force-dynamic";

/** GET ?q=text -> up to 20 { symbol, name, exchange, isin } from the existing universe. */
export async function GET(request: Request) {
  const q = new URL(request.url).searchParams.get("q") ?? "";
  try {
    const entries = await loadUniverse(universeCsvPath(portfolioPaths().repoRoot));
    return NextResponse.json({ ok: true, results: searchUniverse(entries, q) });
  } catch {
    return NextResponse.json({ ok: false, error: "stock universe could not be read" }, { status: 500 });
  }
}
