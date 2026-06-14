"use client";

import { useState } from "react";
import { useRouter, usePathname, useSearchParams } from "next/navigation";

export function TickerPicker({ tickers, current }: { tickers: string[]; current: string }) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const [q, setQ] = useState("");

  const matches = q
    ? tickers.filter((t) => t.toLowerCase().includes(q.toLowerCase())).slice(0, 20)
    : [];

  const pick = (t: string) => {
    const next = new URLSearchParams(params.toString());
    next.set("chart", t);
    setQ("");
    router.push(`${pathname}?${next.toString()}`);
  };

  return (
    <div className="relative mb-2 max-w-xs">
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder={`Search ticker (current: ${current})`}
        className="w-full rounded border border-border bg-background px-2 py-1 text-sm"
      />
      {matches.length > 0 && (
        <ul className="absolute z-10 mt-1 max-h-60 w-full overflow-auto rounded border border-border bg-background text-sm shadow">
          {matches.map((t) => (
            <li key={t}>
              <button onClick={() => pick(t)} className="block w-full px-2 py-1 text-left hover:bg-muted/40">
                {t}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
