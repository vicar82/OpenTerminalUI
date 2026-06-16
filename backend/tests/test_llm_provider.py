from backend.services.llm.base import (
    LLMMessage, ToolCall, AssistantMessage, ToolDef, LLMError,
)


def test_message_to_wire_roundtrip():
    msg = LLMMessage(role="user", content="hi")
    assert msg.to_wire() == {"role": "user", "content": "hi"}


def test_tool_result_message_wire():
    msg = LLMMessage(role="tool", content='{"ok": true}', tool_call_id="call_1")
    wire = msg.to_wire()
    assert wire["role"] == "tool"
    assert wire["tool_call_id"] == "call_1"


def test_assistant_message_with_tool_calls_wire():
    tc = ToolCall(id="call_1", name="screen_stocks", arguments={"query": "pe < 20"})
    msg = AssistantMessage(content=None, tool_calls=[tc])
    wire = msg.to_wire()
    assert wire["role"] == "assistant"
    assert wire["tool_calls"][0]["function"]["name"] == "screen_stocks"
    assert isinstance(wire["tool_calls"][0]["function"]["arguments"], str)


def test_tool_def_wire_shape():
    td = ToolDef(name="get_quote", description="quote", parameters={"type": "object"})
    wire = td.to_wire()
    assert wire["type"] == "function"
    assert wire["function"]["name"] == "get_quote"
