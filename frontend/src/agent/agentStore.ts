import { create } from "zustand";

import { createRun, streamRun } from "./agentApi";
import { buildScreenContext } from "./screenContext";
import type { AgentArtifact, AgentEvent, AgentMessage } from "./types";

let seq = 0;
const nextId = () => `m${Date.now()}_${seq++}`;

interface AgentState {
  open: boolean;
  running: boolean;
  debate: boolean;
  messages: AgentMessage[];
  artifacts: AgentArtifact[];
  toggleOpen: () => void;
  setOpen: (open: boolean) => void;
  toggleDebate: () => void;
  appendUserAndPending: (prompt: string) => void;
  applyEvent: (event: AgentEvent) => void;
  startRun: (prompt: string) => Promise<void>;
}

export const useAgentStore = create<AgentState>((set, get) => ({
  open: false,
  running: false,
  debate: false,
  messages: [],
  artifacts: [],

  toggleOpen: () => set((s) => ({ open: !s.open })),
  setOpen: (open) => set({ open }),
  toggleDebate: () => set((s) => ({ debate: !s.debate })),

  appendUserAndPending: (prompt) =>
    set((s) => ({
      messages: [
        ...s.messages,
        { id: nextId(), role: "user", content: prompt, steps: [], phases: [], roles: [], pending: false },
        { id: nextId(), role: "assistant", content: "", steps: [], phases: [], roles: [], pending: true },
      ],
    })),

  applyEvent: (event) => {
    if (event.type === "artifact") {
      set((s) => ({
        artifacts: [
          ...s.artifacts,
          { id: nextId(), kind: event.kind, name: event.name, data: event.data },
        ],
      }));
      return;
    }
    set((s) => {
      const messages = s.messages.slice();
      const idx = messages.length - 1;
      if (idx < 0 || messages[idx].role !== "assistant") return s;
      const msg = {
        ...messages[idx],
        steps: messages[idx].steps.slice(),
        phases: messages[idx].phases.slice(),
        roles: messages[idx].roles.slice(),
      };

      switch (event.type) {
        case "tool_call":
          msg.steps.push({ id: event.id, name: event.name, isError: false });
          break;
        case "tool_result": {
          // Replace the step object (don't mutate the shared prior-state object).
          const si = msg.steps.findIndex((st) => st.id === event.id);
          if (si !== -1) msg.steps[si] = { ...msg.steps[si], isError: event.is_error };
          break;
        }
        case "phase":
          msg.phases.push({ key: event.key, label: event.label });
          break;
        case "role_message":
          msg.roles.push({ role: event.role, content: event.content });
          break;
        case "token":
          msg.content += event.text;
          break;
        case "final":
          msg.content = event.content;
          msg.pending = false;
          break;
        case "error":
          msg.content = msg.content || `The agent hit an error: ${event.message}`;
          msg.pending = false;
          break;
      }
      messages[idx] = msg;
      const running = event.type === "final" || event.type === "error" ? false : s.running;
      return { messages, running };
    });
  },

  startRun: async (prompt) => {
    const text = prompt.trim();
    if (!text || get().running) return;
    get().appendUserAndPending(text);
    set({ running: true });
    try {
      const debate = get().debate;
      const runId = await createRun({
        prompt: text,
        context: buildScreenContext(),
        ...(debate ? { mode: "debate" as const, ticker: text } : {}),
      });
      await streamRun(runId, (event) => get().applyEvent(event));
    } catch (err) {
      get().applyEvent({ type: "error", message: (err as Error).message || "request failed" });
    } finally {
      if (get().running) set({ running: false });
    }
  },
}));
