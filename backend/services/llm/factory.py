from __future__ import annotations

from backend.config.settings import get_settings
from backend.services.llm.base import LLMError
from backend.services.llm.openai_compatible import OpenAICompatibleProvider

AGENT_PROVIDERS = ("openrouter", "openai", "lmstudio", "ollama")


def get_llm_provider(
    *, provider: str | None = None, model: str | None = None,
    api_key: str | None = None,
) -> OpenAICompatibleProvider:
    """Build an OpenAI-compatible provider for the agent from settings + overrides."""
    settings = get_settings()
    provider = (provider or settings.agent_provider or "ollama").lower()
    timeout = settings.agent_timeout_seconds

    if provider == "openrouter":
        return OpenAICompatibleProvider(
            base_url=settings.openrouter_base_url,
            api_key=api_key or settings.openrouter_api_key,
            model=model or settings.agent_model,
            timeout=timeout,
            extra_headers={
                "HTTP-Referer": "https://openterminalui.local",
                "X-Title": "OpenTerminalUI Agent",
            },
            # Free models are flaky (429/404); try the configured free chain.
            fallback_models=[m for m in (settings.agent_fallback_models or []) if m != (model or settings.agent_model)],
        )
    if provider == "openai":
        return OpenAICompatibleProvider(
            base_url="https://api.openai.com/v1",
            api_key=api_key or settings.openai_api_key,
            model=model or settings.agent_model,
            timeout=timeout,
        )
    if provider == "lmstudio":
        return OpenAICompatibleProvider(
            base_url=settings.lm_studio_base_url,
            api_key=None,
            model=model or settings.lm_studio_model,
            timeout=timeout,
        )
    if provider == "ollama":
        return OpenAICompatibleProvider(
            base_url=f"{settings.ollama_base_url.rstrip('/')}/v1",
            api_key=api_key or settings.ollama_api_key,
            model=model or settings.ollama_model,
            timeout=timeout,
        )
    raise LLMError(f"Unknown agent provider: {provider}")
