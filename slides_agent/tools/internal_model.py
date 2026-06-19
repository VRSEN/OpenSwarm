"""Model selection helpers for Slides internal agents."""

from __future__ import annotations

import inspect
from typing import Any, Callable

from config import get_default_model
from openai import AsyncOpenAI


_OPENAI_PREFIX = "openai/"
_LITELLM_PREFIX = "litellm/"
_OPENAI_BASE_URL = "https://api.openai.com"
_LITELLM_CONFIG_FIELDS = (
    "api_key",
    "base_url",
    "api_base",
    "api_version",
    "organization",
    "project",
    "timeout",
    "max_retries",
    "headers",
    "default_headers",
    "extra_headers",
)
_OPENAI_CLIENT_FIELDS = (
    "api_key",
    "base_url",
    "organization",
    "project",
    "timeout",
    "max_retries",
    "default_headers",
    "default_query",
)


def _current_agent(tool: Any) -> Any | None:
    ctx = getattr(tool, "_context", None)
    master = getattr(ctx, "context", None)
    name = getattr(master, "current_agent_name", None)
    agents = getattr(master, "agents", {})
    return agents.get(name) if name else None


def _model_name(value: Any) -> str | None:
    if isinstance(value, str):
        return value.strip() or None
    for attr in ("model", "model_name", "name"):
        maybe = getattr(value, attr, None)
        if isinstance(maybe, str) and maybe.strip():
            return maybe.strip()
    return None


def _caller_model(tool: Any) -> Any | None:
    agent = _current_agent(tool)
    return getattr(agent, "model", None)


def _source_openai_client(source: Any | None) -> Any | None:
    if source is None:
        return None
    for attr in ("_client", "openai_client", "client"):
        maybe = getattr(source, attr, None)
        if maybe is not None:
            return maybe
    return None


def _resolved_model(tool: Any) -> tuple[str, Any | None]:
    source = _caller_model(tool)
    name = _model_name(source)
    if name:
        return name, source
    default = get_default_model()
    return _model_name(default) or "gpt-5.2", default


def _client_value(client: Any | None, field: str) -> Any | None:
    if client is None:
        return None
    if field == "api_key":
        provider = getattr(client, "_api_key_provider", None)
        if provider is not None:
            return provider
        return getattr(client, "api_key", None) or None
    if field == "base_url":
        value = getattr(client, "base_url", None)
        return str(value) if value is not None else None
    if field in {"headers", "default_headers", "extra_headers"}:
        return getattr(client, "_custom_headers", None)
    if field == "default_query":
        return getattr(client, "_custom_query", None) or getattr(client, field, None)
    return getattr(client, field, None)


def _clone_openai_client(client: AsyncOpenAI | None) -> AsyncOpenAI:
    if client is None:
        return AsyncOpenAI()
    kwargs = {
        field: value
        for field in _OPENAI_CLIENT_FIELDS
        if (value := _client_value(client, field)) is not None
    }
    return AsyncOpenAI(**kwargs)


def _base_url(client: Any | None) -> str:
    value = getattr(client, "base_url", None) if client is not None else None
    return str(value).rstrip("/") if value is not None else ""


def _is_openai_client(client: Any | None) -> bool:
    base = _base_url(client)
    return (
        not base
        or base == _OPENAI_BASE_URL
        or base.startswith(f"{_OPENAI_BASE_URL}/")
    )


def _is_codex_client(client: Any | None) -> bool:
    base = _base_url(client).lower()
    return bool(base and not _is_openai_client(client) and "codex" in base)


def _is_litellm_model(model: str, source: Any | None) -> bool:
    if source is None:
        source_is_litellm = False
    else:
        typ = type(source)
        source_is_litellm = (
            "litellm" in typ.__name__.lower() or "litellm" in typ.__module__.lower()
        )
    if source_is_litellm:
        return True
    if model.startswith(_LITELLM_PREFIX):
        return True
    if model.startswith(_OPENAI_PREFIX):
        return False
    return "/" in model


def _config_value(source: Any | None, field: str) -> Any | None:
    if source is None:
        return None
    value = getattr(source, field, None)
    if value is not None:
        return value
    for attr in ("kwargs", "_kwargs", "model_kwargs", "_model_kwargs"):
        values = getattr(source, attr, None)
        if isinstance(values, dict) and values.get(field) is not None:
            return values[field]
    return _client_value(_source_openai_client(source), field)


def _accepted_litellm_fields(litellm_model: type) -> set[str]:
    try:
        params = inspect.signature(litellm_model).parameters
    except (TypeError, ValueError):
        return {"api_key", "base_url"}
    if any(param.kind == inspect.Parameter.VAR_KEYWORD for param in params.values()):
        return set(_LITELLM_CONFIG_FIELDS)
    return {field for field in _LITELLM_CONFIG_FIELDS if field in params}


def _litellm_kwargs(
    model: str,
    source: Any | None,
    litellm_model: type,
) -> dict[str, Any]:
    bare = model[len(_LITELLM_PREFIX) :] if model.startswith(_LITELLM_PREFIX) else model
    kwargs: dict[str, Any] = {"model": bare}
    for field in _accepted_litellm_fields(litellm_model):
        value = _config_value(source, field)
        if value is not None:
            kwargs[field] = value
    return kwargs


def make_internal_model(
    tool: Any,
    *,
    litellm_model: type,
    openai_model: Callable[..., Any],
    codex_model: Callable[..., Any],
) -> tuple[Any, bool]:
    """Build a model for a Slides sub-agent, preferring the caller's model."""
    model, source = _resolved_model(tool)
    if _is_litellm_model(model, source):
        return litellm_model(**_litellm_kwargs(model, source, litellm_model)), False

    caller_client = _source_openai_client(source)
    client = _clone_openai_client(
        caller_client if isinstance(caller_client, AsyncOpenAI) else None
    )
    is_codex = _is_codex_client(caller_client)
    factory = codex_model if is_codex else openai_model
    return factory(model=model, openai_client=client), is_codex


def uses_openai_model_settings(tool: Any) -> bool:
    model, source = _resolved_model(tool)
    if _is_litellm_model(model, source):
        return False
    client = _source_openai_client(source)
    if client is None:
        return True
    return _is_openai_client(client) or _is_codex_client(client)


def make_internal_model_settings(tool: Any, *, is_codex: bool):
    """Build settings that avoid OpenAI-only fields for LiteLLM-routed models."""
    from agency_swarm import ModelSettings, Reasoning

    if not uses_openai_model_settings(tool):
        return ModelSettings()
    return ModelSettings(
        reasoning=Reasoning(effort="high", summary="auto"),
        verbosity=None if is_codex else "medium",
        store=False if is_codex else None,
    )
