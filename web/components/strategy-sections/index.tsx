import type { ReactNode } from "react";
import type { Strategy } from "@/lib/data/strategies";
import { MonthlyRotationSection } from "@/components/strategy-sections/monthly-rotation";
import { IpoEdgeSection } from "@/components/strategy-sections/ipo-edge";
import { MomentumEdgeSection } from "@/components/strategy-sections/momentum-edge";
import { PeadSection } from "@/components/strategy-sections/pead";

export function StrategySection({ strategy }: { strategy: Strategy }): ReactNode {
  switch (strategy.id) {
    case "monthly_rotation":
      return <MonthlyRotationSection strategy={strategy} />;
    case "ipo_edge":
      return <IpoEdgeSection strategy={strategy} />;
    case "momentum_edge":
      return <MomentumEdgeSection strategy={strategy} />;
    case "pead":
      return <PeadSection strategy={strategy} />;
    default:
      return null;
  }
}
