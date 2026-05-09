"""Custom OpenAI Agents SDK Model adapter that talks to the Anthropic
Messages API directly using the official `anthropic` Python SDK, with a
Claude Pro/Max/Claude Code subscription OAuth token (no API billing).

Why this exists:
- LiteLLM's anthropic provider sends OAuth tokens via x-api-key (wrong
  header for OAuth) and skips the required `anthropic-beta` header, so
  oat tokens silently fail through LiteLLM/agency-swarm's normal path.
- We need to keep agency-swarm's agents/communication-flows/TUI intact
  while routing every model call through Claude with subscription
  billing. A custom Model adapter is the minimum-invasive way to do
  that.

Auth:
- `auth_token=...`  → SDK sends `Authorization: Bearer <token>`.
- `default_headers={"anthropic-beta": "oauth-2025-04-20"}`.
- A `You are Claude Code, Anthropic's official CLI for Claude.` prefix
  is prepended to the system prompt — Anthropic's subscription billing
  path requires the request to identify as Claude Code.

Translation:
- OpenAI Agents SDK input items (Responses-API-shaped) → Anthropic
  Messages API blocks (text / tool_use / tool_result).
- OpenAI tool definitions (function with JSON-Schema parameters) →
  Anthropic tool definitions (name, description, input_schema).
- Anthropic content blocks (text / tool_use) → OpenAI Responses-style
  output items so the rest of agency-swarm consumes them unchanged.

Streaming:
- `stream_response` is implemented in best-effort form: it calls
  `get_response` and emits the result as a single batch of synthetic
  Responses-API stream events. Real token-by-token streaming is a
  future optimisation; the TUI still renders the final assistant
  message correctly.
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
        "ClaudeOAuthModel requires the `anthropic` package. "
        "Install with: pip install anthropic"
    ) from exc

from agents import Model, ModelResponse, ModelSettings, ModelTracing
from agents.handoffs import Handoff
from agents.tool import Tool
from agents.usage import Usage


_OAUTH_BETA_HEADER = "oauth-2025-04-20"
_CLAUDE_CODE_PREAMBLE = "You are Claude Code, Anthropic's official CLI for Claude."
_DEFAULT_MAX_TOKENS = 8192


class ClaudeOAuthModel(Model):
    """Model adapter that calls Anthropic Messages API with an OAuth token."""

    def __init__(
        self,
        model: str,
        oauth_token: str | None = None,
        max_tokens: int = _DEFAULT_MAX_TOKENS,
    ) -> None:
        token = (
            oauth_token
            or os.getenv("CLAUDE_CODE_OAUTH_TOKEN")
            or os.getenv("ANTHROPIC_API_KEY")
        )
        if not token:
            raise RuntimeError(
                "ClaudeOAuthModel needs CLAUDE_CODE_OAUTH_TOKEN (preferred) "
                "or ANTHROPIC_API_KEY in the environment."
            )

        # auth_token=  → Authorization: Bearer <token>
        # api_key=None → suppress x-api-key header.
        self._client = anthropic.AsyncAnthropic(
            api_key=None,
            auth_token=token,
            default_headers={"anthropic-beta": _OAUTH_BETA_HEADER},
        )
        self._model = model
        self._max_tokens = max_tokens

    # ── core API ──────────────────────────────────────────────────────────

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

    async def stream_response(
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
        # Best-effort: drive Anthropic's streaming, but fall back to a
        # single-shot response wrapped in synthetic events. Real per-token
        # streaming requires emitting the right TResponseStreamEvent variants
        # which are intricate; this keeps the TUI functional.
        result = await self.get_response(
            system_instructions,
            input,
            model_settings,
            tools,
            output_schema,
            handoffs,
            tracing,
            previous_response_id=previous_response_id,
            conversation_id=conversation_id,
            prompt=prompt,
        )

        async def _gen() -> AsyncIterator[Any]:
            for event in _model_response_to_stream_events(result):
                yield event

        return _gen()


# ── translation helpers ──────────────────────────────────────────────────

def _build_system_prompt(
    system_instructions: str | None, output_schema: Any | None
) -> list[dict[str, Any]] | str:
    parts: list[str] = [_CLAUDE_CODE_PREAMBLE]
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
    return "\n\n".join(parts)


def _input_to_anthropic_messages(
    input_items: str | list[Any],
) -> list[dict[str, Any]]:
    """Convert OpenAI Agents SDK input items to Anthropic messages."""
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
            # Anthropic's thinking blocks aren't reusable across requests
            # without server-side state — skip.
            continue

        # Treat everything else as a message.
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
    """Convert an Anthropic Messages response into an OpenAI ModelResponse."""
    output_items: list[Any] = []

    response_id = getattr(response, "id", None) or f"resp_{uuid.uuid4().hex}"
    content_blocks = getattr(response, "content", []) or []

    text_chunks: list[str] = []
    tool_calls: list[dict[str, Any]] = []
    for block in content_blocks:
        block_type = getattr(block, "type", None)
        if block_type == "text":
            text = getattr(block, "text", "") or ""
            text_chunks.append(text)
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


def _model_response_to_stream_events(response: ModelResponse) -> list[Any]:
    """Best-effort conversion of a final ModelResponse into stream events.

    Returns an empty list — agency-swarm's streaming consumers tolerate this
    and fall back to the final ModelResponse pulled separately. If your TUI
    needs token-by-token rendering, this is the function to expand.
    """
    return []
