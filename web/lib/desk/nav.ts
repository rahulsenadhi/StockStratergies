/**
 * Sidebar nav — labels, groups and order are verbatim from Streamlit (NAV_LABELS).
 * href null = page not built in Next.js yet; it opens the Streamlit app instead.
 */
export const STREAMLIT_URL = process.env.NEXT_PUBLIC_STREAMLIT_URL ?? "http://localhost:8500";

export type NavIcon =
  | "LayoutDashboard" | "FolderOpen" | "CirclePlus" | "RefreshCw" | "Rocket"
  | "TrendingUp" | "CalendarDays" | "ListChecks" | "Activity" | "ArrowLeftRight";

export interface NavItem {
  label: string;
  icon: NavIcon;
  href: string | null;
}

export interface NavGroup {
  group: "" | "STRATEGIES" | "FIND STOCKS" | "EVALUATE";
  items: NavItem[];
}

export const NAV: NavGroup[] = [
  { group: "", items: [{ label: "Home", icon: "LayoutDashboard", href: "/" }] },
  {
    group: "STRATEGIES",
    items: [
      { label: "Browse strategies", icon: "FolderOpen", href: null },
      { label: "Create a strategy", icon: "CirclePlus", href: null },
    ],
  },
  {
    group: "FIND STOCKS",
    items: [
      { label: "Monthly stock rotation", icon: "RefreshCw", href: null },
      { label: "Newly listed stocks (IPO)", icon: "Rocket", href: null },
      { label: "Price strength (Momentum)", icon: "TrendingUp", href: null },
      { label: "After earnings (PEAD)", icon: "CalendarDays", href: null },
      { label: "Stocks to review", icon: "ListChecks", href: null },
    ],
  },
  {
    group: "EVALUATE",
    items: [
      { label: "Understand past trades", icon: "Activity", href: null },
      { label: "Compare past results", icon: "ArrowLeftRight", href: null },
    ],
  },
];

export interface ResolvedHref {
  href: string;
  external: boolean;
}

export function navHref(item: NavItem): ResolvedHref {
  return item.href ? { href: item.href, external: false } : { href: STREAMLIT_URL, external: true };
}

/** Candidate short names and strategies-index ids → the nav label of their strategy page. */
const STRATEGY_PAGE: Record<string, string> = {
  Monthly: "Monthly stock rotation", monthly_rotation: "Monthly stock rotation",
  IPO: "Newly listed stocks (IPO)", ipo_edge: "Newly listed stocks (IPO)",
  Momentum: "Price strength (Momentum)", momentum_edge: "Price strength (Momentum)",
  PEAD: "After earnings (PEAD)", pead: "After earnings (PEAD)",
};

/**
 * Where a candidate or strategy row opens. Built pages get `?ticker=`; everything else
 * (unbuilt page, custom strategy) opens the Streamlit app. Streamlit has no per-page URL.
 */
export function strategyPageHref(strategyShortOrId: string, ticker?: string): ResolvedHref {
  const label = STRATEGY_PAGE[strategyShortOrId];
  const item = NAV.flatMap((g) => g.items).find((i) => i.label === label);
  if (!item?.href) return { href: STREAMLIT_URL, external: true };
  return { href: ticker ? `${item.href}?ticker=${encodeURIComponent(ticker)}` : item.href, external: false };
}
