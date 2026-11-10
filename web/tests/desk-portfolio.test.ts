import { createElement as h } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { describe, expect, it, vi } from "vitest";
import {
  actionTone, drawdown, held, mapAlert, mapEvaluation, mapPosition, mapTransaction, money, purchaseHref,
  PENDING_HOLDINGS, RECONSTRUCTED_LABEL, SCHEDULER_NOTICE, UNKNOWN_DATE, type PortfolioView,
} from "@/lib/desk/portfolio-text";
import { loadPortfolioView, readEvaluations } from "@/lib/desk/portfolio-view";
import type { PortfolioPaths } from "@/lib/desk/portfolio";

vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: () => {} }) }));
const { PortfolioDesk } = await import("@/components/desk/portfolio/portfolio-desk");
const { HoldingRail } = await import("@/components/desk/portfolio/holding-rail");

function position(over: Record<string, unknown> = {}, evaluation: Record<string, unknown> = {}) {
  return mapPosition({
    symbol: "APLAPOLLO.NS", name: "APL Apollo Tubes Limited", exchange: "NSE", open_qty: 20, avg_price: 2202.38,
    realised_pnl: 0, charges_known: true, first_buy_date: "2026-01-05", date_known: true, closed: false,
    unrealised_pnl: 1000, unrealised_pnl_pct: 2.27, lots: [{ buy_id: "b1", date: "2026-01-05", qty: 20, price: 2202.38, charges_alloc: 20 }],
    evaluation: {
      symbol: "APLAPOLLO.NS", action: "HOLD", rule: null, explanation: "Above the 220-day EMA and the hard stop.",
      last_close: 2252.38, last_bar_date: "2026-11-06", data_status: "OK", evaluated_at: "2026-11-09T03:00:00Z",
      levels: { hard_stop: 1872.02, ema220: 2000, ema_distance_pct: 12.6, highest_close_since_entry: 2400, ema_immature: false, bars: 600 },
      held_days: 308, drawdown_from_peak: -6.15, ...evaluation,
    },
    ...over,
  });
}

function view(over: Partial<PortfolioView> = {}): PortfolioView {
  return {
    positions: [], closed: [], alerts: [], transactions: [], evaluations: {}, errors: [],
    monitor: { last_run: null, last_good_check: null, ok: false, errors: [] }, ledgerReadable: true, snapshotReady: false, ...over,
  };
}
const render = (data: PortfolioView) => renderToStaticMarkup(h(PortfolioDesk, { data }));

describe("portfolio mappers", () => {
  it("defaults an unknown evaluation to DATA UNAVAILABLE, never HOLD", () => {
    const ev = mapEvaluation(undefined);
    expect(ev.action).toBe("DATA UNAVAILABLE");
    expect(ev.data_status).toBe("DATA UNAVAILABLE");
    expect(ev.last_close).toBeNull();
    expect(ev.reconstructed_first_exit).toBeNull();
  });

  it("drops non-finite numbers and keeps reconstruction fields", () => {
    const ev = mapEvaluation({ action: "EXIT", last_close: Number.NaN, levels: { ema220: "86" },
      reconstructed_first_exit: { date: "2026-10-01", rule: "EMA", close: 85, level: 86 } });
    expect(ev.last_close).toBeNull();
    expect(ev.levels.ema220).toBeNull();
    expect(ev.reconstructed_first_exit).toEqual({ date: "2026-10-01", rule: "EMA", close: 85, level: 86 });
  });

  it("maps positions, transactions and alerts defensively", () => {
    const p = mapPosition({ symbol: "X.NS", open_qty: "3" });
    expect(p.name).toBe("X.NS");
    expect(p.open_qty).toBe(0);
    expect(mapTransaction({ id: "t1", type: "VOID", voids: "t0" })).toMatchObject({ id: "t1", voids: "t0", trade_date: null });
    expect(mapAlert({ id: "a1", acknowledged_at: "" }).acknowledged_at).toBeNull();
  });

  it("maps actions to tones", () => {
    expect(actionTone("HOLD")).toBe("gain");
    expect(actionTone("REVIEW")).toBe("warn");
    expect(actionTone("REDUCE")).toBe("info");
    expect(actionTone("EXIT")).toBe("loss");
    expect(actionTone("STALE")).toBe("muted");
    expect(actionTone("DATA UNAVAILABLE")).toBe("muted");
  });

  it("shows buy date unknown instead of numbers for opening balances", () => {
    const p = position({ date_known: false, first_buy_date: null });
    expect(held(p)).toBe(UNKNOWN_DATE);
    expect(drawdown(p)).toBe(UNKNOWN_DATE);
    expect(held(position())).toBe("308 days");
  });

  it("puts the minus sign before the rupee symbol", () => {
    expect(money(-14704.56)).toBe("-₹14,704.56");
    expect(money(805.18)).toBe("₹805.18");
    expect(money(null)).toBe("—");
  });

  it("builds the add-purchase link with an encoded signal", () => {
    expect(purchaseHref("M&M.NS", "momentum_edge:M&M.NS:Breakout Today"))
      .toBe("/portfolio?add=M%26M.NS&signal=momentum_edge%3AM%26M.NS%3ABreakout%20Today#add-purchase");
    expect(purchaseHref("HAL.NS")).toBe("/portfolio?add=HAL.NS#add-purchase");
  });

  it("maps Momentum's bare NSE symbols to the ledger's .NS form and keeps .BO", () => {
    expect(purchaseHref("MINDACORP", "momentum_edge:MINDACORP:Watch Zone"))
      .toBe("/portfolio?add=MINDACORP.NS&signal=momentum_edge%3AMINDACORP%3AWatch%20Zone#add-purchase");
    expect(purchaseHref("ABC.BO")).toBe("/portfolio?add=ABC.BO#add-purchase");
    expect(purchaseHref("bajaj-auto")).toBe("/portfolio?add=BAJAJ-AUTO.NS#add-purchase");
  });
});

