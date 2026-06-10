import { describe, it, expect, vi, afterEach } from "vitest";
import { runJobStream } from "@/lib/use-job-stream";

function streamResponse(frames: string[]): Response {
  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const f of frames) controller.enqueue(encoder.encode(f));
      controller.close();
    },
  });
  return new Response(stream, { headers: { "content-type": "text/event-stream" } });
}

afterEach(() => vi.restoreAllMocks());

describe("runJobStream", () => {
  it("invokes onLine/onPhase and resolves with the done payload", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        streamResponse([
          "event: line\ndata: [3/5] x\n\n",
          'event: done\ndata: {"ok":true,"ran":["a"]}\n\n',
        ]),
      ),
    );
    const lines: string[] = [];
    const phases: string[] = [];
    const res = await runJobStream("/api/x", { id: "a" }, {
      onLine: (l) => lines.push(l),
      onPhase: (p) => phases.push(p),
    });
    expect(lines).toEqual(["[3/5] x"]);
    expect(phases).toEqual(["3/5"]);
    expect(res.ok).toBe(true);
    expect(res.data).toEqual({ ok: true, ran: ["a"] });
  });

  it("returns the JSON body for a non-stream response (e.g. 409)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ ok: false, error: "A job is already running" }), {
          status: 409,
          headers: { "content-type": "application/json" },
        }),
      ),
    );
    const res = await runJobStream("/api/x", { id: "a" });
    expect(res.status).toBe(409);
    expect(res.ok).toBe(false);
    expect(res.data).toEqual({ ok: false, error: "A job is already running" });
  });
});
