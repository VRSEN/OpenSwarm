"""OpenAI Agents SDK Model adapter that talks to Anthropic Messages API
through a local OpenAI-compatible router (9router/CLIProxyAPI/etc.).

Why this exists:
- LiteLLM via agency-swarm rejects router model namespaces like
  'cc/claude-opus-4-7' with 'Unknown prefix: cc'.
- The router (9router) authenticates against your Claude Pro / Max /
  Claude Code subscription itself; it expects the literal API key
  string '9router' on the Anthropic Messages endpoint and routes by
  the model id (cc/..., cx/..., gc/...).
- We hand agency-swarm a Model instance bound to that router so the
  rest of the framework treats it like any other Anthropic backend.

Auth:
- The Anthropic Python SDK is constructed with `api_key="9router"`
  and `base_url=<router URL>`. No OAuth token, no Bearer, no special
  beta header — the router does subscription auth on our behalf.
  This is the same pattern used by openswarm-ai's backend.

Translation:
- OpenAI Agents SDK input items (Responses-API-shaped) → Anthropic
  Messages API blocks (text / tool_use / tool_result).
- OpenAI tool / handoff schemas → Anthropic tool definitions.
- Anthropic content blocks → OpenAI Responses-style output items so
  agency-swarm consumes the response unchanged.

Streaming:
- stream_response drives anthropic.messages.stream() and emits
  per-token text-delta events plus a final completed event.
"""

from __future__ import annotations

import json
import os
import uuid
from typing import Any, AsyncIterator

try:
    import anthropic  # type: ignore
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "ClaudeRouterModel requires the `anthropic` package. "
        "Install with: pip install anthropic"
    ) from exc

from agents import Model, ModelResponse, ModelSettings, ModelTracing
from agents.handoffs import Handoff
from agents.tool import Tool
from agents.usage import Usage


_DEFAULT_ROUTER_URL = "http://localhost:20128"
_DEFAULT_MAX_TOKENS = 8192


