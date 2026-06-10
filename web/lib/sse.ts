/**
 * Format a single Server-Sent Events frame. `data` must be a single line
 * (stdout lines are split before framing; JSON has no embedded newlines).
 */
export function sseFrame(event: string, data: string): string {
  return `event: ${event}\ndata: ${data}\n\n`;
}
