"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BookOpen,
  LayoutDashboard,
  LineChart,
  Target,
  Trophy,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface NavItem {
  label: string;
  href: string;
  icon: React.ElementType;
  exact?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { label: "Dashboard", href: "/", icon: LayoutDashboard, exact: true },
  { label: "Buy Now", href: "/suggestions", icon: Target },
  { label: "Leaderboard", href: "/leaderboard", icon: Trophy },
  { label: "Glossary", href: "/glossary", icon: BookOpen },
];

function NavLink({ item, pathname }: { item: NavItem; pathname: string }) {
  const isActive = item.exact
    ? pathname === item.href
    : pathname.startsWith(item.href);

  return (
    <Link
      href={item.href}
      className={cn(
        "flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors",
        isActive
          ? "border-l-2 border-accent-blue bg-accent-blue/10 font-medium text-accent-blue"
          : "text-muted-foreground hover:bg-muted/50 hover:text-foreground"
      )}
    >
      <item.icon size={15} strokeWidth={1.75} />
      {item.label}
    </Link>
  );
}

export function AppShell({
  children,
  topbarRight,
}: {
  children: React.ReactNode;
  topbarRight?: React.ReactNode;
}) {
  const pathname = usePathname();

  return (
    <div className="flex min-h-dvh">
      {/* Sidebar — desktop only */}
      <aside className="sticky top-0 hidden h-dvh w-56 shrink-0 flex-col border-r border-border bg-background md:flex">
        {/* Brand */}
        <div className="flex items-center gap-2 border-b border-border p-4">
          <LineChart size={18} className="text-accent-blue" strokeWidth={2} />
          <span className="text-sm font-semibold tracking-tight">
            Strategy Hub
          </span>
        </div>

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto px-2 py-3 space-y-0.5">
          {NAV_ITEMS.map((item) => (
            <NavLink key={item.href} item={item} pathname={pathname} />
          ))}
        </nav>
      </aside>

      {/* Main column */}
      <div className="flex flex-1 min-w-0 flex-col">
        {/* Topbar */}
        <header className="sticky top-0 z-10 flex h-12 items-center border-b border-border bg-background/80 px-4 backdrop-blur">
          {/* Mobile: compact horizontal nav */}
          <nav className="flex items-center gap-1 md:hidden">
            {NAV_ITEMS.map((item) => {
              const isActive = item.exact
                ? pathname === item.href
                : pathname.startsWith(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs transition-colors",
                    isActive
                      ? "bg-accent-blue/10 font-medium text-accent-blue"
                      : "text-muted-foreground hover:bg-muted/50 hover:text-foreground"
                  )}
                >
                  <item.icon size={13} strokeWidth={1.75} />
                  {item.label}
                </Link>
              );
            })}
          </nav>

          {/* Right-side action slot */}
          <div className="ml-auto">{topbarRight}</div>
        </header>

        {/* Page content */}
        <main className="flex-1">{children}</main>
      </div>
    </div>
  );
}