class ClaudeRouterModel(Model):
    """Model adapter that calls Anthropic Messages API through a local router."""

    def __init__(
        self,
        model: str,
        base_url: str | None = None,
        api_key: str | None = None,
        max_tokens: int = _DEFAULT_MAX_TOKENS,
    ) -> None:
        # Convention used by 9router/CLIProxyAPI: literal string "9router"
        # in the api_key slot, the router itself authenticates upstream.
        # ANTHROPIC_BASE_URL takes precedence so the user can repoint to
        # any other Anthropic-Messages-compatible router.
        resolved_base = (
            base_url
            or os.getenv("ANTHROPIC_BASE_URL")
            or _strip_v1(os.getenv("OPENAI_BASE_URL", ""))
            or _DEFAULT_ROUTER_URL
        )
        resolved_key = api_key or os.getenv("ANTHROPIC_API_KEY") or "9router"

        self._client = anthropic.AsyncAnthropic(
            api_key=resolved_key,
            base_url=resolved_base,
        )
        self._model = model
        self._max_tokens = max_tokens

    # Backwards-compat alias.
    ClaudeOAuthModel = property(lambda self: self)

    async def get_response(
        self,
        system_instructions: str | None,
        input: str | list[Any],
        model_settings: ModelSettings,
        tools: list[Tool],
        output_schema: Any | None,
        handoffs: list[Handoff],
        tracing: ModelTracing,
        *,
        previous_response_id: str | None = None,
        conversation_id: str | None = None,
        prompt: Any | None = None,
    ) -> ModelResponse:
        messages = _input_to_anthropic_messages(input)
        system = _build_system_prompt(system_instructions, output_schema)
        anthropic_tools = _tools_to_anthropic(tools, handoffs)

        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": getattr(model_settings, "max_tokens", None) or self._max_tokens,
            "system": system,
            "messages": messages,
        }
        if anthropic_tools:
            kwargs["tools"] = anthropic_tools
        temperature = getattr(model_settings, "temperature", None)
        if temperature is not None:
            kwargs["temperature"] = temperature
        top_p = getattr(model_settings, "top_p", None)
        if top_p is not None:
            kwargs["top_p"] = top_p

        response = await self._client.messages.create(**kwargs)
        return _anthropic_response_to_model_response(response)

    def stream_response(
        self,
        system_instructions: str | None,
        input: str | list[Any],
        model_settings: ModelSettings,
        tools: list[Tool],
        output_schema: Any | None,
        handoffs: list[Handoff],
        tracing: ModelTracing,
        *,
        previous_response_id: str | None = None,
        conversation_id: str | None = None,
        prompt: Any | None = None,
    ) -> AsyncIterator[Any]:
        return self._stream_iter(
            system_instructions, input, model_settings, tools, output_schema,
            handoffs, tracing,
            previous_response_id=previous_response_id,
            conversation_id=conversation_id,
            prompt=prompt,
        )

    async def _stream_iter(
        self,
        system_instructions: str | None,
        input: str | list[Any],
        model_settings: ModelSettings,
        tools: list[Tool],
        output_schema: Any | None,
        handoffs: list[Handoff],
        tracing: ModelTracing,
        *,
        previous_response_id: str | None = None,
        conversation_id: str | None = None,
        prompt: Any | None = None,
    ) -> AsyncIterator[Any]:
        messages = _input_to_anthropic_messages(input)
        system = _build_system_prompt(system_instructions, output_schema)
        anthropic_tools = _tools_to_anthropic(tools, handoffs)

        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": getattr(model_settings, "max_tokens", None) or self._max_tokens,
            "system": system,
            "messages": messages,
        }
        if anthropic_tools:
            kwargs["tools"] = anthropic_tools
        temperature = getattr(model_settings, "temperature", None)
        if temperature is not None:
            kwargs["temperature"] = temperature

        seq = 0

        def _next() -> int:
            nonlocal seq
            seq += 1
            return seq

        try:
            from openai.types.responses import (  # noqa: PLC0415
                ResponseTextDeltaEvent,
                ResponseCompletedEvent,
                Response,
            )
            have_event_types = True
        except ImportError:
            have_event_types = False

        async with self._client.messages.stream(**kwargs) as stream:
            async for event in stream:
                etype = getattr(event, "type", None)
                if etype == "content_block_delta":
                    delta = getattr(event, "delta", None)
                    if getattr(delta, "type", None) == "text_delta" and have_event_types:
                        text = getattr(delta, "text", "") or ""
                        if not text:
                            continue
                        yield ResponseTextDeltaEvent.model_construct(
                            type="response.output_text.delta",
                            delta=text,
                            item_id=f"item_{getattr(event, 'index', 0) or 0}",
                            output_index=int(getattr(event, "index", 0) or 0),
                            content_index=0,
                            sequence_number=_next(),
                        )
            final = await stream.get_final_message()

        result = _anthropic_response_to_model_response(final)
        if have_event_types:
            yield ResponseCompletedEvent.model_construct(
                type="response.completed",
                sequence_number=_next(),
                response=Response.model_construct(
                    id=result.response_id,
                    object="response",
                    created_at=0.0,
                    model=self._model,
                    output=result.output,
                    parallel_tool_calls=False,
                    tool_choice="auto",
                    tools=[],
                    status="completed",
                    usage=None,
                ),
            )


# Backwards-compat: keep the old import name working.
ClaudeOAuthModel = ClaudeRouterModel


# ── translation helpers ──────────────────────────────────────────────────

def _strip_v1(url: str) -> str:
    if url.endswith("/v1"):
        return url[:-3]
    if url.endswith("/v1/"):
        return url[:-4]
    return url


def _build_system_prompt(
    system_instructions: str | None, output_schema: Any | None
) -> str:
    parts: list[str] = []
    if system_instructions:
        parts.append(system_instructions)
    if output_schema is not None:
        try:
            schema_json = json.dumps(output_schema.json_schema(), indent=2)
            parts.append(
                "Respond with a JSON object matching this schema "
                "(no markdown, no extra commentary):\n" + schema_json
            )
        except Exception:
            pass
    return "\n\n".join(parts) if parts else "You are a helpful assistant."


