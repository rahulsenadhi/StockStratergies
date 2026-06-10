import { describe, it, expect } from "vitest";
import { sseFrame } from "@/lib/sse";

describe("sseFrame", () => {
  it("formats an event + data frame terminated by a blank line", () => {
    expect(sseFrame("line", "hello")).toBe("event: line\ndata: hello\n\n");
  });
  it("passes JSON data through verbatim (single line)", () => {
    expect(sseFrame("done", '{"ok":true}')).toBe('event: done\ndata: {"ok":true}\n\n');
  });
});