describe("portfolio page rendering", () => {
  it("empty ledger lists the seven named holdings without creating transactions", () => {
    const html = render(view());
    expect(html).toContain("Holdings pending your details");
    for (const p of PENDING_HOLDINGS) expect(html).toContain(p.symbol);
    // TMCV and JAYBARMARU identities were confirmed by the user on 2026-11-09.
    expect(html).not.toContain("please confirm");
    expect(html).toContain("No transactions have been created here");
    expect(html).toContain("No open holdings recorded");
    expect(html).toContain(SCHEDULER_NOTICE);
  });

  it("hides the pending card once any transaction exists", () => {
    const html = render(view({ transactions: [mapTransaction({ id: "t1", type: "BUY", symbol: "HAL.NS" })] }));
    expect(html).not.toContain("Holdings pending your details");
  });

  it("renders a STALE row with a muted pill and its data status", () => {
    const stale = position({}, { action: "STALE", data_status: "STALE", rule: null });
    const html = render(view({ positions: [stale] }));
    expect(html).toContain('rd-pill--muted">STALE');
    expect(html).not.toContain('rd-pill--gain">HOLD');
  });

  it("renders an EXIT row with its rule text", () => {
    const exit = position({ symbol: "PFOCUS.NS", name: "Prime Focus Limited" },
      { action: "EXIT", rule: "Hard stop", explanation: "Close 285.20 is below the hard stop 302.49." });
    const html = render(view({ positions: [exit] }));
    expect(html).toContain('rd-pill--loss">EXIT');
    expect(html).toContain("Rule: Hard stop");
    expect(html).not.toContain("please confirm");
    expect(html).toContain("Close 285.20 is below the hard stop 302.49.");
  });

  it("labels the reconstructed first exit as approximate", () => {
    const p = position({}, { reconstructed_first_exit: { date: "2026-10-01", rule: "EMA", close: 1990, level: 2000 } });
    const html = renderToStaticMarkup(h(HoldingRail, { position: p, transactions: [], evaluations: [], busy: false, onVoid: async () => true }));
    expect(html).toContain(RECONSTRUCTED_LABEL);
    expect(html).toContain("2026-10-01 · EMA");
  });

  it("disables writes when the ledger cannot be read", () => {
    const html = render(view({ ledgerReadable: false, errors: ["ledger file is unreadable; it was left untouched"] }));
    expect(html).toContain("Transactions are unavailable until the ledger can be read.");
    expect(html).toContain("Holdings cannot be confirmed");
    expect(html).not.toContain("Holdings pending your details");
  });
});

describe("loadPortfolioView", () => {
  async function tempPaths(): Promise<PortfolioPaths> {
    const dir = await fs.mkdtemp(path.join(os.tmpdir(), "portfolio-view-"));
    return { repoRoot: dir, dir, ledger: path.join(dir, "ledger.json"), alerts: path.join(dir, "alerts.json"),
      uiOut: path.join(dir, "ui_portfolio.json"), pythonBin: "python", script: path.join(dir, "none.py") };
  }

  it("treats a fresh folder as an empty readable ledger with no check yet", async () => {
    const v = await loadPortfolioView(await tempPaths());
    expect(v.ledgerReadable).toBe(true);
    expect(v.transactions).toEqual([]);
    expect(v.snapshotReady).toBe(false);
    expect(v.errors).toContain("No saved holding check yet. Check holdings now to build it.");
  });

  it("uses saved acknowledgements from alerts.json over the snapshot", async () => {
    const p = await tempPaths();
    const alert = { id: "a1", symbol: "PFOCUS.NS", action: "EXIT", message: "m" };
    await fs.writeFile(p.uiOut, JSON.stringify({ version: 1, positions: [], closed: [], alerts: [alert], monitor: { ok: true, last_run: "2026-11-09T03:00:00Z" } }));
    await fs.writeFile(p.alerts, JSON.stringify({ version: 1, alerts: [alert], acknowledgements: [{ alert_id: "a1", acknowledged_at: "2026-11-09T04:00:00Z" }] }));
    const v = await loadPortfolioView(p);
    expect(v.alerts[0].acknowledged_at).toBe("2026-11-09T04:00:00Z");
    expect(v.monitor.last_good_check).toBe("2026-11-09T03:00:00Z");
  });

  it("keeps the last 20 evaluations per holding and flags malformed lines", async () => {
    const p = await tempPaths();
    const file = path.join(p.dir, "evaluations.jsonl");
    const lines = Array.from({ length: 25 }, (_, i) => JSON.stringify({ symbol: "HAL.NS", action: "HOLD", evaluated_at: `t${i}` }));
    await fs.writeFile(file, [...lines, "{not json"].join("\n"));
    const { evaluations, error } = await readEvaluations(file);
    expect(evaluations["HAL.NS"]).toHaveLength(20);
    expect(evaluations["HAL.NS"][0].evaluated_at).toBe("t5");
    expect(error).toMatch(/could not be read/);
  });
});
