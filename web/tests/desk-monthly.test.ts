import { describe, expect, test } from "vitest";
import { execFileSync } from "node:child_process";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { bigValueParts, formatNumber, formatRupees, formatSigned, pyFixed } from "@/lib/desk/format";
import {
  benchSub, cagrText, cagrTone, exitTexts, loadMonthly, rankCells, rankStatus, rankSub, rankingAge,
  rebalanceCells, resolveSelected, summaryStats, MONTHLY_FILTERS, HOW_IT_WORKS,
  type MonthlySummary, type RankRow,
} from "@/lib/desk/monthly";

const row = (rank: number, symbol: string): RankRow => ({
  rank, ticker: `${symbol}.NS`, symbol, company: symbol, price: 100, month_ret: 1, bench_ret: 1, rs: 0, label: "Hold",
});

describe("format additions", () => {
  test("formatSigned / formatRupees / bigValueParts", () => {
    expect(formatSigned(20.94, 1)).toBe("+20.9");
    expect(formatSigned(-4.93, 2)).toBe("-4.93");
    expect(formatRupees(1087.75, 2)).toBe("₹1,087.75");
    expect(formatRupees(91013.4, 0)).toBe("₹91,013");
    expect(bigValueParts("+20.9%")).toEqual({ head: "+20", dec: ".9%" });
    expect(bigValueParts("—")).toEqual({ head: "—", dec: null });
  });
});

describe("monthly mappers", () => {
  const rows = [row(1, "BAJFINANCE"), row(2, "HAL"), row(3, "M&M"), row(4, "BAJAJ-AUTO")];

  test("resolveSelected", () => {
    expect(resolveSelected(rows, "BAJFINANCE", "HAL")).toBe("HAL");
    expect(resolveSelected(rows, "BAJFINANCE", "HAL.NS")).toBe("HAL");
    expect(resolveSelected(rows, "BAJFINANCE", "M&M")).toBe("M&M");
    expect(resolveSelected(rows, "BAJFINANCE", "BAJAJ-AUTO")).toBe("BAJAJ-AUTO");
    for (const bad of ["ZZZ", "", null, undefined]) expect(resolveSelected(rows, "BAJFINANCE", bad)).toBe("BAJFINANCE");
    expect(resolveSelected(rows, null, "ZZZ")).toBe("BAJFINANCE");
    expect(resolveSelected([], null, "HAL")).toBeNull();
  });

  const summary: MonthlySummary = {
    cagr: 20.94, total_ret: 79.8, max_dd: -12.34, start: "a", end: "b",
    bench_ret: 26.1, bench_cagr: 8.0, alpha: 12.94, n_months: 36,
  };

  test("summaryStats", () => {
    expect(summaryStats(summary)).toEqual([
      { label: "Extra vs Nifty", value: "+12.9% / yr", tone: "gain" },
      { label: "Total return", value: "+79.8%", tone: "info" },
      { label: "Nifty total", value: "+26.1%", tone: "muted" },
      { label: "Worst fall from a peak", value: "-12.3%", tone: "loss" },
      { label: "Sample", value: "36 monthly rebalances", tone: "muted" },
    ]);
    expect(summaryStats({ ...summary, n_months: null })[4].value).toBe("—");
    expect(summaryStats({ ...summary, alpha: -1 })[0].tone).toBe("loss");
    expect(cagrText(summary)).toBe("+20.9%");
    expect(cagrTone(summary)).toBe("gain");
    expect(cagrTone({ ...summary, cagr: -1 })).toBe("loss");
    expect(benchSub(summary)).toBe("vs Nifty +8.0% per year, same period");
  });

  test("rank sub, status, age and cells", () => {
    expect(rankSub(row(3, "HAL"))).toBe("HAL · top 5 candidate");
    expect(rankSub(row(12, "HAL"))).toBe("HAL");
    expect(rankStatus(row(3, "X"), 50)).toEqual({ label: "Top-5 candidate", tone: "info" });
    expect(rankStatus(row(12, "X"), 50)).toEqual({ label: "Rank 12 of 50", tone: "muted" });
    expect(rankingAge(3)).toEqual({ label: "Ranking 3 days old", tone: "gain" });
    expect(rankingAge(null)).toEqual({ label: "Ranking no saved file", tone: "muted" });
    expect(rankCells({ ...row(1, "HAL"), price: 1087.75, month_ret: -4.93, rs: 7.715 })).toMatchObject({
      price: "₹1,087.75", move: { text: "↘ 4.93%", direction: "down" }, rs: "+7.71%",
    });
    expect(rebalanceCells({ date: "d", top5: "a", bought: "b", sold: "c", value: 91013.4 })[4]).toBe("₹91,013");
  });

  test("exitTexts", () => {
    const t = exitTexts({
      hold_days: 2, hold_median_return: 0.44, hold_win_rate: 0.56,
      targets: [{ pct: 7.6, book_pct: 40, hit_rate: 0.6 }], stop_pct: -12.8, sample_size: 152, data_quality: "close",
    });
    expect(t).toMatchObject({ hold: "2 days", median: "0.4%", winRate: "56%" });
    expect(t.targets[0]).toEqual({ tier: "T1", target: "+7.6%", book: "40%", hit: "60%" });
    expect(t.caption).toContain("-12.8%");
    expect(t.caption).toContain("152 trades");
    expect(t.caption).toContain("close-only (approx.)");
  });

  test("constants", () => {
    expect(MONTHLY_FILTERS).toEqual(["All 50", "Top 5", "Beating Nifty", "Lagging Nifty"]);
    expect(HOW_IT_WORKS.filter((s) => s.bold).map((s) => s.text)).toEqual(["How it works:", "RS Score"]);
  });
});

