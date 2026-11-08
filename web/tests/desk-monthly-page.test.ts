import { createElement as h } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { MonthlyResult } from "@/lib/desk/monthly";
import {
  EMPTY_NO_RANKING, EMPTY_NO_REBALANCE, EMPTY_NO_SIMULATION, EXIT_EMPTY, FOOTER_CAPTION, MONTHLY_TITLE,
  emptyNoPrices, type RankRow, type UiMonthly,
} from "@/lib/desk/monthly-text";

const load = vi.hoisted(() => ({ result: null as MonthlyResult | null }));
vi.mock("@/lib/desk/monthly", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/desk/monthly")>()),
  loadMonthly: async () => load.result,
}));

const { default: MonthlyPage } = await import("@/app/monthly/page");
const { RankingDesk } = await import("@/components/desk/monthly/ranking-desk");
const { SummaryCard } = await import("@/components/desk/monthly/summary-card");
const { ExitResearch, LowerTabs } = await import("@/components/desk/monthly/lower-tabs");

const row = (rank: number, symbol: string, company: string): RankRow => ({
  rank, ticker: `${symbol}.NS`, symbol, company, price: 100 + rank, month_ret: 5 - rank, bench_ret: 1, rs: 4 - rank,
  label: rank <= 5 ? "Strong BUY" : "Weak",
});
const RANKING = [row(1, "AAA", "Alpha Ltd"), row(2, "BBB", "Beta Ltd"), row(6, "HAL", "Hindustan Aeronautics")];
const FILTERS = { "All 50": ["AAA", "BBB", "HAL"], "Top 5": ["AAA", "BBB"], "Beating Nifty": ["AAA", "BBB"], "Lagging Nifty": ["HAL"] };

function data(overrides: Partial<UiMonthly> = {}): UiMonthly {
  return {
    version: 1, generated_at: "2026-11-07T00:00:00", colour: "#7c9cff",
    summary: { cagr: 20, total_ret: 72.9, max_dd: -12.7, start: "2023-11-30", end: "2026-11-30",
      bench_ret: 28, bench_cagr: 8.6, alpha: 11.4, n_months: 36 },
    chart: { "1Y": [], "3Y": [], All: [{ name: "Monthly Rotation", colour: "#7c9cff", dash: false, points: [["2024-01-31", 0]] }] },
    ranking: RANKING, filters: FILTERS, default_symbol: "AAA", top5: ["AAA", "BBB"],
    closes: { AAA: { saved_to: "06 Nov 2026", points: [["2026-11-06", 101]] } },
    rebalances: { total: 1, rows: [{ date: "2026-11-30", top5: "AAA, BBB", bought: "AAA", sold: "—", value: 86444.4 }] },
    checks: [], exit_rec: null,
    ...overrides,
  };
}

const page = async (search: Record<string, string>) =>
  renderToStaticMarkup(await MonthlyPage({ searchParams: Promise.resolve(search) }));
const selectedRow = (html: string) => html.match(/<tr class="rd-tr rd-tr--sel"[^>]*>(.*?)<\/tr>/)?.[1] ?? "";

describe("/monthly page", () => {
  beforeEach(() => { load.result = { ok: true, data: data() }; });

  it("selects ?ticker= when it is in the ranking, with or without .NS", async () => {
    expect(selectedRow(await page({ ticker: "HAL" }))).toContain("Hindustan Aeronautics");
    expect(selectedRow(await page({ ticker: "BBB.NS" }))).toContain("Beta Ltd");
  });

  it("falls back to the default symbol for an unknown ticker instead of crashing", async () => {
    const html = await page({ ticker: "NOPE<script>" });
    expect(selectedRow(html)).toContain("Alpha Ltd");
    expect(html).not.toContain("NOPE<script>");
  });

  it("renders every section in Streamlit order", async () => {
    const html = await page({});
    const order = [MONTHLY_TITLE, "Result context", "Avg yearly return (CAGR)", "Saved ranking", "role=\"tablist\"",
      "Historical simulation", FOOTER_CAPTION, "Glossary"].map((s) => html.indexOf(s));
    expect(order.every((i) => i >= 0)).toBe(true);
    expect([...order].sort((a, b) => a - b)).toEqual(order);
  });

  it("shows the not-ready state naming ui_monthly.json when the file cannot be loaded", async () => {
    load.result = { ok: false, reason: "missing" };
    const html = await page({});
    expect(html).toContain(MONTHLY_TITLE);
    expect(html).toContain("ui_monthly.json");
    expect(html).not.toContain("Saved ranking");
  });

  it("with no simulation shows the empty state plus the ranking only (Streamlit returns early)", async () => {
    load.result = { ok: true, data: data({ summary: null }) };
    const html = await page({});
    expect(html).toContain(EMPTY_NO_SIMULATION.title);
    expect(html).toContain("Alpha Ltd");
    expect(html).not.toContain("role=\"tablist\"");
    expect(html).not.toContain("Result context");
  });
});

describe("Monthly sections with partial data", () => {
  it("summary keeps its figures when the chart is missing", () => {
    const html = renderToStaticMarkup(h(SummaryCard, { summary: data().summary!, chart: null }));
    expect(html).toContain("+20<span class=\"rd-big__dec\">.0%</span>");
    expect(html).toContain(EMPTY_NO_SIMULATION.title);
  });

  it("rail shows the no-price state when the selected stock has no saved closes", () => {
    const html = renderToStaticMarkup(h(RankingDesk, {
      ranking: RANKING, filters: FILTERS, initialSelected: "HAL", closes: {}, top5: ["AAA", "BBB"], colour: "#7c9cff",
    }));
    expect(html).toContain(emptyNoPrices("HAL.NS").reason);
    expect(html).toContain("Rank 6 of 3");
    expect(html).toContain("class=\"desk-rail");
  });

  it("an empty ranking shows the no-ranking state and no rail", () => {
    const html = renderToStaticMarkup(h(RankingDesk, {
      ranking: [], filters: FILTERS, initialSelected: null, closes: {}, top5: [], colour: "#7c9cff",
    }));
    expect(html).toContain(EMPTY_NO_RANKING.title);
    expect(html).not.toContain("desk-rail");
  });

  it("rebalance tab shows its empty state and exit research its no-rec text", () => {
    const tabs = renderToStaticMarkup(h(LowerTabs, {
      rebalances: { total: 0, rows: [] }, checks: [], exitRec: null, colour: "#7c9cff",
    }));
    expect(tabs).toContain(EMPTY_NO_REBALANCE.title);
    expect(renderToStaticMarkup(h(ExitResearch, { rec: null }))).toContain(EXIT_EMPTY);
  });
});
