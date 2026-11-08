"use client";

import { createContext, useContext, useState, type ReactNode } from "react";

interface Selection { selected: string | null; select: (symbol: string) => void }

const SelectionContext = createContext<Selection | null>(null);

/** Shares the selected Monthly stock between the top 5 card and the ranking desk; mirrors it into `?ticker=`. */
export function MonthlySelectionProvider({ initial, children }: { initial: string | null; children: ReactNode }) {
  const [selected, setSelected] = useState<string | null>(initial);
  const select = (symbol: string) => {
    setSelected(symbol);
    window.history.replaceState(null, "", `?ticker=${encodeURIComponent(symbol)}`);
  };
  return <SelectionContext.Provider value={{ selected, select }}>{children}</SelectionContext.Provider>;
}

export const useMonthlySelection = () => useContext(SelectionContext);
