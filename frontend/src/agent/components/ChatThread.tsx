import type { AgentMessage, AgentRoleNote } from "../types";

// Role → display label + accent tone. Mirrors the debate roles emitted by the
// backend. Tones map to the home-screen palette (terminal-pos/neg/accent).
const ROLE_META: Record<string, { label: string; tone: "accent" | "pos" | "neg" }> = {
  fundamental: { label: "Fundamental", tone: "accent" },
  sentiment: { label: "Sentiment", tone: "accent" },
  technical: { label: "Technical", tone: "accent" },
  bull: { label: "Bull", tone: "pos" },
  bear: { label: "Bear", tone: "neg" },
};

const TONE_BORDER = { accent: "border-l-terminal-accent", pos: "border-l-terminal-pos", neg: "border-l-terminal-neg" } as const;
const TONE_TEXT = { accent: "text-terminal-accent", pos: "text-terminal-pos", neg: "text-terminal-neg" } as const;

// Card styling mirrors the home screen (rounded border-terminal-border
// bg-terminal-panel/80, accent uppercase label) so the debate feels native.
function RoleCard({ note }: { note: AgentRoleNote }) {
  const meta = ROLE_META[note.role] ?? { label: note.role, tone: "accent" as const };
  return (
    <div className={`rounded border border-l-2 border-terminal-border ${TONE_BORDER[meta.tone]} bg-terminal-panel/80 p-2.5 font-mono`}>
      <span className={`text-[10px] font-semibold uppercase tracking-wide ${TONE_TEXT[meta.tone]}`}>
        {meta.label}
      </span>
      <div className="mt-1 whitespace-pre-wrap text-xs leading-5 text-terminal-muted">
        {note.content}
      </div>
    </div>
  );
}

export function ChatThread({ messages }: { messages: AgentMessage[] }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--ot-space-3)", padding: "var(--ot-space-3)" }}>
      {messages.map((m) => (
        <div key={m.id} style={{ display: "flex", flexDirection: "column", gap: "var(--ot-space-1)" }}>
          <span style={{ fontSize: 10, textTransform: "uppercase", letterSpacing: 0.6, color: "var(--ot-color-text-muted)" }}>
            {m.role}
          </span>
          {m.steps.length > 0 && (
            <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 2 }}>
              {m.steps.map((s) => (
                <li
                  key={s.id}
                  style={{
                    fontFamily: "var(--ot-font-data)", fontSize: 11,
                    color: s.isError ? "var(--ot-color-feedback-error)" : "var(--ot-color-text-secondary)",
                  }}
                >
                  {s.isError ? "✗ failed " : "→ ran "}{s.name}
                </li>
              ))}
            </ul>
          )}
          {(m.phases ?? []).length > 0 && (
            <div className="mb-0.5 flex flex-wrap gap-1 font-mono">
              {(m.phases ?? []).map((p, i) => (
                <span
                  key={p.key}
                  className="rounded border border-terminal-border px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-terminal-muted"
                >
                  {i + 1}. {p.label}
                </span>
              ))}
            </div>
          )}
          {(m.roles ?? []).length > 0 && (
            <div className="flex flex-col gap-1">
              {(m.roles ?? []).map((r, i) => (
                <RoleCard key={`${m.id}-${r.role}-${i}`} note={r} />
              ))}
            </div>
          )}
          <div
            style={{
              fontFamily: "var(--ot-font-ui)", fontSize: 13, lineHeight: 1.5,
              color: "var(--ot-color-text-primary)", whiteSpace: "pre-wrap",
            }}
          >
            {m.pending && !m.content ? <span style={{ color: "var(--ot-color-text-muted)" }}>Thinking…</span> : m.content}
          </div>
        </div>
      ))}
    </div>
  );
}
