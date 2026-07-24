"""Model and transport helpers for Slides internal agents."""

from __future__ import annotations

import inspect
from dataclasses import dataclass, replace
from typing import Any, Literal
from urllib.parse import urlsplit

from agency_swarm import ModelSettings, Reasoning
from agency_swarm.messages.codex_input import is_codex_base_url
from agency_swarm.utils.openrouter import (
    build_openrouter_chat_model,
    get_openrouter_model_name,
    is_openrouter_model_name,
)
from agents import OpenAIChatCompletionsModel, OpenAIResponsesModel
from agents.extensions.models.litellm_model import LitellmModel
from agents.models._openai_shared import get_default_openai_client
from config import get_default_model
from openai import AsyncOpenAI


Transport = Literal[
    "openai_responses",
    "codex_responses",
    "chat_completions",
    "openrouter",
    "litellm",
]

_LITELLM_PREFIX = "litellm/"
_OPENAI_PREFIX = "openai/"
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
    "should_replay_reasoning_content",
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


@dataclass(frozen=True)
class InternalModelRoute:
    model: Any
    transport: Transport

    @property
    def is_codex(self) -> bool:
        return self.transport == "codex_responses"


@dataclass
class _StreamResult:
    final_output: str
    raw_responses: list[Any]


class _CodexResponsesModel(OpenAIResponsesModel):
    """Responses model with settings accepted by Codex browser auth."""

    async def _fetch_response(
        self,
        system_instructions,
        input,
        model_settings,
        *args,
        **kwargs,
    ):
        model_settings = replace(
            model_settings,
            truncation=None,
            verbosity=None,
        )
        return await super()._fetch_response(
            system_instructions,
            input,
            model_settings,
            *args,
            **kwargs,
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
    return getattr(_current_agent(tool), "model", None)


def _run_config_model(tool: Any) -> Any | None:
    ctx = getattr(tool, "_context", None)
    return getattr(getattr(ctx, "run_config", None), "model", None)


def _source_openai_client(source: Any | None) -> AsyncOpenAI | None:
    if source is None:
        return None
    for attr in ("_client", "openai_client", "client"):
        maybe = getattr(source, attr, None)
        if isinstance(maybe, AsyncOpenAI):
            return maybe
    return None


def _resolved_model(tool: Any) -> tuple[str, Any | None]:
    caller = _caller_model(tool)
    request = _run_config_model(tool)
    request_name = _model_name(request)
    if request_name:
        source = request if not isinstance(request, str) else caller
        return request_name, source

    caller_name = _model_name(caller)
    if caller_name:
        return caller_name, caller

    default = get_default_model()
    return _model_name(default) or "gpt-5.4", default


def _client_value(client: AsyncOpenAI, field: str) -> Any | None:
    if field == "api_key":
        provider = getattr(client, "_api_key_provider", None)
        return provider if provider is not None else getattr(client, "api_key", None)
    if field == "base_url":
        value = getattr(client, "base_url", None)
        return str(value) if value is not None else None
    if field == "default_headers":
        return getattr(client, "_custom_headers", None)
    if field == "default_query":
        return getattr(client, "_custom_query", None)
    return getattr(client, field, None)


def _clone_openai_client(client: AsyncOpenAI | None) -> AsyncOpenAI:
    source = client or get_default_openai_client()
    if source is None:
        return AsyncOpenAI()
    kwargs = {
        field: value
        for field in _OPENAI_CLIENT_FIELDS
        if (value := _client_value(source, field)) is not None
    }
    return AsyncOpenAI(**kwargs)


def _is_direct_openai_url(value: str | None) -> bool:
    if not value:
        return True
    parsed = urlsplit(value)
    return (
        parsed.scheme == "https"
        and parsed.hostname == "api.openai.com"
        and parsed.path.rstrip("/") in ("", "/v1")
        and not parsed.query
        and not parsed.fragment
    )


def _is_litellm_route(model: str, source: Any | None) -> bool:
    if isinstance(source, LitellmModel):
        return True
    if model.startswith(_LITELLM_PREFIX):
        return True
    if get_openrouter_model_name(source):
        return False
    if model.startswith((_OPENAI_PREFIX, "openrouter/")):
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
    client = _source_openai_client(source)
    if client is not None and field in _OPENAI_CLIENT_FIELDS:
        return _client_value(client, field)
    return None


def _accepted_litellm_fields() -> set[str]:
    try:
        params = inspect.signature(LitellmModel).parameters
    except (TypeError, ValueError):
        return {"api_key", "base_url"}
    if any(param.kind == inspect.Parameter.VAR_KEYWORD for param in params.values()):
        return set(_LITELLM_CONFIG_FIELDS)
    return {field for field in _LITELLM_CONFIG_FIELDS if field in params}


def _make_litellm_model(model: str, source: Any | None) -> LitellmModel:
    bare = model[len(_LITELLM_PREFIX) :] if model.startswith(_LITELLM_PREFIX) else model
    kwargs: dict[str, Any] = {"model": bare}
    for field in _accepted_litellm_fields():
        value = _config_value(source, field)
        if value is not None:
            kwargs[field] = value
    return LitellmModel(**kwargs)


def make_internal_model(tool: Any) -> InternalModelRoute:
    """Clone the selected model and its transport for a Slides sub-agent."""
    model_name, source = _resolved_model(tool)

    if _is_litellm_route(model_name, source):
        return InternalModelRoute(
            model=_make_litellm_model(model_name, source),
            transport="litellm",
        )

    source_client = _source_openai_client(source)
    client = _clone_openai_client(source_client)
    openrouter_name = get_openrouter_model_name(source)
    if openrouter_name or is_openrouter_model_name(model_name):
        alias = (
            model_name
            if is_openrouter_model_name(model_name)
            else f"openrouter/{model_name}"
        )
        return InternalModelRoute(
            model=build_openrouter_chat_model(
                alias,
                openai_client=client,
                should_replay_reasoning_content=getattr(
                    source,
                    "should_replay_reasoning_content",
                    None,
                ),
            ),
            transport="openrouter",
        )

    base_url = str(client.base_url)
    if is_codex_base_url(base_url):
        return InternalModelRoute(
            model=_CodexResponsesModel(model=model_name, openai_client=client),
            transport="codex_responses",
        )

    if isinstance(source, OpenAIChatCompletionsModel) or not _is_direct_openai_url(
        base_url
    ):
        return InternalModelRoute(
            model=OpenAIChatCompletionsModel(
                model=model_name,
                openai_client=client,
            ),
            transport="chat_completions",
        )

    return InternalModelRoute(
        model=OpenAIResponsesModel(model=model_name, openai_client=client),
        transport="openai_responses",
    )


def make_internal_model_settings(route: InternalModelRoute) -> ModelSettings:
    """Use OpenAI-only settings only on verified Responses transports."""
    if route.transport == "openrouter":
        return ModelSettings(
            reasoning=Reasoning(effort="high", summary=None),
        )
    if route.transport not in {"openai_responses", "codex_responses"}:
        return ModelSettings()
    return ModelSettings(
        reasoning=Reasoning(effort="high", summary="auto"),
        verbosity=None if route.is_codex else "medium",
        store=False if route.is_codex else None,
    )


async def get_internal_agent_response(
    agent: Any,
    prompt: str,
    *,
    use_stream: bool = False,
    on_delta: Any | None = None,
) -> Any:
    """Run a helper agent and retain streamed text when final parsing is empty."""
    if not use_stream and on_delta is None:
        return await agent.get_response(prompt)

    stream = agent.get_response_stream(prompt)
    text_deltas: list[str] = []
    async for event in stream:
        data = getattr(event, "data", None)
        if getattr(data, "type", None) != "response.output_text.delta":
            continue
        delta = getattr(data, "delta", None)
        if not isinstance(delta, str) or not delta:
            continue
        text_deltas.append(delta)
        if on_delta is not None:
            try:
                on_delta(delta)
            except Exception:
                pass

    result = None
    final_error: Exception | None = None
    try:
        result = await stream.wait_final_result()
    except Exception as exc:
        final_error = exc

    if getattr(result, "final_output", None):
        return result

    assembled = "".join(text_deltas)
    if assembled:
        return _StreamResult(
            final_output=assembled,
            raw_responses=getattr(result, "raw_responses", []) or [],
        )
    if final_error is not None:
        raise final_error
    return result
