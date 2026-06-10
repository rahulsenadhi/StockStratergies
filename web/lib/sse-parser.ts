export interface SseEvent {
  event: string;
  data: string;
}

/** Stateful parser: feed decoded text chunks, get back complete SSE events. */
export function createSseParser(): { push(chunk: string): SseEvent[] } {
  let buf = "";
  return {
    push(chunk: string): SseEvent[] {
      buf += chunk;
      const events: SseEvent[] = [];
      let idx: number;
      while ((idx = buf.indexOf("\n\n")) !== -1) {
        const raw = buf.slice(0, idx);
        buf = buf.slice(idx + 2);
        let event = "message";
        let data = "";
        for (const line of raw.split("\n")) {
          if (line.startsWith("event:")) event = line.slice(6).trim();
          else if (line.startsWith("data:")) data = line.slice(5).replace(/^ /, "");
        }
        events.push({ event, data });
      }
      return events;
    },
  };
}

/** Extract a coarse "N/M" phase from a "[N/M] …" stdout line, or null. */
export function parsePhase(line: string): string | null {
  const m = line.match(/\[(\d+)\/(\d+)\]/);
  return m ? `${m[1]}/${m[2]}` : null;
}
