import type { AgentEvent } from "./types";

const FRAME_SEP = "\n\n";

/**
 * Split an accumulating SSE text buffer into complete events.
 * Returns parsed events plus the unconsumed remainder (a partial frame).
 * Malformed JSON frames are skipped, not thrown.
 */
export function parseSSEBuffer(buffer: string): { events: AgentEvent[]; rest: string } {
  const events: AgentEvent[] = [];
  let rest = buffer;

  let sep = rest.indexOf(FRAME_SEP);
  while (sep !== -1) {
    const frame = rest.slice(0, sep);
    rest = rest.slice(sep + FRAME_SEP.length);

    const line = frame.trim();
    if (line.startsWith("data:")) {
      const payload = line.slice("data:".length).trim();
      try {
        events.push(JSON.parse(payload) as AgentEvent);
      } catch {
        // skip malformed frame
      }
    }
    sep = rest.indexOf(FRAME_SEP);
  }
  return { events, rest };
}
