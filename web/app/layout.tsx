import type { Metadata } from "next";
import "./globals.css";
import { AppShell } from "@/components/app-shell";
import { DataFreshness } from "@/components/data-freshness";

export const metadata: Metadata = {
  title: "NSE Strategy Hub",
  description: "Backtested NSE strategy leaderboard, detail, and portfolio",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="bg-background text-foreground antialiased">
        <AppShell topbarRight={<DataFreshness />}>{children}</AppShell>
      </body>
    </html>
  );
}
