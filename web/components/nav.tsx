import Link from "next/link";

export function Nav() {
  return (
    <nav className="sticky top-0 z-10 border-b border-border bg-background/80 backdrop-blur">
      <div className="mx-auto flex max-w-5xl gap-4 p-4 text-sm">
        <Link href="/" className="font-semibold hover:underline">Home</Link>
        <Link href="/leaderboard" className="text-muted-foreground hover:underline">Leaderboard</Link>
        <Link href="/glossary" className="text-muted-foreground hover:underline">Glossary</Link>
      </div>
    </nav>
  );
}
