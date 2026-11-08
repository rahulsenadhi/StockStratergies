import { GLOSSARY } from "@/lib/glossary";

/** Home's "Glossary — What do these words mean?" disclosure, shared by every desk page. */
export function GlossaryDisclosure() {
  return (
    <details className="desk-disclosure">
      <summary>Glossary — What do these words mean?</summary>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: "10px 24px" }}>
        {Object.entries(GLOSSARY).map(([key, g]) => (
          <p key={key} className="rd-note" style={{ margin: 0 }}><b style={{ color: "var(--rd-text)" }}>{g.label}</b> — {g.explain}</p>
        ))}
      </div>
    </details>
  );
}
