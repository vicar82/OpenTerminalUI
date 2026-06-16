import type { AgentMessage } from "../types";

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
                  data-tool-name={s.name}
                  aria-label={`${s.isError ? "failed" : "ran"} ${s.name}`}
                  style={{
                    fontFamily: "var(--ot-font-data)", fontSize: 11,
                    color: s.isError ? "var(--ot-color-feedback-error)" : "var(--ot-color-text-secondary)",
                  }}
                >
                  {s.isError ? "✗ failed" : "→ ran tool"}
                </li>
              ))}
            </ul>
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