def _input_to_anthropic_messages(
    input_items: str | list[Any],
) -> list[dict[str, Any]]:
    if isinstance(input_items, str):
        return [{"role": "user", "content": [{"type": "text", "text": input_items}]}]

    messages: list[dict[str, Any]] = []
    pending_assistant_blocks: list[dict[str, Any]] = []
    pending_tool_results: list[dict[str, Any]] = []

    def _flush_assistant() -> None:
        if pending_assistant_blocks:
            messages.append({"role": "assistant", "content": list(pending_assistant_blocks)})
            pending_assistant_blocks.clear()

    def _flush_tool_results() -> None:
        if pending_tool_results:
            messages.append({"role": "user", "content": list(pending_tool_results)})
            pending_tool_results.clear()

    for item in input_items:
        d = _as_dict(item)
        item_type = d.get("type")

        if item_type == "function_call":
            _flush_tool_results()
            args = d.get("arguments")
            if isinstance(args, str):
                try:
                    args = json.loads(args) if args else {}
                except Exception:
                    args = {}
            pending_assistant_blocks.append({
                "type": "tool_use",
                "id": d.get("call_id") or d.get("id") or f"toolu_{uuid.uuid4().hex[:24]}",
                "name": d.get("name") or "",
                "input": args or {},
            })
            continue

        if item_type == "function_call_output":
            _flush_assistant()
            content = d.get("output")
            if not isinstance(content, str):
                try:
                    content = json.dumps(content)
                except Exception:
                    content = str(content)
            pending_tool_results.append({
                "type": "tool_result",
                "tool_use_id": d.get("call_id") or d.get("id") or "",
                "content": content,
            })
            continue

        if item_type == "reasoning":
            continue

        role = d.get("role") or ("assistant" if item_type == "message" and d.get("status") else "user")
        text = _extract_text(d)
        if text is None:
            continue

        if role == "assistant":
            _flush_tool_results()
            pending_assistant_blocks.append({"type": "text", "text": text})
        else:
            _flush_assistant()
            _flush_tool_results()
            messages.append({"role": "user", "content": [{"type": "text", "text": text}]})

    _flush_assistant()
    _flush_tool_results()

    if not messages:
        messages = [{"role": "user", "content": [{"type": "text", "text": ""}]}]
    return messages


def _as_dict(item: Any) -> dict[str, Any]:
    if isinstance(item, dict):
        return item
    if hasattr(item, "model_dump"):
        try:
            return item.model_dump()
        except Exception:
            pass
    if hasattr(item, "__dict__"):
        return dict(item.__dict__)
    return {}


def _extract_text(d: dict[str, Any]) -> str | None:
    content = d.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks: list[str] = []
        for c in content:
            cd = _as_dict(c)
            t = cd.get("type")
            if t in ("input_text", "output_text", "text"):
                txt = cd.get("text")
                if isinstance(txt, str):
                    chunks.append(txt)
        if chunks:
            return "\n".join(chunks)
    text = d.get("text")
    if isinstance(text, str):
        return text
    return None


def _tools_to_anthropic(tools: list[Tool], handoffs: list[Handoff]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for tool in list(tools) + list(handoffs):
        name = getattr(tool, "name", None)
        description = getattr(tool, "description", "") or ""
        schema = (
            getattr(tool, "params_json_schema", None)
            or getattr(tool, "input_schema", None)
            or {"type": "object", "properties": {}}
        )
        if name:
            out.append({
                "name": name,
                "description": description,
                "input_schema": schema,
            })
    return out


def _anthropic_response_to_model_response(response: Any) -> ModelResponse:
    output_items: list[Any] = []
    response_id = getattr(response, "id", None) or f"resp_{uuid.uuid4().hex}"
    content_blocks = getattr(response, "content", []) or []

    text_chunks: list[str] = []
    tool_calls: list[dict[str, Any]] = []
    for block in content_blocks:
        block_type = getattr(block, "type", None)
        if block_type == "text":
            text_chunks.append(getattr(block, "text", "") or "")
        elif block_type == "tool_use":
            tool_calls.append({
                "id": getattr(block, "id", "") or f"toolu_{uuid.uuid4().hex[:24]}",
                "name": getattr(block, "name", "") or "",
                "input": getattr(block, "input", {}) or {},
            })

    if text_chunks:
        output_items.append({
            "type": "message",
            "id": f"msg_{uuid.uuid4().hex}",
            "role": "assistant",
            "status": "completed",
            "content": [{"type": "output_text", "text": "".join(text_chunks), "annotations": []}],
        })

    for call in tool_calls:
        output_items.append({
            "type": "function_call",
            "id": call["id"],
            "call_id": call["id"],
            "name": call["name"],
            "arguments": json.dumps(call["input"]),
            "status": "completed",
        })

    usage = Usage()
    raw_usage = getattr(response, "usage", None)
    if raw_usage is not None:
        try:
            usage.input_tokens = int(getattr(raw_usage, "input_tokens", 0) or 0)
            usage.output_tokens = int(getattr(raw_usage, "output_tokens", 0) or 0)
            usage.total_tokens = usage.input_tokens + usage.output_tokens
            usage.requests = 1
        except Exception:
            pass

    return ModelResponse(
        output=output_items,
        usage=usage,
        response_id=response_id,
    )
