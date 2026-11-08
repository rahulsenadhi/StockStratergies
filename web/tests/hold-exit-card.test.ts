import { createElement as h } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { HONESTY_NOTE, SMALL_SAMPLE_NOTE, EXIT_EMPTY, holdExitRows, type ExitRec } from "@/lib/desk/exit-text";
import { formatSigned } from "@/lib/desk/format";
import type { RankRow } from "@/lib/desk/monthly-text";

vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: () => {} }) }));
const { HoldExitCard } = await import("@/components/desk/hold-exit-card");
const { Top5Card } = await import("@/components/desk/monthly/top5-card");

const MOMENTUM: ExitRec = {
  hold_days: 65, hold_median_return: 39.55, hold_win_rate: 0.81, stop_pct: -10.1, sample_size: 31, data_quality: "ohlcv",
  targets: [{ pct: 22, book_pct: 40, hit_rate: 0.9 }, { pct: 69.9, book_pct: 30, hit_rate: 0.5 }],
};
const MONTHLY: ExitRec = {
  hold_days: 2, hold_median_return: 0.44, hold_win_rate: 0.56, stop_pct: -12.8, sample_size: 152, data_quality: "close",
};

describe("holdExitRows", () => {
  it("formats the Momentum saved rec", () => {
    const r = holdExitRows(MOMENTUM);
    expect(r.hold).toBe("65 days");
    expect(r.winRate).toBe("81%");
    expect(r.median).toBe(`${formatSigned(39.55, 1)}%`);
    expect(r.stop).toBe("-10.1%");
    expect(r.basis).toBe("Based on 31 past trades");
    expect(r.isSmallSample).toBe(false);
    expect(r.lossPct).toBe(19);
    expect(r.targets[0]).toMatchObject({ tier: "T1", target: "+22.0%", book: "40%", hit: "90%" });
  });
  it("flags a small sample under 30 and handles missing numbers", () => {
    expect(holdExitRows({ ...MOMENTUM, sample_size: 29 }).isSmallSample).toBe(true);
    const r = holdExitRows({ ...MONTHLY, hold_win_rate: null, sample_size: null });
    expect(r.winRate).toBe("—");
    expect(r.lossPct).toBeNull();
    expect(r.basis).toBe("Based on — past trades");
  });
});

describe("HONESTY_NOTE", () => {
  it("states past results are not a promise", () => {
    expect(HONESTY_NOTE(19)).toBe("Past results, not a promise. At the suggested hold, 19% of past trades still lost money.");
    expect(HONESTY_NOTE(19)).not.toMatch(/no loss|guarantee|100%/i);
  });
});

describe("HoldExitCard", () => {
  it("shows Streamlit's empty text for a null rec", () => {
    expect(renderToStaticMarkup(h(HoldExitCard, { rec: null, title: "t" }))).toContain(EXIT_EMPTY);
  });
  it("renders the rows, targets, honesty note and extra rows", () => {
    const html = renderToStaticMarkup(h(HoldExitCard, { rec: MOMENTUM, title: "Hold and exit plan: Momentum",
      extra: [{ label: "Trades in profit at exit", value: "81% of 31" }] }));
    for (const s of ["Hold and exit plan: Momentum", "Suggested hold", "65 days", "Success rate at that hold", "81%",
      "Median return at that hold", "Sell plan", "Sell at", "Sell this much", "Hit before (hist.)", "Stop level", "-10.1%",
      "Based on 31 past trades", HONESTY_NOTE(19), "Trades in profit at exit", "81% of 31"]) {
      expect(html).toContain(s);
    }
    expect(html).not.toContain(SMALL_SAMPLE_NOTE);
    expect(html).not.toMatch(/no loss|guarantee/i);
  });
  it("warns on a small sample and omits the targets table when none are saved", () => {
    const html = renderToStaticMarkup(h(HoldExitCard, { rec: { ...MONTHLY, sample_size: 12 }, title: "t" }));
    expect(html).toContain(SMALL_SAMPLE_NOTE);
    expect(html).not.toContain("<table");
    expect(html).toContain(HONESTY_NOTE(44));
  });
});

describe("Top5Card", () => {
  const row = (rank: number, symbol: string): RankRow => ({
    rank, ticker: `${symbol}.NS`, symbol, company: `${symbol} Ltd`, price: 100 + rank, month_ret: 3, bench_ret: 1, rs: 2, label: "Strong BUY",
  });
  const ranking = ["BAJFINANCE", "M&M", "HDFCBANK", "RELIANCE", "ULTRACEMCO", "ZZZ"].map((s, i) => row(i + 1, s));
  it("shows five rows in rank order with the sub-line", () => {
    const html = renderToStaticMarkup(h(Top5Card, { ranking, top5: ["BAJFINANCE", "M&M", "HDFCBANK", "RELIANCE", "ULTRACEMCO"], onSelect: () => {} }));
    expect(html).toContain("Model&#x27;s top 5 for this month");
    expect(html).toContain("A model list, not an instruction.");
    const order = ["BAJFINANCE Ltd", "M&amp;M Ltd", "HDFCBANK Ltd", "RELIANCE Ltd", "ULTRACEMCO Ltd"].map((s) => html.indexOf(s));
    expect(order.every((i) => i >= 0)).toBe(true);
    expect([...order].sort((a, b) => a - b)).toEqual(order);
    expect(html).not.toContain("ZZZ Ltd");
  });
});

describe("holdExitExtras", () => {
  it("follows the health numbers of the current view", async () => {
    const { holdExitExtras } = await import("@/lib/desk/momentum-text");
    const rows = holdExitExtras({ win_rate: 81, n_trades: 31, safe_20d_pct: 74 } as never);
    expect(rows).toEqual([
      { label: "Trades in profit at exit", value: "81% of 31" },
      { label: "Stayed above entry 20+ days", value: "74%" },
    ]);
    expect(holdExitExtras({ win_rate: null, n_trades: null, safe_20d_pct: null } as never)[0].value).toBe("—");
  });
});
