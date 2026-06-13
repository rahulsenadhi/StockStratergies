import { describe, it, expect } from "vitest";
import { filterScreener, sectorsOf, toCsv } from "@/lib/pead-screener";
import type { PeadScreenerRow } from "@/lib/data/strategies";

const row = (over: Partial<PeadScreenerRow>): PeadScreenerRow => ({
  ticker: "X.NS",
  sector: "Energy",
  resultDate: "2026-03-31",
  periodType: "Q",
  sue: 1,
  sueDecile: 8,
  epsActual: 10,
  epsExpected: 8,
  piotroski: 6,
  pb: 3,
  pbSectorMedian: 2,
  qualifiesLong: true,
  ...over,
});

describe("filterScreener", () => {
  const rows = [
    row({ ticker: "A", sue: 2, piotroski: 7, pb: 3, sector: "Energy" }),
    row({ ticker: "B", sue: -1, piotroski: 7, pb: 3, sector: "Energy" }), // sue too low
    row({ ticker: "C", sue: 2, piotroski: 3, pb: 3, sector: "IT" }), // pio too low
    row({ ticker: "D", sue: 2, piotroski: 7, pb: 12, sector: "IT" }), // pb too high
    row({ ticker: "E", sue: null, piotroski: 7, pb: 3, sector: "IT" }), // null sue
  ];

  it("applies SUE/Piotroski/P-B thresholds", () => {
    const out = filterScreener(rows, { sueMin: 0, pioMin: 5, pbMax: 10, sectors: [] });
    expect(out.map((r) => r.ticker)).toEqual(["A"]);
  });

  it("excludes null SUE/Piotroski/P-B rows", () => {
    const out = filterScreener([row({ ticker: "N", pb: null })], {
      sueMin: -5,
      pioMin: 0,
      pbMax: 100,
      sectors: [],
    });
    expect(out).toHaveLength(0);
  });

  it("filters by sector when provided", () => {
    const out = filterScreener(rows, { sueMin: -5, pioMin: 0, pbMax: 100, sectors: ["IT"] });
    expect(out.every((r) => r.sector === "IT")).toBe(true);
    expect(out.map((r) => r.ticker).sort()).toEqual(["C", "D"]);
  });
});

describe("sectorsOf", () => {
  it("returns distinct sorted non-null sectors", () => {
    expect(
      sectorsOf([row({ sector: "IT" }), row({ sector: "Energy" }), row({ sector: null }), row({ sector: "IT" })]),
    ).toEqual(["Energy", "IT"]);
  });
});

describe("toCsv", () => {
  it("emits a header + escaped rows", () => {
    const csv = toCsv([row({ ticker: "A,B", sector: 'He said "hi"', pb: null })]);
    const [header, line] = csv.split("\n");
    expect(header.startsWith("ticker,sector,resultDate")).toBe(true);
    expect(line).toContain('"A,B"');
    expect(line).toContain('"He said ""hi"""');
    expect(line).toContain(",,"); // null pb -> empty cell
  });
});
