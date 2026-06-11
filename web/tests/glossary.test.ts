import { describe, it, expect } from "vitest";
import { GLOSSARY, glossaryTerm, glossaryLabel } from "@/lib/glossary";

describe("glossary", () => {
  it("has the core terms", () => {
    expect(GLOSSARY.CAGR.label).toMatch(/Compound Annual Growth/);
    expect(GLOSSARY.MAE.label).toMatch(/Max Adverse/);
    expect(Object.keys(GLOSSARY).length).toBe(28);
  });
  it("glossaryTerm returns explanation, falls back to key", () => {
    expect(glossaryTerm("Sharpe")).toMatch(/volatility/);
    expect(glossaryTerm("NOPE")).toBe("NOPE");
  });
  it("glossaryLabel returns full label, falls back to key", () => {
    expect(glossaryLabel("EMA220")).toMatch(/220-day/);
    expect(glossaryLabel("NOPE")).toBe("NOPE");
  });
});
