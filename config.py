"""Shared model configuration helpers — read by all agents at startup."""
from collections.abc import Callable
import os
from typing import TypeVar

Tool = TypeVar("Tool")


def get_default_model(fallback: str = "gpt-5.2"):
    """Return the configured default model for standard agents."""
    model = os.getenv("DEFAULT_MODEL", fallback)
    return _resolve(model)


def is_openai_provider() -> bool:
    """Return True when the configured provider is OpenAI (not LiteLLM).

    OpenAI model IDs never contain a slash (e.g. 'gpt-5.2', 'o3').
    Any 'provider/model' string (e.g. 'anthropic/claude-sonnet-4-6',
    'litellm/gemini/gemini-3-flash') is treated as a LiteLLM-routed model.
    """
    return "/" not in os.getenv("DEFAULT_MODEL", "")


def openai_hosted_tools(*factories: Callable[[], Tool]) -> list[Tool]:
    """Instantiate OpenAI hosted tools only for OpenAI-routed agents."""
    if not is_openai_provider():
        return []
    return [factory() for factory in factories]


def _resolve(model: str):
    """Route 'provider/model' strings through LitellmModel.

    Handles both explicit 'litellm/<model>' and bare 'provider/model' forms.
    OpenAI model IDs contain no slash, so they pass through unchanged.
    """
    if "/" not in model:
        return model
    bare = model[len("litellm/"):] if model.startswith("litellm/") else model
    try:
        from agency_swarm import LitellmModel  # noqa: PLC0415
        return LitellmModel(model=bare)
    except ImportError:
        return model
