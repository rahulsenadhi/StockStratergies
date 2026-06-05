import type { Metadata } from "next";
import "./globals.css";
import { Nav } from "@/components/nav";

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
        <Nav />
        {children}
      </body>
    </html>
  );
}
