import { describe, it, expect } from "vitest";
import { parseSSEBuffer } from "../agent/sse";

describe("parseSSEBuffer", () => {
  it("parses complete events and keeps remainder", () => {
    const buf = 'data: {"type":"token","text":"hi"}\n\ndata: {"type":"final","content":"done"}\n\ndata: {"type":"to';
    const { events, rest } = parseSSEBuffer(buf);
    expect(events).toHaveLength(2);
    expect(events[0]).toEqual({ type: "token", text: "hi" });
    expect(events[1]).toEqual({ type: "final", content: "done" });
    expect(rest).toBe('data: {"type":"to');
  });

  it("returns no events when buffer has no complete frame", () => {
    const { events, rest } = parseSSEBuffer('data: {"type":"to');
    expect(events).toHaveLength(0);
    expect(rest).toBe('data: {"type":"to');
  });

  it("ignores malformed json frames but still advances", () => {
    const buf = 'data: not-json\n\ndata: {"type":"final","content":"ok"}\n\n';
    const { events, rest } = parseSSEBuffer(buf);
    expect(events).toEqual([{ type: "final", content: "ok" }]);
    expect(rest).toBe("");
  });
});
