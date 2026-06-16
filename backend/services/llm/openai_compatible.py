from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx

from backend.services.llm.base import (
    AssistantMessage, LLMError, LLMMessage, ToolCall, ToolDef,
)


class OpenAICompatibleProvider:
    """Async client for any OpenAI-compatible /chat/completions endpoint."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None,
        model: str,
        timeout: float = 120.0,
        extra_headers: dict[str, str] | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.extra_headers = extra_headers or {}
        self._transport = transport  # injected in tests

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", **self.extra_headers}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def complete(
        self,
        messages: list[LLMMessage | AssistantMessage],
        tools: list[ToolDef] | None = None,
        *,
        temperature: float = 0.1,
        max_tokens: int = 1024,
    ) -> AssistantMessage:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [m.to_wire() for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if tools:
            payload["tools"] = [t.to_wire() for t in tools]
            payload["tool_choice"] = "auto"
        url = f"{self.base_url}/chat/completions"
        # Free/shared providers (e.g. OpenRouter :free models) return 429 or 5xx
        # under load; retry a couple of times with backoff before giving up.
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(
                    timeout=self.timeout, trust_env=False, transport=self._transport
                ) as client:
                    resp = await client.post(url, json=payload, headers=self._headers())
                    resp.raise_for_status()
                    return self._parse(resp.json())
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code if exc.response is not None else 0
                last_exc = LLMError(f"LLM HTTP {status}")
                if status in (429, 500, 502, 503, 504) and attempt < 2:
                    await asyncio.sleep(1.5 * (attempt + 1))
                    continue
                raise last_exc from exc
            except (httpx.HTTPError, ValueError) as exc:
                last_exc = LLMError(f"LLM request failed: {exc}")
                if attempt < 2:
                    await asyncio.sleep(1.0 * (attempt + 1))
                    continue
                raise last_exc from exc
        raise last_exc or LLMError("LLM request failed")

    @staticmethod
    def _parse(data: dict[str, Any]) -> AssistantMessage:
        try:
            message = data["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("LLM returned an unexpected payload") from exc
        raw_calls = message.get("tool_calls") or []
        calls: list[ToolCall] = []
        for rc in raw_calls:
            fn = rc.get("function", {})
            raw_args = fn.get("arguments") or "{}"
            try:
                args = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
            except json.JSONDecodeError:
                args = {}
            calls.append(ToolCall(id=rc.get("id", ""), name=fn.get("name", ""), arguments=args))
        return AssistantMessage(content=message.get("content"), tool_calls=calls)
