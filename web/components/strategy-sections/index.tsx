import type { ReactNode } from "react";
import type { Strategy } from "@/lib/data/strategies";
import { MonthlyRotationSection } from "@/components/strategy-sections/monthly-rotation";

export function StrategySection({ strategy }: { strategy: Strategy }): ReactNode {
  switch (strategy.id) {
    case "monthly_rotation":
      return <MonthlyRotationSection strategy={strategy} />;
    default:
      return null;
  }
}
