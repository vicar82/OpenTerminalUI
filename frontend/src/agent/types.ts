export type AgentEvent =
  | { type: "token"; text: string }
  | { type: "tool_call"; id: string; name: string; arguments: Record<string, unknown> }
  | { type: "tool_result"; id: string; name: string; result: unknown; is_error: boolean }
  | { type: "artifact"; kind: string; name: string; data: unknown }
  | { type: "final"; content: string }
  | { type: "error"; message: string };

export interface RunContext {
  route?: string;
  symbol?: string;
}

export interface RunRequest {
  prompt: string;
  context?: RunContext;
  provider?: string;
  model?: string;
}

export interface AgentMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  steps: { id: string; name: string; isError: boolean }[];
  pending: boolean;
}

export interface AgentArtifact {
  id: string;
  kind: string;
  name: string;
  data: unknown;
}
