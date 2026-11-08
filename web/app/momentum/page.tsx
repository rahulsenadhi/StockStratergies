import { GlossaryDisclosure } from "@/components/desk/glossary";
import { ResearchNotice } from "@/components/desk/notices";
import { PageUpdateButton } from "@/components/desk/page-update-button";
import { ContextBar, EmptyState, PageHeader, StatusPill } from "@/components/desk/primitives";
import { MomentumDesk } from "@/components/desk/momentum/momentum-desk";
import { freshnessLabel, freshnessTone } from "@/lib/desk/format";
import {
  CONTEXT_BASIS, CONTEXT_RULE, CONTEXT_UNIVERSE, MOMENTUM_SUB, MOMENTUM_TITLE, loadMomentum,
} from "@/lib/desk/momentum";
import { savedDataAges } from "@/lib/desk/saved-ages";

export const dynamic = "force-dynamic";

/** Same "not ready" wording as Home, naming this page's file. */
const NOT_READY_TITLE = "Saved results for this page are not ready. Run Update all data.";
const NOT_READY: Record<"missing" | "invalid" | "version", string> = {
  missing: "No saved results file (ui_momentum.json) was found.",
  invalid: "The saved results file (ui_momentum.json) could not be read; it may be mid-update.",
  version: "The saved results file (ui_momentum.json) was written by a newer version of the update script.",
};

type SearchParams = Promise<{ [key: string]: string | string[] | undefined }>;

function firstParam(v: string | string[] | undefined): string | undefined {
  return Array.isArray(v) ? v[0] : v;
}

/** Price strength (Momentum) in Streamlit's section order. */
export default async function MomentumPage({ searchParams }: { searchParams: SearchParams }) {
  const [res, ages, params] = await Promise.all([loadMomentum(), savedDataAges(), searchParams]);
  const age = ages.find((a) => a.name === "Momentum")?.ageDays ?? null;
  const header = (
    <PageHeader title={MOMENTUM_TITLE} sub={MOMENTUM_SUB}
      right={<><StatusPill label={`Signals ${freshnessLabel(age)}`} tone={freshnessTone(age)} />{" "}
        <StatusPill label="“Buy now” is a model label" tone="muted" />{" "}
        <PageUpdateButton strategy="Momentum" label="Update Momentum data" /></>} />
  );
  if (!res.ok) return <>{header}<EmptyState title={NOT_READY_TITLE} reason={NOT_READY[res.reason]} /></>;

  const data = res.data;
  const universe = data.funnel ? CONTEXT_UNIVERSE(data.funnel.total) : "NSE + BSE";
  const period = data.summary ? `${data.summary.start} → ${data.summary.end}` : "—";
  return (
    <>
      {header}
      <ContextBar items={[["Universe", universe], ["Test period", period], ["Rule", CONTEXT_RULE]]} basis={CONTEXT_BASIS} />
      <MomentumDesk data={data} ticker={firstParam(params.ticker)} />
      <ResearchNotice />
      <GlossaryDisclosure />
    </>
  );
}
