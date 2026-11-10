"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { purchaseHref } from "@/lib/desk/portfolio-text";
import { EmptyState, SectionHead, StatusPill } from "@/components/desk/primitives";
import { RailChart } from "@/components/desk/momentum/rail-chart";
import { STREAMLIT_URL } from "@/lib/desk/nav";
import { OLD_APP_LINK, exchangeOf, conditionTitle as conditionTitleOf, signalCells, type SignalRow, type StockDetail } from "@/lib/desk/momentum-text";
import type { Tone } from "@/lib/desk/format";

export function signalTone(signal: string): Tone {
  if (signal === "Breakout Today") return "gain";
  if (signal === "Near Breakout") return "warn";
  if (signal === "Watch Zone") return "info";
  return "muted";
}

function Row({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="rd-li">
      <span className="rd-li__sub">{title}</span>
      <span className="rd-li__val">{children}</span>
    </div>
  );
}

export interface RailStock {
  symbol: string;
  company: string;
  price: string;
  pillLabel: string;
  pillTone: Tone;
  stop: string;
  signal: SignalRow | null;
}

/** Right rail: the chosen stock, its saved 90-session chart, the seven checks and a few facts. */
export function StockRail({ stock, detail, colour }: { stock: RailStock; detail: StockDetail | undefined; colour: string }) {
  const conditions = detail?.conditions ?? null;
  const passed = conditions?.filter((c) => c.ok).length ?? 0;
  const chart = detail?.chart ?? null;
  const caption = chart ? `Closing price · last ${chart.close.length} sessions (saved to ${chart.saved_to})` : "";
  const cells = stock.signal ? signalCells(stock.signal) : null;
  const earlier = stock.signal?.hist_win == null || !cells ? "—" : `won ${cells.histWin} · avg ${cells.histAvg}`;

  return (
    <>
      <section className="rd-list" aria-label={`${stock.company} detail`}>
        <div className="rd-li"><Link className="desk-btn" href={purchaseHref(stock.symbol, stock.signal ? `momentum_edge:${stock.symbol}:${stock.signal.signal}` : undefined)}>I bought this</Link></div>
        <div className="rd-li"><span className="rd-li__sub">{`${stock.symbol} · ${exchangeOf(stock.symbol)}`}</span></div>
        <div className="rd-li"><span className="desk-rail__title">{stock.company}</span></div>
        <div className="rd-li">
          <span className="rd-li__val" style={{ fontSize: "var(--rd-fs-lg)", fontWeight: 600 }}>{stock.price}</span>
          <StatusPill label={stock.pillLabel} tone={stock.pillTone} />
        </div>
      </section>
      <div className="desk-card" style={{ padding: "10px 12px" }}>
        {chart && chart.close.length > 0 ? (
          <>
            <div className="rd-stat-label">{caption}</div>
            <RailChart key={stock.symbol} chart={chart} colour={colour} label={caption} />
          </>
        ) : (
          <EmptyState title="No saved prices for this stock" />
        )}
      </div>
      <section className="rd-list" aria-label="Why it is on the list">
        <SectionHead title="Why it is on the list" meta={conditions ? `${passed} of 7 pass` : undefined} />
        {conditions ? conditions.map((c) => (
          <div className="rd-li" key={c.label}>
            <span className="rd-li__main">
              <span className="rd-li__title" style={{ whiteSpace: "normal" }}>{conditionTitleOf(c.label)}</span>
              <span className="rd-li__sub">{`${c.label} · ${c.detail}`}</span>
            </span>
            <StatusPill label={c.ok ? "Pass" : "Fail"} tone={c.ok ? "gain" : "loss"} />
          </div>
        )) : <EmptyState title={detail?.note ?? "No condition check is saved for this stock"} />}
        <Row title="Suggested stop">{stock.stop}</Row>
        <Row title="Earlier trades like this">{earlier}</Row>
        <Row title={`Past model trades in ${stock.symbol}`}>{detail?.past_trades ?? "—"}</Row>
        <div className="rd-li">
          <a className="rd-table__more" style={{ border: 0, padding: 0 }} href={STREAMLIT_URL} target="_blank" rel="noreferrer">
            {OLD_APP_LINK}
          </a>
        </div>
      </section>
    </>
  );
}

