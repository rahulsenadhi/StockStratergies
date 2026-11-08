"use client";

import { DeskTable, NameCell } from "@/components/desk/desk-table";
import { ChangePill, SectionHead } from "@/components/desk/primitives";
import { useMonthlySelection } from "@/components/desk/monthly/selection";
import { TOP5_CARD_SUB, TOP5_CARD_TITLE, rankCells, type RankRow } from "@/lib/desk/monthly-text";
import type { DeskColumn } from "@/lib/desk/table";

const COLUMNS: DeskColumn<RankRow>[] = [
  { key: "rank", label: "#", kind: "num", priority: 1, render: (r) => rankCells(r).rank },
  { key: "company", label: "Company", kind: "name", priority: 1,
    render: (r) => { const c = rankCells(r); return <NameCell title={c.company} sub={c.sub} />; } },
  { key: "price", label: "Price", kind: "num", priority: 2, render: (r) => rankCells(r).price },
  { key: "move", label: "Month move", kind: "num", priority: 1, render: (r) => <ChangePill value={r.month_ret} /> },
  { key: "rs", label: "RS score", kind: "num", priority: 1, render: (r) => rankCells(r).rs },
];

/** The stocks the model would hold this month, in saved top 5 order. */
export function Top5Card({ ranking, top5, onSelect }: { ranking: RankRow[]; top5: string[]; onSelect?: (symbol: string) => void }) {
  const sel = useMonthlySelection();
  const pick = onSelect ?? sel?.select;
  const rows = top5
    .map((s) => ranking.find((r) => r.symbol === s))
    .filter((r): r is RankRow => r !== undefined);
  if (rows.length === 0) return null;
  return (
    <section className="desk-stack" style={{ gap: 6 }} aria-label={TOP5_CARD_TITLE}>
      <SectionHead title={TOP5_CARD_TITLE} />
      <p className="rd-note" style={{ margin: 0 }}>{TOP5_CARD_SUB}</p>
      <DeskTable rows={rows} columns={COLUMNS} getRowId={(r) => r.symbol} caption={TOP5_CARD_TITLE}
        selectedId={sel?.selected ?? null} onRowClick={pick ? (r) => pick(r.symbol) : undefined} />
    </section>
  );
}
