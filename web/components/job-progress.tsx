"use client";

import { useState } from "react";

interface JobProgressProps {
  phase: string | null;
  lines: string[];
}

/** Live progress display: latest line + coarse phase, with a collapsible mini-log. */
export function JobProgress({ phase, lines }: JobProgressProps) {
  const [open, setOpen] = useState(false);
  const latest = lines.length > 0 ? lines[lines.length - 1] : "";
  if (lines.length === 0 && !phase) return null;
  return (
    <div className="flex flex-col items-end gap-1 text-sm text-muted-foreground">
      <span className="font-mono">
        {phase ? `[${phase}] ` : ""}
        {latest}
      </span>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="text-xs underline"
      >
        {open ? "hide log" : "show log"}
      </button>
      {open && (
        <pre className="max-h-40 w-80 overflow-auto rounded border bg-muted p-2 text-left text-xs">
          {lines.slice(-10).join("\n")}
        </pre>
      )}
    </div>
  );
}
