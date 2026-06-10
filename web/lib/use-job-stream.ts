"use client";

import { createSseParser, parsePhase } from "@/lib/sse-parser";

export interface JobStreamHandlers {
  onLine?: (line: string) => void;
  onPhase?: (phase: string) => void;
}

export interface JobStreamResult {
  ok: boolean;
  status: number;
  data: Record<string, unknown>;
}

/**
 * POST to `url`, then read the SSE stream, invoking handlers per progress line,
 * and resolve with the terminal `done` payload. Non-stream responses (validation
 * errors / 409) are returned as plain JSON.
 */
export async function runJobStream(
  url: string,
  body?: unknown,
  handlers: JobStreamHandlers = {},
): Promise<JobStreamResult> {
  const res = await fetch(url, {
    method: "POST",
    headers: body !== undefined ? { "content-type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  const ctype = res.headers.get("content-type") ?? "";
  if (!ctype.includes("text/event-stream") || !res.body) {
    const data = (await res.json().catch(() => ({}))) as Record<string, unknown>;
    return { ok: res.ok, status: res.status, data };
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  const parser = createSseParser();
  let done: Record<string, unknown> | null = null;

  for (;;) {
    const { value, done: finished } = await reader.read();
    if (finished) break;
    for (const ev of parser.push(decoder.decode(value, { stream: true }))) {
      if (ev.event === "line") {
        handlers.onLine?.(ev.data);
        const ph = parsePhase(ev.data);
        if (ph) handlers.onPhase?.(ph);
      } else if (ev.event === "done") {
        try {
          done = JSON.parse(ev.data) as Record<string, unknown>;
        } catch {
          done = { ok: false, error: "bad done frame" };
        }
      }
    }
  }

  const data = done ?? { ok: false, error: "stream ended without result" };
  return { ok: data.ok === true, status: 200, data };
}
