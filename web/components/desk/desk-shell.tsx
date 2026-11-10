"use client";

import { useState, useSyncExternalStore, type ReactNode } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity, ArrowLeftRight, ArrowUpRight, Briefcase, CalendarDays, ChevronsLeft, ChevronsRight, CirclePlus, FolderOpen,
  LayoutDashboard, ListChecks, Menu, Moon, RefreshCw, Rocket, Sun, TrendingUp, type LucideIcon,
} from "lucide-react";
import { NAV, navHref, type NavIcon } from "@/lib/desk/nav";
import type { SavedAge } from "@/lib/desk/ages";
import { UpdatePanel } from "@/components/desk/update-panel";
import { THEME_KEY, type Theme } from "@/lib/desk/theme";

const ICONS: Record<NavIcon, LucideIcon> = {
  LayoutDashboard, FolderOpen, CirclePlus, RefreshCw, Rocket, TrendingUp, CalendarDays, ListChecks, Activity, ArrowLeftRight, Briefcase,
};

function subscribeTheme(onChange: () => void): () => void {
  const obs = new MutationObserver(onChange);
  obs.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  return () => obs.disconnect();
}
const readTheme = (): Theme => (document.documentElement.dataset.theme === "dark" ? "dark" : "light");

interface DeskShellProps {
  ages: SavedAge[];
  marketContext: ReactNode;
  children: ReactNode;
}

/** Research Desk frame: sidebar (nav + pinned updates), top bar, scrolling page area. */
export function DeskShell({ ages, marketContext, children }: DeskShellProps) {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const theme = useSyncExternalStore(subscribeTheme, readTheme, (): Theme => "light");

  function toggleTheme() {
    const next: Theme = theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try {
      window.localStorage.setItem(THEME_KEY, next);
    } catch {
      // not saved; the choice still applies to this visit
    }
  }

  return (
    <div className="desk">
      <aside className="desk-sidebar" data-collapsed={collapsed} data-open={mobileOpen} aria-label="Main navigation">
        <div className="desk-brand">
          <div className="desk-brand__logo" aria-hidden="true"><TrendingUp size={20} /></div>
          <div>
            <div className="desk-brand__l1">Strategy</div>
            <div className="desk-brand__l2">BACKTESTER</div>
          </div>
        </div>
        <nav className="desk-nav">
          {NAV.map((g) => (
            <div key={g.group || "home"}>
              {g.group ? <div className="desk-nav__group">{g.group}</div> : null}
              {g.items.map((item) => {
                const Icon = ICONS[item.icon];
                const { href, external } = navHref(item);
                const current = !external && pathname === href;
                return external ? (
                  <a key={item.label} className="desk-nav__item" href={href} target="_blank" rel="noreferrer"
                     onClick={() => setMobileOpen(false)} title="Not moved yet — opens the old Streamlit app">
                    <Icon aria-hidden="true" /> {item.label}
                    <ArrowUpRight className="desk-nav__hint" aria-hidden="true" />
                    <span className="sr-only">(opens old app)</span>
                  </a>
                ) : (
                  <Link key={item.label} className="desk-nav__item" href={href} aria-current={current ? "page" : undefined}
                        onClick={() => setMobileOpen(false)}>
                    <Icon aria-hidden="true" /> {item.label}
                  </Link>
                );
              })}
            </div>
          ))}
        </nav>
        <UpdatePanel ages={ages} />
      </aside>
      <div className="desk-scrim" data-open={mobileOpen} onClick={() => setMobileOpen(false)} aria-hidden="true" />
      <main className="desk-main">
        <div className="desk-topbar">
          <button type="button" className="desk-btn desk-btn--icon desk-only-mobile" aria-label="Open menu"
                  onClick={() => setMobileOpen(true)}>
            <Menu size={16} aria-hidden="true" />
          </button>
          <button type="button" className="desk-btn desk-btn--icon desk-only-desktop"
                  aria-label={collapsed ? "Show sidebar" : "Hide sidebar"} onClick={() => setCollapsed((c) => !c)}>
            {collapsed ? <ChevronsRight size={16} aria-hidden="true" /> : <ChevronsLeft size={16} aria-hidden="true" />}
          </button>
          <span style={{ flex: 1 }} />
          <button type="button" className="desk-btn desk-btn--icon" onClick={toggleTheme}
                  aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}>
            {theme === "dark" ? <Sun size={16} aria-hidden="true" /> : <Moon size={16} aria-hidden="true" />}
          </button>
        </div>
        <div className="desk-content desk-stack">
          {marketContext}
          {children}
        </div>
      </main>
    </div>
  );
}
