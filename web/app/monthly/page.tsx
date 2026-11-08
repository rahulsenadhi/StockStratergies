import { GlossaryDisclosure } from "@/components/desk/glossary";
import { PageUpdateButton } from "@/components/desk/page-update-button";
import { ResearchNotice } from "@/components/desk/notices";
import { ContextBar, EmptyState, PageHeader, StatusPill } from "@/components/desk/primitives";
import { HoldExitCard } from "@/components/desk/hold-exit-card";
import { MonthlySelectionProvider } from "@/components/desk/monthly/selection";
import { Top5Card } from "@/components/desk/monthly/top5-card";
import { LowerTabs } from "@/components/desk/monthly/lower-tabs";
import { RankingDesk } from "@/components/desk/monthly/ranking-desk";
import { SummaryCard } from "@/components/desk/monthly/summary-card";
import {
  CONTEXT_BASIS, CONTEXT_RULE, CONTEXT_UNIVERSE, EMPTY_NO_SIMULATION, FOOTER_CAPTION, LIVE_PILL, MONTHLY_SUB,
  HOLD_EXIT_TITLE, MONTHLY_TITLE, loadMonthly, rankingAge, resolveSelected, testPeriod, type UiMonthly,
} from "@/lib/desk/monthly";
import { savedDataAges } from "@/lib/desk/saved-ages";

export const dynamic = "force-dynamic";

/** Same "not ready" wording as Home, naming this page's file. */
const NOT_READY_TITLE = "Saved results for this page are not ready. Run Update all data.";
const NOT_READY: Record<"missing" | "invalid" | "version", string> = {
  missing: "No saved results file (ui_monthly.json) was found.",
  invalid: "The saved results file (ui_monthly.json) could not be read; it may be mid-update.",
  version: "The saved results file (ui_monthly.json) was written by a newer version of the update script.",
};

type SearchParams = Promise<{ [key: string]: string | string[] | undefined }>;

function firstParam(v: string | string[] | undefined): string | undefined {
  return Array.isArray(v) ? v[0] : v;
}

function Ranking({ data, initial }: { data: UiMonthly; initial: string | null }) {
  return (
    <RankingDesk key={initial ?? ""} ranking={data.ranking} filters={data.filters} initialSelected={initial}
      closes={data.closes} top5={data.top5} colour={data.colour} />
  );
}

/** Monthly stock rotation (Streamlit render_monthly), in the same section order. */
export default async function MonthlyPage({ searchParams }: { searchParams: SearchParams }) {
  const [res, ages, params] = await Promise.all([loadMonthly(), savedDataAges(), searchParams]);
  const age = rankingAge(ages.find((a) => a.name === "Monthly")?.ageDays ?? null);
  const header = (
    <PageHeader title={MONTHLY_TITLE} sub={MONTHLY_SUB}
      right={<><StatusPill label={LIVE_PILL} tone="info" />{" "}<StatusPill label={age.label} tone={age.tone} />{" "}
        <PageUpdateButton strategy="Monthly" label="Update Monthly data" /></>} />
  );
  if (!res.ok) {
    return <>{header}<EmptyState title={NOT_READY_TITLE} reason={NOT_READY[res.reason]} /></>;
  }

  const data = res.data;
  const ticker = firstParam(params.ticker);
  const initial = resolveSelected(data.ranking, data.default_symbol, ticker);
  if (data.summary === null) {
    return (
      <>
        {header}
        <EmptyState title={EMPTY_NO_SIMULATION.title} reason={EMPTY_NO_SIMULATION.reason} />
        <MonthlySelectionProvider key={initial ?? ""} initial={initial}>
          <Ranking data={data} initial={initial} />
        </MonthlySelectionProvider>
      </>
    );
  }

  return (
    <>
      {header}
      <ContextBar
        items={[["Universe", CONTEXT_UNIVERSE], ["Test period", testPeriod(data.summary)], ["Rule", CONTEXT_RULE]]}
        basis={CONTEXT_BASIS} />
      <MonthlySelectionProvider key={initial ?? ""} initial={initial}>
        <Top5Card ranking={data.ranking} top5={data.top5} />
        <HoldExitCard rec={data.exit_rec} title={HOLD_EXIT_TITLE} />
        <SummaryCard summary={data.summary} chart={data.chart} />
        <Ranking data={data} initial={initial} />
      </MonthlySelectionProvider>
      <LowerTabs rebalances={data.rebalances} checks={data.checks} colour={data.colour} />
      <ResearchNotice />
      <p className="rd-note" style={{ margin: 0 }}>{FOOTER_CAPTION}</p>
      <GlossaryDisclosure />
    </>
  );
}
