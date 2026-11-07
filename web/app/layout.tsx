import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import "./desk.css";
import { DeskShell } from "@/components/desk/desk-shell";
import { THEME_BOOT_SCRIPT } from "@/lib/desk/theme";
import { MarketContext } from "@/components/desk/notices";
import { loadSnapshot, withLiveFreshness } from "@/lib/desk/snapshot";
import { savedDataAges } from "@/lib/desk/saved-ages";

const inter = Inter({ subsets: ["latin"], weight: ["400", "500", "600", "700"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "NSE Strategy Hub",
  description: "Research desk for the NSE strategies: candidates and the evidence behind them",
};

// Saved files change after every update, so the frame is read fresh on each request.
export const dynamic = "force-dynamic";

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const [ages, snap] = await Promise.all([savedDataAges(), loadSnapshot()]);
  const marketContext = snap.ok ? <MarketContext {...(await withLiveFreshness(snap.snapshot)).frame} /> : null;
  return (
    <html lang="en" data-theme="light" className={inter.variable} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_BOOT_SCRIPT }} />
      </head>
      <body className="antialiased">
        <DeskShell ages={ages} marketContext={marketContext}>{children}</DeskShell>
      </body>
    </html>
  );
}
