import { sseFrame } from "@/lib/sse";

export type JobResult = { status: number; body: unknown };

/**
 * Run a job that may emit progress lines, streaming them as SSE `line` frames,
 * then a terminal `done` frame carrying the result body. The caller acquires the
 * job-lock BEFORE calling this and must release it inside `run`'s own finally.
 * A thrown `run` is captured as a done frame with { ok:false, error }.
 */
export function streamJob(
  run: (onLine: (line: string) => void) => Promise<JobResult>,
): Response {
  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      const enqueue = (frame: string) => {
        try {
          controller.enqueue(encoder.encode(frame));
        } catch {
          // controller closed (client gone) — ignore; job still runs to completion
        }
      };
      let body: unknown;
      try {
        const result = await run((line) => enqueue(sseFrame("line", line)));
        body = result.body;
      } catch (e) {
        body = { ok: false, error: e instanceof Error ? e.message : String(e) };
      }
      enqueue(sseFrame("done", JSON.stringify(body)));
      try {
        controller.close();
      } catch {
        // already closed
      }
    },
  });
  return new Response(stream, {
    headers: {
      "content-type": "text/event-stream; charset=utf-8",
      "cache-control": "no-cache, no-transform",
      connection: "keep-alive",
    },
  });
}
