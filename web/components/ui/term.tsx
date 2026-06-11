import * as React from "react";
import { GLOSSARY } from "@/lib/glossary";
import { cn } from "@/lib/utils";

export function Term({ k, children, className }: { k: string; children?: React.ReactNode; className?: string }) {
  const entry = GLOSSARY[k];
  if (!entry) return <>{children ?? k}</>;
  return (
    <span title={entry.explain} className={cn("cursor-help underline decoration-dotted underline-offset-2", className)}>
      {children ?? entry.label}
    </span>
  );
}
