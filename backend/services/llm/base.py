from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Protocol


class LLMError(RuntimeError):
    """Raised when an LLM provider is unreachable or returns bad data."""


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]

    def to_wire(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": "function",
            "function": {"name": self.name, "arguments": json.dumps(self.arguments)},
        }


@dataclass
class LLMMessage:
    role: str  # "system" | "user" | "tool"
    content: str | None = None
    tool_call_id: str | None = None

    def to_wire(self) -> dict[str, Any]:
        wire: dict[str, Any] = {"role": self.role, "content": self.content or ""}
        if self.tool_call_id is not None:
            wire["tool_call_id"] = self.tool_call_id
        return wire


@dataclass
class AssistantMessage:
    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)

    def to_wire(self) -> dict[str, Any]:
        wire: dict[str, Any] = {"role": "assistant", "content": self.content}
        if self.tool_calls:
            wire["tool_calls"] = [tc.to_wire() for tc in self.tool_calls]
        return wire


@dataclass
class ToolDef:
    name: str
    description: str
    parameters: dict[str, Any]

    def to_wire(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class LLMProvider(Protocol):
    async def complete(
        self,
        messages: list[LLMMessage | AssistantMessage],
        tools: list[ToolDef] | None = None,
        *,
        temperature: float = 0.1,
        max_tokens: int = 1024,
    ) -> AssistantMessage: ...
