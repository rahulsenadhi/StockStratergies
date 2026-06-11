import { describe, it, expect } from "vitest";
import { validateDryrunBody } from "@/lib/dryrun-validate";

describe("validateDryrunBody", () => {
  it("accepts a non-empty formula and trims it; defaults universe", () => {
    const r = validateDryrunBody({ entry_formula: "  rsi_14 > 70  " });
    expect(r).toEqual({ ok: true, formula: "rsi_14 > 70", universe: "Nifty 50" });
  });
  it("keeps a provided universe", () => {
    const r = validateDryrunBody({ entry_formula: "x > 1", universe: "Nifty 500" });
    expect(r).toEqual({ ok: true, formula: "x > 1", universe: "Nifty 500" });
  });
  it("rejects an empty/whitespace formula", () => {
    expect(validateDryrunBody({ entry_formula: "   " })).toEqual({ ok: false, error: "entry_formula is required" });
  });
  it("rejects a missing/non-string formula", () => {
    expect(validateDryrunBody({})).toEqual({ ok: false, error: "entry_formula is required" });
    expect(validateDryrunBody({ entry_formula: 42 })).toEqual({ ok: false, error: "entry_formula is required" });
  });
});
