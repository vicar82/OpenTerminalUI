import { describe, it, expect, beforeEach } from "vitest";
import { useAgentStore } from "../agent/agentStore";

function reset() {
  useAgentStore.setState({
    open: false, running: false, messages: [], artifacts: [],
  });
}

describe("agentStore.applyEvent", () => {
  beforeEach(reset);

  it("tool_call appends a step to the pending assistant message", () => {
    const s = useAgentStore.getState();
    s.appendUserAndPending("find cheap stocks");
    s.applyEvent({ type: "tool_call", id: "c1", name: "screen_stocks", arguments: {} });
    const msgs = useAgentStore.getState().messages;
    const assistant = msgs[msgs.length - 1];
    expect(assistant.role).toBe("assistant");
    expect(assistant.steps).toEqual([{ id: "c1", name: "screen_stocks", isError: false }]);
  });

  it("tool_result marks the step errored without mutating the prior step object", () => {
    const s = useAgentStore.getState();
    s.appendUserAndPending("x");
    s.applyEvent({ type: "tool_call", id: "c1", name: "screen_stocks", arguments: {} });
    const priorStep = useAgentStore.getState().messages.at(-1)!.steps[0];
    s.applyEvent({ type: "tool_result", id: "c1", name: "screen_stocks", result: {}, is_error: true });
    const newStep = useAgentStore.getState().messages.at(-1)!.steps[0];
    expect(newStep.isError).toBe(true);
    // The previous-state object must be untouched (referential immutability).
    expect(priorStep.isError).toBe(false);
    expect(newStep).not.toBe(priorStep);
  });

  it("artifact event pushes an artifact", () => {
    useAgentStore.getState().appendUserAndPending("x");
    useAgentStore.getState().applyEvent({
      type: "artifact", kind: "screener_table", name: "screen_stocks",
      data: { rows: [{ ticker: "AAPL" }] },
    });
    expect(useAgentStore.getState().artifacts).toHaveLength(1);
    expect(useAgentStore.getState().artifacts[0].kind).toBe("screener_table");
  });

  it("final event fills assistant content and clears pending/running", () => {
    const s = useAgentStore.getState();
    s.appendUserAndPending("x");
    useAgentStore.setState({ running: true });
    s.applyEvent({ type: "final", content: "Top pick: AAPL" });
    const msgs = useAgentStore.getState().messages;
    expect(msgs[msgs.length - 1].content).toBe("Top pick: AAPL");
    expect(msgs[msgs.length - 1].pending).toBe(false);
    expect(useAgentStore.getState().running).toBe(false);
  });

  it("error event sets assistant content and clears running", () => {
    const s = useAgentStore.getState();
    s.appendUserAndPending("x");
    useAgentStore.setState({ running: true });
    s.applyEvent({ type: "error", message: "boom" });
    const msgs = useAgentStore.getState().messages;
    expect(msgs[msgs.length - 1].content).toContain("boom");
    expect(useAgentStore.getState().running).toBe(false);
  });

  it("toggleOpen flips open state", () => {
    expect(useAgentStore.getState().open).toBe(false);
    useAgentStore.getState().toggleOpen();
    expect(useAgentStore.getState().open).toBe(true);
  });
});
