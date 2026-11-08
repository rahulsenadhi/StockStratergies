"use client";

import { useState } from "react";
import { HoldExitCard } from "@/components/desk/hold-exit-card";
import { SectionHead } from "@/components/desk/primitives";
import { Segmented } from "@/components/desk/segmented";
import { Funnel } from "@/components/desk/momentum/funnel";
import { LowerTabs } from "@/components/desk/momentum/lower-tabs";
import { SetupsDesk } from "@/components/desk/momentum/setups-desk";
import { SummaryCard } from "@/components/desk/momentum/summary-card";
import {
  ATH_NOTE, ATH_OPTIONS, ATH_SWITCH_LABEL, FUNNEL_NOTE, FUNNEL_TITLE, HOLD_EXIT_TITLE, holdExitExtras, resolveSelected, type UiMomentum, type ViewKey,
} from "@/lib/desk/momentum-text";

type AthOption = (typeof ATH_OPTIONS)[number];
const VIEW_OF: Record<AthOption, ViewKey> = { [ATH_OPTIONS[0]]: "all", [ATH_OPTIONS[1]]: "ath" };

/** Owns the "which breakouts count" switch so the stats, setups and past trades all follow it. */
export function MomentumDesk({ data, ticker }: { data: UiMomentum; ticker: string | undefined }) {
  const [option, setOption] = useState<AthOption>(ATH_OPTIONS[0]);
  const view = VIEW_OF[option];
  const initial = resolveSelected(data, ticker);

  return (
    <>
      <div className="desk-stack" style={{ gap: 4 }}>
        <div className="desk-row">
          <span className="rd-note">{ATH_SWITCH_LABEL}</span>
          <Segmented options={ATH_OPTIONS} value={option} onChange={setOption} ariaLabel={ATH_SWITCH_LABEL} />
        </div>
        <p className="rd-note" style={{ margin: 0 }}>{ATH_NOTE}</p>
      </div>
      <HoldExitCard rec={data.exit_rec} title={HOLD_EXIT_TITLE} extra={holdExitExtras(data.views[view].health)} />
      <SummaryCard summary={data.summary} chart={data.chart} health={data.views[view].health} />
      <SetupsDesk key={initial.symbol ?? ""} data={data} view={view} initial={initial} />
      {data.funnel ? (
        <section className="desk-stack" style={{ gap: 8 }} aria-label="Filter funnel">
          <SectionHead title={FUNNEL_TITLE(data.funnel.total)} meta={FUNNEL_NOTE} />
          <Funnel funnel={data.funnel} />
        </section>
      ) : null}
      <LowerTabs data={data} view={view} />
    </>
  );
}
