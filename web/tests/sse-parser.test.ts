import { describe, it, expect } from "vitest";
import { createSseParser, parsePhase } from "@/lib/sse-parser";

describe("createSseParser", () => {
  it("parses a complete frame", () => {
    const p = createSseParser();
    expect(p.push("event: line\ndata: hello\n\n")).toEqual([
      { event: "line", data: "hello" },
    ]);
  });

  it("buffers a frame split across two chunks", () => {
    const p = createSseParser();
    expect(p.push("event: do")).toEqual([]);
    expect(p.push('ne\ndata: {"ok":true}\n\n')).toEqual([
      { event: "done", data: '{"ok":true}' },
    ]);
  });

  it("parses multiple frames in one chunk", () => {
    const p = createSseParser();
    expect(p.push("event: line\ndata: a\n\nevent: line\ndata: b\n\n")).toEqual([
      { event: "line", data: "a" },
      { event: "line", data: "b" },
    ]);
  });
});

describe("parsePhase", () => {
  it("extracts N/M from a [N/M] marker", () => {
    expect(parsePhase("[3/5] Computing indicators")).toBe("3/5");
  });
  it("returns null when there is no marker", () => {
    expect(parsePhase("Validated 200/963")).toBeNull();
  });
});
