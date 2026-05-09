"""OpenAI Agents SDK Model adapter that runs Claude via the local
`claude` CLI using `claude_agent_sdk`.

Auth strategy (mirrors openswarm-ai):
    The local `claude` CLI carries the user's Claude Pro/Max/Claude
    Code subscription credentials (saved by `claude login`). The
    `claude_agent_sdk` Python package spawns that CLI and inherits its
    auth. We don't touch tokens, OAuth, or API keys — the SDK does it
    via the subprocess.

Usage flow:
    Each call to ClaudeAgentSDKModel.get_response():
      1. Builds an in-process SDK MCP server exposing agency-swarm's
         tools as MCP tools (so Claude can actually invoke them).
      2. Constructs ClaudeAgentOptions with that MCP server, the
         agent's system instructions, and Claude Code's built-in
         tools disabled (only our agency-swarm tools are exposed).
      3. Calls claude_agent_sdk.query() with the conversation
         transcript as a single prompt.
      4. The SDK runs Claude → tool → Claude … until Claude returns
         a final assistant message. All tool calls happen inside this
         one query() invocation.
      5. We translate the final messages back into OpenAI Responses-
         shaped output items so agency-swarm consumes them unchanged.

Limitations (acknowledged):
  - Past tool calls in the input are flattened into a text transcript;
    Claude can't re-issue them as if it had generated them itself.
  - Claude Code's built-in tools (Bash, WebSearch, Edit) are disabled
    by default to keep behavior parity with agency-swarm. Set
    CLAUDE_USE_BUILTIN_TOOLS=1 to re-enable them.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from typing import Any, AsyncIterator

try:
    from claude_agent_sdk import (  # type: ignore
        query as _sdk_query,
        ClaudeAgentOptions,
        AssistantMessage,
        ResultMessage,
        SystemMessage,
        UserMessage,
        tool as _sdk_tool,
        create_sdk_mcp_server,
    )
    from claude_agent_sdk.types import (  # type: ignore
        TextBlock,
        ToolUseBlock,
    )
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "ClaudeAgentSDKModel requires the `claude-agent-sdk` package. "
        "Install with: pip install claude-agent-sdk\n"
        "It also requires the `claude` CLI to be installed and logged in "
        "(`claude login`)."
    ) from exc

from agents import Model, ModelResponse, ModelSettings, ModelTracing
from agents.handoffs import Handoff
from agents.tool import Tool
from agents.usage import Usage


class ClaudeAgentSDKModel(Model):
    """Model adapter backed by `claude_agent_sdk` + local `claude` CLI."""

    def __init__(self, model: str) -> None:
        self._model = model
        self._use_builtin_tools = os.getenv("CLAUDE_USE_BUILTIN_TOOLS", "").lower() in ("1", "true", "yes")

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
        text_chunks: list[str] = []
        tool_calls: list[dict[str, Any]] = []
        usage = Usage()

        async for msg in self._run_query(
            system_instructions, input, tools, handoffs, output_schema
        ):
            if isinstance(msg, AssistantMessage):
                for block in getattr(msg, "content", []) or []:
                    if isinstance(block, TextBlock):
                        t = getattr(block, "text", "") or ""
                        if t:
                            text_chunks.append(t)
                    elif isinstance(block, ToolUseBlock):
                        # Captured for visibility; the SDK already
                        # executed the tool via our MCP server before
                        # this final assembly.
                        tool_calls.append({
                            "id": getattr(block, "id", "") or f"toolu_{uuid.uuid4().hex[:24]}",
                            "name": _strip_mcp_prefix(getattr(block, "name", "") or ""),
                            "input": getattr(block, "input", {}) or {},
                        })
            elif isinstance(msg, ResultMessage):
                _accumulate_usage(usage, msg)

        return _build_model_response(text_chunks, tool_calls, usage)

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
        try:
            from openai.types.responses import (  # noqa: PLC0415
                ResponseTextDeltaEvent,
                ResponseCompletedEvent,
                Response,
            )
            have_event_types = True
        except ImportError:
            have_event_types = False

        seq = 0

        def _next() -> int:
            nonlocal seq
            seq += 1
            return seq

        text_chunks: list[str] = []
        tool_calls: list[dict[str, Any]] = []
        usage = Usage()

        async for msg in self._run_query(
            system_instructions, input, tools, handoffs, output_schema
        ):
            if isinstance(msg, AssistantMessage):
                for block in getattr(msg, "content", []) or []:
                    if isinstance(block, TextBlock):
                        t = getattr(block, "text", "") or ""
                        if not t:
                            continue
                        text_chunks.append(t)
                        if have_event_types:
                            yield ResponseTextDeltaEvent.model_construct(
                                type="response.output_text.delta",
                                delta=t,
                                item_id="item_0",
                                output_index=0,
                                content_index=0,
                                sequence_number=_next(),
                            )
                    elif isinstance(block, ToolUseBlock):
                        tool_calls.append({
                            "id": getattr(block, "id", "") or f"toolu_{uuid.uuid4().hex[:24]}",
                            "name": _strip_mcp_prefix(getattr(block, "name", "") or ""),
                            "input": getattr(block, "input", {}) or {},
                        })
            elif isinstance(msg, ResultMessage):
                _accumulate_usage(usage, msg)

        result = _build_model_response(text_chunks, tool_calls, usage)
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

    # ── internals ────────────────────────────────────────────────────────

    async def _run_query(
        self,
        system_instructions: str | None,
        input: str | list[Any],
        tools: list[Tool],
        handoffs: list[Handoff],
        output_schema: Any | None,
    ):
        prompt = _input_to_prompt(input)
        sdk_tools, tool_name_index = _wrap_tools_for_sdk(tools, handoffs)

        options_kwargs: dict[str, Any] = {
            "model": self._model,
            "system_prompt": _build_system_prompt(system_instructions, output_schema),
            "permission_mode": "bypassPermissions",
        }

        mcp_servers: dict[str, Any] = {}
        allowed_tools: list[str] = []
        if sdk_tools:
            mcp_servers["agency"] = create_sdk_mcp_server(name="agency", tools=sdk_tools)
            allowed_tools = [f"mcp__agency__{name}" for name in tool_name_index]

        if not self._use_builtin_tools:
            # Restrict the run to only our wrapped tools — keeps behavior
            # consistent with agency-swarm's tool surface. To re-enable
            # Claude Code's built-ins (Bash, WebSearch, etc.) set
            # CLAUDE_USE_BUILTIN_TOOLS=1.
            options_kwargs["allowed_tools"] = allowed_tools
            options_kwargs["disallowed_tools"] = ["Bash", "Edit", "Write", "Read", "WebSearch", "Grep", "Glob"]

        if mcp_servers:
            options_kwargs["mcp_servers"] = mcp_servers

        options = ClaudeAgentOptions(**options_kwargs)

        async for msg in _sdk_query(prompt=prompt, options=options):
            yield msg


# ── helpers ──────────────────────────────────────────────────────────────

_MCP_NAME_RE = re.compile(r"[^A-Za-z0-9_]")


def _sanitize_tool_name(name: str) -> str:
    """Make a name MCP-safe: only alnum + underscore."""
    cleaned = _MCP_NAME_RE.sub("_", name or "tool")
    return cleaned[:60] or "tool"


def _strip_mcp_prefix(name: str) -> str:
    """'mcp__agency__SomeTool' → 'SomeTool'."""
    if name.startswith("mcp__"):
        parts = name.split("__", 2)
        if len(parts) == 3:
            return parts[2]
    return name


def _wrap_tools_for_sdk(
    tools: list[Tool], handoffs: list[Handoff]
) -> tuple[list[Any], list[str]]:
    """Wrap each agency-swarm tool/handoff as a claude_agent_sdk @tool."""
    sdk_tools: list[Any] = []
    names: list[str] = []
    for t in list(tools) + list(handoffs):
        name = _sanitize_tool_name(getattr(t, "name", "") or f"tool_{len(sdk_tools)}")
        description = getattr(t, "description", "") or name
        schema = (
            getattr(t, "params_json_schema", None)
            or getattr(t, "input_schema", None)
            or {"type": "object", "properties": {}}
        )

        # Capture in default args to pin per-iteration values.
        async def _wrapper(args: dict, _t=t, _name=name) -> dict:
            try:
                args_json = json.dumps(args or {})
                invoke = getattr(_t, "on_invoke_tool", None)
                if invoke is None:
                    return _mcp_text_result(f"Tool {_name} has no on_invoke_tool method")
                # ctx=None — agency-swarm tools that need context will
                # raise; the error text is surfaced to Claude as the
                # tool result so the run continues.
                result = await invoke(None, args_json)
                if isinstance(result, (dict, list)):
                    text = json.dumps(result)
                else:
                    text = str(result)
                return _mcp_text_result(text)
            except Exception as e:
                return _mcp_text_result(f"Tool error in {_name}: {e}")

        # claude_agent_sdk's @tool decorator returns a wrapped tool spec.
        sdk_tools.append(_sdk_tool(name, description, schema)(_wrapper))
        names.append(name)
    return sdk_tools, names


def _mcp_text_result(text: str) -> dict:
    return {"content": [{"type": "text", "text": text[:50_000]}]}


def _build_system_prompt(system_instructions: str | None, output_schema: Any | None) -> str:
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


def _input_to_prompt(input_items: str | list[Any]) -> str:
    """Flatten the OpenAI Responses-style input into a single text prompt.

    Past tool calls/results are included as text so Claude has context,
    but we don't try to replay them as native tool_use blocks (Claude
    can't reissue something it didn't generate this run).
    """
    if isinstance(input_items, str):
        return input_items

    lines: list[str] = []
    for item in input_items:
        d = _as_dict(item)
        item_type = d.get("type")

        if item_type == "function_call":
            args = d.get("arguments")
            if isinstance(args, str):
                args_repr = args
            else:
                try:
                    args_repr = json.dumps(args)
                except Exception:
                    args_repr = str(args)
            lines.append(f"[assistant tool call] {d.get('name', '')}({args_repr})")
            continue
        if item_type == "function_call_output":
            out = d.get("output")
            if not isinstance(out, str):
                try:
                    out = json.dumps(out)
                except Exception:
                    out = str(out)
            lines.append(f"[tool result] {out}")
            continue
        if item_type == "reasoning":
            continue

        text = _extract_text(d)
        if text is None:
            continue
        role = d.get("role") or "user"
        if role == "assistant":
            lines.append(f"Assistant: {text}")
        elif role == "system":
            lines.append(f"System: {text}")
        else:
            lines.append(f"User: {text}")

    if not lines:
        return ""

    # The actual NEW user message is whatever the agent just said —
    # that's the last 'User: ...' or the last item overall. Keep it
    # all together as a transcript ending with the latest turn.
    return "\n".join(lines)


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


def _accumulate_usage(usage: Usage, msg: Any) -> None:
    raw = getattr(msg, "usage", None) or {}
    if isinstance(raw, dict):
        try:
            usage.input_tokens += int(raw.get("input_tokens", 0) or 0)
            usage.output_tokens += int(raw.get("output_tokens", 0) or 0)
            usage.total_tokens = usage.input_tokens + usage.output_tokens
            usage.requests += 1
        except Exception:
            pass


def _build_model_response(
    text_chunks: list[str],
    tool_calls: list[dict[str, Any]],
    usage: Usage,
) -> ModelResponse:
    output_items: list[Any] = []
    if text_chunks:
        output_items.append({
            "type": "message",
            "id": f"msg_{uuid.uuid4().hex}",
            "role": "assistant",
            "status": "completed",
            "content": [{
                "type": "output_text",
                "text": "".join(text_chunks),
                "annotations": [],
            }],
        })
    # Note: tool_calls are NOT re-emitted as function_call output items.
    # The SDK already executed the tools internally via our MCP server,
    # so agency-swarm doesn't need to dispatch them again. Re-emitting
    # would cause the runner to call the tools a second time.

    return ModelResponse(
        output=output_items,
        usage=usage,
        response_id=f"resp_{uuid.uuid4().hex}",
    )


# Backwards-compat aliases so existing imports keep working.
ClaudeOAuthModel = ClaudeAgentSDKModel
ClaudeRouterModel = ClaudeAgentSDKModel