describe("loadMonthly", () => {
  const withDir = async (content: string | null) => {
    const dir = await fs.mkdtemp(path.join(os.tmpdir(), "monthly-"));
    if (content !== null) await fs.writeFile(path.join(dir, "ui_monthly.json"), content);
    return dir;
  };

  test("missing, invalid, version and ok", async () => {
    expect(await loadMonthly(await withDir(null))).toEqual({ ok: false, reason: "missing" });
    expect(await loadMonthly(await withDir("{"))).toEqual({ ok: false, reason: "invalid" });
    expect(await loadMonthly(await withDir('{"version":2}'))).toEqual({ ok: false, reason: "version" });
    const valid = {
      version: 1, generated_at: "x", colour: "#fff", summary: null, chart: null, ranking: [], filters: {},
      default_symbol: null, top5: [], closes: {}, rebalances: { total: 0, rows: [] }, checks: [], exit_rec: null,
    };
    const res = await loadMonthly(await withDir(JSON.stringify(valid)));
    expect(res.ok).toBe(true);
  });
});

// Integration: the Next.js text for the saved Monthly files equals what Streamlit renders.
const PY = process.env.PYTHON_BIN;
describe.skipIf(!PY)("Monthly parity with Streamlit", () => {
  test("summary, ranking rows and rebalance rows match", async () => {
    const cwd = path.resolve(process.cwd(), process.env.DATA_DIR ?? "..");
    const py = path.resolve(process.cwd(), PY!);
    const env = { ...process.env, PYTHONIOENCODING: "utf-8" };
    execFileSync(py, ["precompute_ui_monthly.py"], { cwd, env, stdio: "ignore" });
    const script = path.resolve(process.cwd(), "tests/parity/monthly_streamlit_text.py");
    const out = execFileSync(py, [script], { cwd, env, encoding: "utf-8", stdio: ["ignore", "pipe", "ignore"] });
    const expected = JSON.parse(out.trim().split(/\r?\n/).pop() ?? "{}");

    const res = await loadMonthly(cwd);
    expect(res.ok).toBe(true);
    if (!res.ok) return;
    const d = res.data;
    expect(d.summary).not.toBeNull();
    const s = d.summary!;
    expect(bigValueParts(cagrText(s))).toEqual(expected.summary.big);
    expect(benchSub(s)).toBe(expected.summary.sub);
    expect(summaryStats(s).map((r) => [r.label, r.value, r.tone])).toEqual(expected.summary.bars);
    expect(d.ranking.map((r) => {
      const c = rankCells(r);
      return [c.rank, c.company, c.sub, c.price, c.move.text, c.rs, c.label];
    })).toEqual(expected.ranking);
    expect(d.rebalances.rows.map(rebalanceCells)).toEqual(expected.rebalances);
  }, 180_000);
});

describe("pyFixed matches Python round-half-even on exact ties", () => {
  test("ties and non-ties", () => {
    expect(pyFixed(3.125, 2)).toBe("3.12");
    expect(pyFixed(3.375, 2)).toBe("3.38");
    expect(pyFixed(0.5, 0)).toBe("0");
    expect(pyFixed(2.5, 0)).toBe("2");
    expect(pyFixed(-3.125, 2)).toBe("-3.12");
    expect(pyFixed(1.005, 2)).toBe("1.00");
    expect(formatRupees(4785.125, 2)).toBe("₹4,785.12");
  });
});

describe("pyFixed signs and grouping match Python", () => {
  test("negative zero, tiny negatives and grouped negatives", () => {
    expect(pyFixed(-0, 2)).toBe("-0.00"); // Python format(-0.0, '.2f')
    expect(pyFixed(-0.001, 2)).toBe("-0.00"); // Python format(-0.001, '.2f')
    expect(formatSigned(-0, 1)).toBe("-0.0");
    expect(formatNumber(-1234567.5, 2)).toBe("-1,234,567.50"); // Python f"{-1234567.5:,.2f}"
  });
});
