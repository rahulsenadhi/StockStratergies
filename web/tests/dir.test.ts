import { describe, it, expect } from "vitest";
import { upDown } from "@/lib/dir";

describe("upDown", () => {
  it("returns text-up for positive numbers", () => {
    expect(upDown(1)).toBe("text-up");
  });

  it("returns text-down for negative numbers", () => {
    expect(upDown(-1)).toBe("text-down");
  });

  it("returns text-muted-foreground for zero", () => {
    expect(upDown(0)).toBe("text-muted-foreground");
  });

  it("returns text-muted-foreground for null", () => {
    expect(upDown(null)).toBe("text-muted-foreground");
  });

  it("returns text-muted-foreground for undefined", () => {
    expect(upDown(undefined)).toBe("text-muted-foreground");
  });

  it("returns text-muted-foreground for NaN", () => {
    expect(upDown(NaN)).toBe("text-muted-foreground");
  });
});
