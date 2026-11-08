"use client";

import { useState } from "react";
import { DeskTable } from "@/components/desk/desk-table";
import { ExitResearch } from "@/components/desk/exit-research";
import { PastTrades, type TradesControls } from "@/components/desk/momentum/past-trades";
import { Tabs } from "@/components/desk/tabs";
import {
  BUY_NOW_NOTE, COLUMN_GUIDE, EXIT_RULES, HOW_TO_READ, HOW_TO_READ_TITLE, type TradePeriod, type UiMomentum, type ViewKey,
} from "@/lib/desk/momentum-text";
import type { DeskColumn } from "@/lib/desk/table";

const GUIDE_COLUMNS: DeskColumn<[string, string]>[] = [
  { key: "col", label: "Column", kind: "text", priority: 1, render: (r) => <b>{r[0]}</b> },
  { key: "means", label: "What it means", kind: "text", priority: 1, render: (r) => <span style={{ whiteSpace: "normal" }}>{r[1]}</span> },
];

/** Past trades / How the model exits / What each column means. */
export function LowerTabs({ data, view }: { data: UiMomentum; view: ViewKey }) {
  const [period, setPeriod] = useState<TradePeriod>("Last 1Y");
  const [year, setYear] = useState<number | null>(data.trade_filters.years[0] ?? null);
  const [strict, setStrict] = useState(false);
  const [allCols, setAllCols] = useState(false);
  const controls: TradesControls = { period, setPeriod, year, setYear, strict, setStrict, allCols, setAllCols };
  return (
    <Tabs tabs={[
      { id: "trades", label: `Past trades (${data.views[view].trade_ids.length})`, content: <PastTrades data={data} view={view} controls={controls} /> },
      {
        id: "exits", label: "How the model exits",
        content: (
          <div className="desk-stack" style={{ gap: 10 }}>
            <p className="rd-note" style={{ margin: 0 }}>{EXIT_RULES}</p>
            <p className="rd-note" style={{ margin: 0 }}>{BUY_NOW_NOTE}</p>
            <ExitResearch rec={data.exit_rec} title="Exit research: Price strength (Momentum)" />
          </div>
        ),
      },
      {
        id: "columns", label: "What each column means",
        content: (
          <div className="desk-stack" style={{ gap: 10 }}>
            <p className="rd-note" style={{ margin: 0 }}>
              <b style={{ color: "var(--rd-text)" }}>{HOW_TO_READ_TITLE}</b><br />{HOW_TO_READ}
            </p>
            <DeskTable rows={COLUMN_GUIDE} columns={GUIDE_COLUMNS} getRowId={(r) => r[0]} caption="What each column means" />
          </div>
        ),
      },
    ]} />
  );
}
