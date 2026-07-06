"""Free-tier, capability-aware model selection for agent phases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


SAFETY_MODEL = "openai/gpt-oss-20b:free"

DEFAULT_TOOL_USE_MODELS = [
    "meta-llama/llama-3.3-70b-instruct:free",
    "qwen/qwen3-coder:free",
    SAFETY_MODEL,
]
DEFAULT_REASONING_MODELS = [
    "deepseek/deepseek-r1:free",
    "qwen/qwq-32b:free",
    "openai/gpt-oss-120b:free",
    SAFETY_MODEL,
]
DEFAULT_GENERAL_MODELS = [
    SAFETY_MODEL,
    "google/gemini-2.0-flash-exp:free",
]


@dataclass(frozen=True)
class TaskProfile:
    mode: str = "standard"
    phase: str = "tool_use"
    role: str | None = None
    intent: str | None = None


def classify_intent(prompt: str) -> str:
    text = prompt.lower()
    if any(word in text for word in (
        "backtest", "screen", "scan", "compare", "valuation", "ratio",
        "momentum", "rotation", "technical",
    )):
        return "quantitative"
    if any(word in text for word in (
        "why", "explain", "outlook", "thesis", "risk", "should", "opinion",
    )):
        return "narrative"
    return "general"


def _free_models(settings: Any, field: str, defaults: list[str]) -> list[str]:
    configured = getattr(settings, field, None) or defaults
    # Local providers (ollama, lmstudio) do not use OpenRouter-style :free suffixes.
    provider = (settings.agent_provider or "").lower()
    if provider in {"ollama", "lmstudio"}:
        return [model for model in configured if isinstance(model, str)]
    return [model for model in configured if isinstance(model, str) and model.endswith(":free")]


def select_chain(profile: TaskProfile, settings: Any) -> list[str]:
    """Return a non-empty ordered free-model chain for a unit of agent work."""
    tool_use = _free_models(settings, "agent_models_tool_use", DEFAULT_TOOL_USE_MODELS)
    reasoning = _free_models(settings, "agent_models_reasoning", DEFAULT_REASONING_MODELS)
    general = _free_models(settings, "agent_models_general", DEFAULT_GENERAL_MODELS)

    role = (profile.role or "").lower()
    if profile.phase == "synthesis" or role in {"bull", "bear", "portfolio_manager", "judge"}:
        selected, safety = reasoning, tool_use + general
    elif profile.phase == "general" or profile.mode in {"trivial", "general"}:
        selected, safety = general, tool_use + reasoning
    elif profile.phase == "tool_use" or role == "analyst":
        selected, safety = tool_use, reasoning + general
    else:
        selected, safety = general, tool_use + reasoning

    # Keep configured ordering, remove duplicates, and reserve the guaranteed
    # final fallback for the end of every chain.
    chain: list[str] = []
    for model in selected + safety:
        if model != SAFETY_MODEL and model not in chain:
            chain.append(model)
    chain.append(SAFETY_MODEL)
    return chain
