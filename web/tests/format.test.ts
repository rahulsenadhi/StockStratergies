import { describe, it, expect } from "vitest";
import { pct, signed, naDash } from "@/lib/format";

describe("format", () => {
  it("pct: positive gets +, scaled to %", () => {
    expect(pct(0.261)).toBe("+26.1%");
  });
  it("pct: negative keeps -", () => {
    expect(pct(-0.114)).toBe("-11.4%");
  });
  it("pct: null -> dash", () => {
    expect(pct(null)).toBe("—");
  });
  it("signed: fixed decimals; null -> dash", () => {
    expect(signed(2.453)).toBe("2.45");
    expect(signed(null)).toBe("—");
  });
  it("naDash: passes through or dashes null", () => {
    expect(naDash(3)).toBe("3");
    expect(naDash(null)).toBe("—");
  });
});
