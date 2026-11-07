import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import "./desk.css";
import { AppShell } from "@/components/app-shell";
import { DataFreshness } from "@/components/data-freshness";

const inter = Inter({ subsets: ["latin"], weight: ["400", "500", "600", "700"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "NSE Strategy Hub",
  description: "Research desk for the NSE strategies: candidates and the evidence behind them",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" data-theme="light" className={inter.variable} suppressHydrationWarning>
      <body className="bg-background text-foreground antialiased">
        <AppShell topbarRight={<DataFreshness />}>{children}</AppShell>
      </body>
    </html>
  );
}
