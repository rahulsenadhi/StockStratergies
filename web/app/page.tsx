import { CandidatesCard, GrowthCard, StrategiesCard } from "@/components/desk/home/home-cards";
import { GlossaryDisclosure } from "@/components/desk/glossary";
import { ResearchNotice } from "@/components/desk/notices";
import { ChangePill, EmptyState, PageHeader, RailList, StatusPill } from "@/components/desk/primitives";
import { freshnessLabel, freshnessTone } from "@/lib/desk/format";
import { HOW_TO_READ, headerSub, headerTrend, marketRows, priceAge } from "@/lib/desk/home";
import { savedDataAges } from "@/lib/desk/saved-ages";
import { loadSnapshot, withLiveFreshness } from "@/lib/desk/snapshot";

export const dynamic = "force-dynamic";

const NOT_READY: Record<"missing" | "invalid" | "version", string> = {
  missing: "No saved results file (ui_snapshot.json) was found.",
  invalid: "The saved results file could not be read; it may be mid-update.",
  version: "The saved results file was written by a newer version of the update script.",
};

export default async function Home() {
  const [snap, ages] = await Promise.all([loadSnapshot(), savedDataAges()]);
  if (!snap.ok) {
    return (
      <>
        <PageHeader title="Overview" />
        <EmptyState title="Saved results for this page are not ready. Run Update all data." reason={NOT_READY[snap.reason]} />
      </>
    );
  }
  const { frame, home } = await withLiveFreshness(snap.snapshot);
  const trend = headerTrend(frame.regime.status);

  return (
    <>
      <PageHeader
        title="Overview"
        sub={headerSub(home.candidates.length)}
        right={<><StatusPill label={trend.label} tone={trend.tone} />{" "}
          Prices up to {frame.freshness.latest_bar ?? "—"} · {priceAge(frame.freshness.age_hours)}</>}
      />
      <div className="desk-split">
        <div className="desk-stack" style={{ gap: 18 }}>
          <CandidatesCard candidates={home.candidates} peadHasSignals={home.pead_has_signals} />
          <GrowthCard growth={home.growth} />
        </div>
        <div className="desk-stack">
          <RailList title="Market" meta="Nifty" items={marketRows(frame.regime).map((r) => ({
            key: r.title, title: r.title, sub: r.sub || undefined,
            value: r.pill ? <StatusPill label={r.pill.label} tone={r.pill.tone} />
              : r.change !== undefined ? <ChangePill value={r.change} />
                : <span className="rd-li__val">{r.text}</span>,
          }))} />
          <StrategiesCard strategies={home.strategies} />
          <RailList title="Saved data" meta="Refresh data in the sidebar" items={ages.map((a) => ({
            key: a.name, title: a.name, value: <StatusPill label={freshnessLabel(a.ageDays)} tone={freshnessTone(a.ageDays)} />,
          }))} />
        </div>
      </div>
      <ResearchNotice />
      <details className="desk-disclosure">
        <summary>How to read these figures</summary>
        <div>{HOW_TO_READ}</div>
      </details>
      <GlossaryDisclosure />
    </>
  );
}
