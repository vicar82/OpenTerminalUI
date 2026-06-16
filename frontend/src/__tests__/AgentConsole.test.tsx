import { describe, it, expect, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { AgentConsole } from "../agent/components/AgentConsole";
import { useAgentStore } from "../agent/agentStore";

beforeEach(() => {
  useAgentStore.setState({ open: false, running: false, messages: [], artifacts: [] });
});

describe("AgentConsole", () => {
  it("is not visible when closed", () => {
    render(<AgentConsole />);
    expect(screen.queryByRole("dialog", { name: /agent console/i })).toBeNull();
  });

  it("renders messages and artifacts when open", () => {
    useAgentStore.setState({
      open: true,
      messages: [
        { id: "u1", role: "user", content: "find cheap stocks", steps: [], pending: false },
        { id: "a1", role: "assistant", content: "Top pick: AAPL",
          steps: [{ id: "c1", name: "screen_stocks", isError: false }], pending: false },
      ],
      artifacts: [{ id: "art1", kind: "screener_table", name: "screen_stocks", data: { rows: [{ ticker: "AAPL" }] } }],
    });
    render(<AgentConsole />);
    expect(screen.getByRole("dialog", { name: /agent console/i })).toBeInTheDocument();
    expect(screen.getByText("find cheap stocks")).toBeInTheDocument();
    expect(screen.getByText("Top pick: AAPL")).toBeInTheDocument();
    expect(screen.getByText(/screen_stocks/)).toBeInTheDocument();
    expect(screen.getByText("AAPL")).toBeInTheDocument();
  });

  it("Ctrl/Cmd+J toggles the console open", () => {
    render(<AgentConsole />);
    expect(useAgentStore.getState().open).toBe(false);
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "j", ctrlKey: true }));
    expect(useAgentStore.getState().open).toBe(true);
  });
});
