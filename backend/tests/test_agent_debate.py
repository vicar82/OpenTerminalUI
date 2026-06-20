import pytest

from backend.agent.debate.orchestrator import DebateOrchestrator
from backend.agent.debate import roles
from backend.agent.tools.registry import ToolRegistry, ToolSpec
from backend.services.llm.base import AssistantMessage, ToolCall


class RoleAwareProvider:
    """Offline provider keyed by the first system prompt, safe under concurrency."""

    def __init__(self, fail_pm=False):
        self.calls_by_role = {}
        self.fail_pm = fail_pm

    async def complete(self, messages, tools=None, *, temperature=0.1, max_tokens=1024):
        system = messages[0].content
        count = self.calls_by_role.get(system, 0)
        self.calls_by_role[system] = count + 1
        if system == roles.FUNDAMENTAL_ANALYST:
            if count == 0:
                return AssistantMessage(tool_calls=[
                    ToolCall(id="fund-tool", name="get_stock_snapshot", arguments={"ticker": "AAPL"})
                ])
            return AssistantMessage(content="Fundamentals are strong.")
        if system == roles.SENTIMENT_ANALYST:
            return AssistantMessage(content="Sentiment is neutral.")
        if system == roles.TECHNICAL_ANALYST:
            return AssistantMessage(content="Momentum is positive.")
        if system == roles.BULL_RESEARCHER:
            return AssistantMessage(content="Bull case: quality and momentum support upside.")
        if system == roles.BEAR_RESEARCHER:
            return AssistantMessage(content="Bear case: valuation risk remains.")
        if system == roles.PORTFOLIO_MANAGER:
            if self.fail_pm:
                raise RuntimeError("portfolio manager unavailable")
            return AssistantMessage(
                content="Balanced setup.\nDECISION: BUY | CONVICTION: 72 | Evidence supports measured upside."
            )
        raise AssertionError(f"unexpected system prompt: {system}")


def _registry():
    registry = ToolRegistry()

    async def snapshot(args):
        return {"ticker": args["ticker"], "price": 200.0}

    registry.register(ToolSpec(
        "get_stock_snapshot", "snapshot", {"type": "object"}, snapshot, read_only=True,
    ))
    return registry


@pytest.mark.asyncio
async def test_debate_stream_has_ordered_roles_tools_and_one_final():
    stream = DebateOrchestrator(provider=RoleAwareProvider(), registry=_registry())
    result = [event async for event in stream.run("AAPL")]

    milestones = [
        (event["type"], event.get("key") or event.get("role"))
        for event in result
        if event["type"] in {"phase", "role_message", "final"}
    ]
    assert milestones == [
        ("phase", "analysts"),
        ("role_message", "fundamental"),
        ("role_message", "sentiment"),
        ("role_message", "technical"),
        ("phase", "debate"),
        ("role_message", "bull"),
        ("role_message", "bear"),
        ("phase", "decision"),
        ("final", None),
    ]
    assert any(event["type"] == "tool_call" for event in result)
    assert any(event["type"] == "tool_result" for event in result)
    finals = [event for event in result if event["type"] == "final"]
    assert len(finals) == 1
    assert "DECISION:" in finals[0]["content"]


@pytest.mark.asyncio
async def test_debate_emits_final_when_portfolio_manager_fails():
    stream = DebateOrchestrator(provider=RoleAwareProvider(fail_pm=True), registry=_registry())
    result = [event async for event in stream.run("AAPL")]

    assert result[-1]["type"] == "final"
    assert "DECISION:" in result[-1]["content"]
    assert any(event["type"] == "error" for event in result)


class EmptyContentProvider:
    """Analysts answer; bull/bear/PM return empty content (no exception).

    Reproduces a flaky small/free model that intermittently yields empty
    completions on long prompts.
    """

    async def complete(self, messages, tools=None, *, temperature=0.1, max_tokens=1024):
        system = messages[0].content
        if system in (roles.FUNDAMENTAL_ANALYST, roles.SENTIMENT_ANALYST, roles.TECHNICAL_ANALYST):
            return AssistantMessage(content="Analyst verdict.")
        return AssistantMessage(content="")  # bull, bear, portfolio manager


@pytest.mark.asyncio
async def test_debate_handles_empty_model_content_with_valid_decision():
    stream = DebateOrchestrator(provider=EmptyContentProvider(), registry=_registry())
    result = [event async for event in stream.run("RELIANCE")]

    finals = [e for e in result if e["type"] == "final"]
    assert len(finals) == 1
    # The final must still carry a usable DECISION line despite empty PM content.
    assert "DECISION:" in finals[0]["content"]
    # Bull/bear role messages must not be blank.
    role_msgs = {e["role"]: e["content"] for e in result if e["type"] == "role_message"}
    assert role_msgs["bull"].strip()
    assert role_msgs["bear"].strip()
