import "../agentConsole.css";
import { useAgentStore } from "../agentStore";

export function AgentLauncher() {
  const open = useAgentStore((s) => s.open);
  const toggleOpen = useAgentStore((s) => s.toggleOpen);
  if (open) return null;
  return (
    <button type="button" className="ot-agent-launcher" onClick={toggleOpen} aria-label="Открыть консоль агента (Ctrl+J)">
      Agent
    </button>
  );
}
