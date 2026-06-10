import { describe, it, expect } from "vitest";
import { streamJob } from "@/lib/job-stream";

describe("streamJob", () => {
  it("streams line frames then a done frame with the result body", async () => {
    const res = streamJob(async (onLine) => {
      onLine("Loading");
      onLine("[1/5] x");
      return { status: 200, body: { ok: true, ran: ["a"] } };
    });
    expect(res.headers.get("content-type")).toContain("text/event-stream");
    const text = await res.text();
    expect(text).toContain("event: line\ndata: Loading\n\n");
    expect(text).toContain("event: line\ndata: [1/5] x\n\n");
    expect(text).toContain('event: done\ndata: {"ok":true,"ran":["a"]}\n\n');
  });

  it("a thrown run becomes a done frame with ok:false", async () => {
    const res = streamJob(async () => {
      throw new Error("kaboom");
    });
    const text = await res.text();
    expect(text).toContain('event: done\ndata: {"ok":false,"error":"kaboom"}\n\n');
  });
});
