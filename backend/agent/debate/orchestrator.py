from __future__ import annotations

import asyncio
from typing import Any, AsyncGenerator

from backend.agent import events
from backend.agent.debate import roles
from backend.agent.orchestrator import Orchestrator
from backend.services.llm.base import LLMMessage


class DebateOrchestrator:
    """Coordinates independent analysts and a short bull/bear investment debate."""

    def __init__(self, *, provider: Any, registry: Any, analyst_max_steps: int = 4) -> None:
        self.provider = provider
        self.registry = registry
        self.analyst_max_steps = analyst_max_steps

    async def _collect_analyst(
        self, role_key: str, system_prompt: str, subject: str,
        screen_context: dict[str, Any] | None,
    ) -> tuple[list[dict[str, Any]], str]:
        passthrough: list[dict[str, Any]] = []
        note = ""
        try:
            orchestrator = Orchestrator(
                provider=self.provider,
                registry=self.registry,
                max_steps=self.analyst_max_steps,
                system_prompt=system_prompt,
            )
            async for event in orchestrator.run(
                f"Analyze {subject}. Give a tight verdict with evidence.",
                screen_context=screen_context,
            ):
                if event.get("type") in {"tool_call", "tool_result", "error"}:
                    passthrough.append(event)
                elif event.get("type") == "final":
                    note = str(event.get("content") or "")
        except Exception as exc:  # defensive: one analyst must not abort the debate
            passthrough.append(events.error(str(exc)))
            note = f"{role_key} analysis was unavailable."
        return passthrough, note

    @staticmethod
    def _analyst_context(notes: dict[str, str]) -> str:
        return "\n\n".join(
            f"{role.upper()} ANALYST NOTE:\n{notes.get(role, '')[:6000]}"
            for role, _ in roles.ANALYSTS
        )

    async def _complete(self, system: str, user: str) -> str:
        response = await self.provider.complete(
            [LLMMessage(role="system", content=system), LLMMessage(role="user", content=user)],
            tools=None,
        )
        return response.content or ""

    async def run(
        self, subject: str, *, screen_context: dict[str, Any] | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Yield a complete debate stream, containing one and only one final event."""
        try:
            yield events.phase("analysts", "Analyst team")
            results = await asyncio.gather(*[
                self._collect_analyst(role, prompt, subject, screen_context)
                for role, prompt in roles.ANALYSTS
            ])
            notes: dict[str, str] = {}
            for (role, _), (passthrough, note) in zip(roles.ANALYSTS, results):
                for event in passthrough:
                    yield event
                notes[role] = note
                yield events.role_message(role, note)

            yield events.phase("debate", "Bull vs Bear")
            analyst_context = self._analyst_context(notes)
            try:
                bull = await self._complete(roles.BULL_RESEARCHER, analyst_context)
            except Exception as exc:
                yield events.error(str(exc))
                bull = "Bull case unavailable."
            yield events.role_message("bull", bull)
            try:
                bear = await self._complete(roles.BEAR_RESEARCHER, analyst_context)
            except Exception as exc:
                yield events.error(str(exc))
                bear = "Bear case unavailable."
            yield events.role_message("bear", bear)

            yield events.phase("decision", "Portfolio manager")
            decision_context = f"{analyst_context}\n\nBULL CASE:\n{bull}\n\nBEAR CASE:\n{bear}"
            try:
                decision = await self._complete(roles.PORTFOLIO_MANAGER, decision_context)
            except Exception as exc:
                yield events.error(str(exc))
                decision = "Unable to complete the portfolio review.\nDECISION: HOLD | CONVICTION: 0 | The portfolio-manager model request failed."
            yield events.final(decision)
        except Exception as exc:  # final defensive boundary for all coordinator failures
            yield events.error(str(exc))
            yield events.final(
                "Unable to complete the debate.\n"
                "DECISION: HOLD | CONVICTION: 0 | The debate coordinator encountered an unexpected error."
            )
