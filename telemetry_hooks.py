from __future__ import annotations

import contextvars
import inspect
import logging
import time
import types
import uuid
from collections.abc import Iterable
from typing import Any

from agents.lifecycle import AgentHooksBase, RunHooksBase

import telemetry

logger = logging.getLogger(__name__)
_trusted_message_context: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
    "openswarm_trusted_message_context",
    default=None,
)
_trusted_thread_managers: dict[int, dict[str, Any]] = {}
_MESSAGE_TYPES = {"message"}
_TOOL_ERROR_PREFIXES = ("❌", "error", "failed", "failure", "html validation failed", "an error occurred")
_logged_tool_failure_keys: dict[tuple[int, str, str], float] = {}


class ToolReturnedError(Exception):
    """Marker exception for tools that report failure as their return value."""


class CompositeRunHooks(RunHooksBase[Any, Any]):
    """Run hook fan-out that preserves existing user or persistence hooks."""

    def __init__(self, *hooks: RunHooksBase[Any, Any] | None) -> None:
        self.hooks = [hook for hook in hooks if hook is not None and not isinstance(hook, OpenSwarmTelemetryRunHooks)]
        self.telemetry_hooks = OpenSwarmTelemetryRunHooks()

    async def _invoke(self, hook: Any, method_name: str, *args: Any) -> None:
        method = getattr(hook, method_name, None)
        if method is None:
            return
        result = method(*args)
        if inspect.isawaitable(result):
            await result

    async def _call(self, method_name: str, *args: Any) -> None:
        for hook in self.hooks:
            await self._invoke(hook, method_name, *args)
        try:
            await self._invoke(self.telemetry_hooks, method_name, *args)
        except Exception:
            logger.debug("Telemetry run hook %s failed", method_name, exc_info=True)

    async def on_llm_start(self, context: Any, agent: Any, system_prompt: str | None, input_items: list[Any]) -> None:
        await self._call("on_llm_start", context, agent, system_prompt, input_items)

    async def on_llm_end(self, context: Any, agent: Any, response: Any) -> None:
        await self._call("on_llm_end", context, agent, response)

    async def on_agent_start(self, context: Any, agent: Any) -> None:
        await self._call("on_agent_start", context, agent)

    async def on_agent_end(self, context: Any, agent: Any, output: Any) -> None:
        await self._call("on_agent_end", context, agent, output)

    async def on_handoff(self, context: Any, from_agent: Any, to_agent: Any) -> None:
        await self._call("on_handoff", context, from_agent, to_agent)

    async def on_tool_start(self, context: Any, agent: Any, tool: Any) -> None:
        await self._call("on_tool_start", context, agent, tool)

    async def on_tool_end(self, context: Any, agent: Any, tool: Any, result: str) -> None:
        await self._call("on_tool_end", context, agent, tool, result)


class CompositeAgentHooks(AgentHooksBase[Any, Any]):
    """Agent hook fan-out that keeps any pre-existing per-agent hooks active."""

    def __init__(self, *hooks: AgentHooksBase[Any, Any] | None) -> None:
        self.hooks = [hook for hook in hooks if hook is not None and not isinstance(hook, OpenSwarmTelemetryAgentHooks)]
        self.telemetry_hooks = OpenSwarmTelemetryAgentHooks()

    async def _invoke(self, hook: Any, method_name: str, *args: Any) -> None:
        method = getattr(hook, method_name, None)
        if method is None:
            return
        result = method(*args)
        if inspect.isawaitable(result):
            await result

    async def _call(self, method_name: str, *args: Any) -> None:
        for hook in self.hooks:
            await self._invoke(hook, method_name, *args)
        try:
            await self._invoke(self.telemetry_hooks, method_name, *args)
        except Exception:
            logger.debug("Telemetry agent hook %s failed", method_name, exc_info=True)

    async def on_start(self, context: Any, agent: Any) -> None:
        await self._call("on_start", context, agent)

    async def on_end(self, context: Any, agent: Any, output: Any) -> None:
        await self._call("on_end", context, agent, output)

    async def on_handoff(self, context: Any, agent: Any, source: Any) -> None:
        await self._call("on_handoff", context, agent, source)

    async def on_tool_start(self, context: Any, agent: Any, tool: Any) -> None:
        await self._call("on_tool_start", context, agent, tool)

    async def on_tool_end(self, context: Any, agent: Any, tool: Any, result: str) -> None:
        await self._call("on_tool_end", context, agent, tool, result)

    async def on_llm_start(self, context: Any, agent: Any, system_prompt: str | None, input_items: list[Any]) -> None:
        await self._call("on_llm_start", context, agent, system_prompt, input_items)

    async def on_llm_end(self, context: Any, agent: Any, response: Any) -> None:
        await self._call("on_llm_end", context, agent, response)


class OpenSwarmTelemetryRunHooks(RunHooksBase[Any, Any]):
    """Run hook placeholder so composition remains explicit and future-safe."""


class OpenSwarmTelemetryAgentHooks(AgentHooksBase[Any, Any]):
    def __init__(self) -> None:
        self._agent_start_times: dict[tuple[int, str], float] = {}
        self._tool_start_times: dict[tuple[int, str, str], float] = {}
        self._llm_start_times: dict[tuple[int, str], float] = {}

    async def on_start(self, context: Any, agent: Any) -> None:
        key = _context_agent_key(context, agent)
        self._agent_start_times[key] = time.monotonic()
        props = _agent_props(context, agent, status="started")
        _set_trusted_message_context(props)
        _safe_capture("agent_run_started", props)

    async def on_end(self, context: Any, agent: Any, output: Any) -> None:
        key = _context_agent_key(context, agent)
        started = self._agent_start_times.pop(key, None)
        _safe_capture(
            "agent_run_completed",
            _agent_props(
                context,
                agent,
                status="completed",
                latency_ms=_elapsed_ms(started),
            ),
        )

    async def on_tool_start(self, context: Any, agent: Any, tool: Any) -> None:
        tool_name = _tool_name(tool)
        self._tool_start_times[_context_tool_key(context, agent, tool_name)] = time.monotonic()

    async def on_tool_end(self, context: Any, agent: Any, tool: Any, result: str) -> None:
        tool_name = _tool_name(tool)
        key = _context_tool_key(context, agent, tool_name)
        started = self._tool_start_times.pop(key, None)
        if _logged_tool_failure_keys.pop(key, None) is not None:
            return
        if _is_tool_error_result(result):
            _capture_tool_failure(
                context,
                agent,
                tool_name,
                started_at=started,
                error=ToolReturnedError(),
            )
            return
        _capture_tool_invoked(context, agent, tool_name, status="completed", started_at=started)

    async def on_handoff(self, context: Any, agent: Any, source: Any) -> None:
        source_name = _agent_name(source)
        props = _agent_props(context, agent, status="completed")
        _set_trusted_message_context(props)
        if source_name:
            props["caller_agent_name"] = source_name
            props["parent_agent_id"] = telemetry.agent_id(source_name)
        _safe_capture("handoff", props)

    async def on_llm_start(self, context: Any, agent: Any, system_prompt: str | None, input_items: list[Any]) -> None:
        self._llm_start_times[_context_agent_key(context, agent)] = time.monotonic()

    async def on_llm_end(self, context: Any, agent: Any, response: Any) -> None:
        key = _context_agent_key(context, agent)
        started = self._llm_start_times.pop(key, None)
        props = _agent_props(context, agent, status="completed", latency_ms=_elapsed_ms(started))
        props.update(_usage_props_from_response(response))
        stop_reason = _stop_reason(response)
        if stop_reason:
            props["stop_reason"] = stop_reason
        _safe_capture("llm_generation_completed", props)


class TelemetryStreamingRunResponse:
    """Proxy that records completion/error only after a stream is consumed."""

    def __init__(self, stream: Any, base_props: dict[str, Any], started_at: float) -> None:
        self._stream = stream
        self._base_props = base_props
        self._started_at = started_at
        self._finished = False
        self._cancelled = False

    def __getattr__(self, name: str) -> Any:
        return getattr(self._stream, name)

    def __aiter__(self) -> Any:
        return self

    async def __anext__(self) -> Any:
        token = _set_trusted_message_context(self._base_props)
        try:
            return await self._stream.__anext__()
        except StopAsyncIteration:
            self._complete(status="cancelled" if self._cancelled else "completed")
            raise
        except BaseException as exc:
            self._error(exc)
            raise
        finally:
            _reset_trusted_message_context(token)

    async def asend(self, value: Any) -> Any:
        token = _set_trusted_message_context(self._base_props)
        try:
            return await self._stream.asend(value)
        except StopAsyncIteration:
            self._complete(status="cancelled" if self._cancelled else "completed")
            raise
        except BaseException as exc:
            self._error(exc)
            raise
        finally:
            _reset_trusted_message_context(token)

    async def athrow(self, typ: Any, val: Any = None, tb: Any = None) -> Any:
        token = _set_trusted_message_context(self._base_props)
        try:
            return await self._stream.athrow(typ, val, tb)
        except BaseException as exc:
            self._error(exc)
            raise
        finally:
            _reset_trusted_message_context(token)

    async def aclose(self) -> None:
        token = _set_trusted_message_context(self._base_props)
        try:
            await self._stream.aclose()
        except BaseException as exc:
            self._error(exc)
            raise
        finally:
            self._complete(status="cancelled" if self._cancelled else "closed")
            _reset_trusted_message_context(token)

    def cancel(self, mode: str = "immediate") -> None:
        self._cancelled = True
        cancel = getattr(self._stream, "cancel", None)
        if callable(cancel):
            cancel(mode=mode)

    async def wait_final_result(self) -> Any:
        token = _set_trusted_message_context(self._base_props)
        try:
            result = await self._stream.wait_final_result()
        except BaseException as exc:
            self._error(exc)
            raise
        finally:
            _reset_trusted_message_context(token)
        self._complete(status="cancelled" if self._cancelled else "completed", run_result=result)
        return result

    @property
    def final_result(self) -> Any:
        return getattr(self._stream, "final_result", None)

    @property
    def final_output(self) -> Any:
        return getattr(self._stream, "final_output", None)

    def _adopt_stream(self, other: Any) -> None:
        adopt = getattr(self._stream, "_adopt_stream", None)
        if callable(adopt):
            adopt(other)

    def _complete(self, *, status: str, run_result: Any | None = None) -> None:
        if self._finished:
            return
        self._finished = True
        props = dict(self._base_props)
        props.update({"status": status, "latency_ms": _elapsed_ms(self._started_at)})
        props.update(_usage_props_from_run_result(run_result if run_result is not None else self.final_result))
        _safe_capture("swarm_run_completed", props)

    def _error(self, exc: BaseException) -> None:
        if self._finished:
            return
        self._finished = True
        props = dict(self._base_props)
        props.update({"status": "error", "latency_ms": _elapsed_ms(self._started_at)})
        _safe_capture_error(exc, category="swarm_run", properties=props)


def instrument_agency(agency: Any) -> Any:
    """Attach OpenSwarm telemetry to an Agency instance without replacing hooks."""

    install_thread_manager_telemetry()
    _register_thread_manager_context(agency)
    agents = _iter_agents(agency)
    _attach_agent_hooks(agents)
    _wrap_agent_tools(agents)
    _wrap_agency_methods(agency)
    if getattr(agency, "persistence_hooks", None) is not None:
        agency.persistence_hooks = compose_run_hooks(agency.persistence_hooks)
    return agency


def compose_run_hooks(hooks: RunHooksBase[Any, Any] | None) -> RunHooksBase[Any, Any] | None:
    if hooks is None:
        return None
    if isinstance(hooks, CompositeRunHooks):
        return hooks
    return CompositeRunHooks(hooks)


def compose_agent_hooks(hooks: AgentHooksBase[Any, Any] | None) -> AgentHooksBase[Any, Any]:
    if isinstance(hooks, CompositeAgentHooks):
        return hooks
    return CompositeAgentHooks(hooks)


def install_thread_manager_telemetry() -> None:
    from agency_swarm.utils.thread import ThreadManager

    if getattr(ThreadManager, "_openswarm_telemetry_wrapped", False):
        return

    original_add_message = ThreadManager.add_message
    original_add_messages = ThreadManager.add_messages

    def add_message(self: Any, message: Any) -> Any:
        result = original_add_message(self, message)
        try:
            _capture_message_sent(message, self)
        except Exception:
            logger.debug("Telemetry message capture failed", exc_info=True)
        return result

    def add_messages(self: Any, messages: list[Any]) -> Any:
        result = original_add_messages(self, messages)
        for message in messages or []:
            try:
                _capture_message_sent(message, self)
            except Exception:
                logger.debug("Telemetry message capture failed", exc_info=True)
        return result

    ThreadManager.add_message = add_message
    ThreadManager.add_messages = add_messages
    ThreadManager._openswarm_telemetry_wrapped = True


def _wrap_agency_methods(agency: Any) -> None:
    if getattr(agency, "_openswarm_telemetry_wrapped", False):
        return

    original_get_response = agency.get_response
    original_get_response_stream = agency.get_response_stream

    async def get_response_with_telemetry(self: Any, *args: Any, **kwargs: Any) -> Any:
        args = _compose_hooks_override(args, kwargs)
        props = _swarm_props(self, args, kwargs, is_streaming=False, status="started")
        started_at = time.monotonic()
        _safe_capture("swarm_run_started", props)
        token = _set_trusted_message_context(props)
        try:
            result = await original_get_response(*args, **kwargs)
        except BaseException as exc:
            error_props = dict(props)
            error_props.update({"status": "error", "latency_ms": _elapsed_ms(started_at)})
            _safe_capture_error(exc, category="swarm_run", properties=error_props)
            raise
        finally:
            _reset_trusted_message_context(token)
        completed_props = dict(props)
        completed_props.update({"status": "completed", "latency_ms": _elapsed_ms(started_at)})
        completed_props.update(_usage_props_from_run_result(result))
        _safe_capture("swarm_run_completed", completed_props)
        return result

    def get_response_stream_with_telemetry(self: Any, *args: Any, **kwargs: Any) -> Any:
        args = _compose_hooks_override(args, kwargs)
        props = _swarm_props(self, args, kwargs, is_streaming=True, status="started")
        started_at = time.monotonic()
        _safe_capture("swarm_run_started", props)
        try:
            stream = original_get_response_stream(*args, **kwargs)
        except BaseException as exc:
            error_props = dict(props)
            error_props.update({"status": "error", "latency_ms": _elapsed_ms(started_at)})
            _safe_capture_error(exc, category="swarm_run", properties=error_props)
            raise
        return TelemetryStreamingRunResponse(stream, props, started_at)

    agency.get_response = types.MethodType(get_response_with_telemetry, agency)
    agency.get_response_stream = types.MethodType(get_response_stream_with_telemetry, agency)
    agency._openswarm_telemetry_wrapped = True


def _compose_hooks_override(args: tuple[Any, ...], kwargs: dict[str, Any]) -> tuple[Any, ...]:
    if "hooks_override" in kwargs and kwargs["hooks_override"] is not None:
        kwargs["hooks_override"] = compose_run_hooks(kwargs["hooks_override"])
        return args
    if len(args) <= 3 or args[3] is None:
        return args
    mutable_args = list(args)
    mutable_args[3] = compose_run_hooks(mutable_args[3])
    return tuple(mutable_args)


def _attach_agent_hooks(agents: Iterable[Any]) -> None:
    for agent in agents:
        try:
            agent.hooks = compose_agent_hooks(getattr(agent, "hooks", None))
        except Exception:
            logger.debug("Could not attach telemetry hooks to agent", exc_info=True)


def _wrap_agent_tools(agents: Iterable[Any]) -> None:
    for agent in agents:
        for tool in _iter_agent_tools(agent):
            try:
                _wrap_tool_invocation(agent, tool)
            except Exception:
                logger.debug("Could not attach telemetry wrapper to tool", exc_info=True)


def _iter_agent_tools(agent: Any) -> list[Any]:
    tools = getattr(agent, "tools", None)
    if tools is None:
        return []
    if isinstance(tools, dict):
        return list(tools.values())
    return list(tools or [])


def _wrap_tool_invocation(agent: Any, tool: Any) -> None:
    if getattr(tool, "_openswarm_telemetry_wrapped", False):
        return
    original = getattr(tool, "on_invoke_tool", None)
    if not callable(original):
        return
    tool_name = _tool_name(tool)

    async def on_invoke_tool_with_telemetry(context: Any, args_json: str) -> Any:
        started = time.monotonic()
        try:
            result = original(context, args_json)
            if inspect.isawaitable(result):
                result = await result
            if _is_tool_error_result(result):
                _remember_tool_failure_logged(context, agent, tool_name)
                _capture_tool_failure(
                    context,
                    agent,
                    tool_name,
                    started_at=started,
                    error=ToolReturnedError(),
                )
            return result
        except BaseException as exc:
            _remember_tool_failure_logged(context, agent, tool_name)
            _capture_tool_failure(
                context,
                agent,
                tool_name,
                started_at=started,
                error=exc,
            )
            raise

    tool.on_invoke_tool = on_invoke_tool_with_telemetry
    tool._openswarm_telemetry_wrapped = True


def _iter_agents(agency: Any) -> list[Any]:
    raw_agents = getattr(agency, "agents", None)
    if isinstance(raw_agents, dict):
        return list(raw_agents.values())
    if raw_agents is not None:
        return list(raw_agents)
    entry_points = getattr(agency, "entry_points", None)
    return list(entry_points or [])


def _register_thread_manager_context(agency: Any) -> None:
    manager = getattr(agency, "thread_manager", None)
    if manager is None:
        return
    agent_names = {name for name in (_agent_name(agent) for agent in _iter_agents(agency)) if name}
    _trusted_thread_managers[id(manager)] = {"agent_names": agent_names}


def _capture_message_sent(message: Any, manager: Any) -> None:
    if not isinstance(message, dict):
        return
    role = message.get("role")
    if role not in {"user", "assistant"}:
        return
    trusted_context = _message_context_for(manager)
    known_agent_names = trusted_context.get("agent_names") or set()
    agent_name = _trusted_agent_name(trusted_context, known_agent_names)
    caller_agent_name = _trusted_message_agent_name(message.get("callerAgent"), known_agent_names)
    props: dict[str, Any] = {
        "message_role": role,
        "message_type": _safe_message_type(message.get("type")),
        "thread_id": telemetry.thread_id(id(manager)),
        "session_id": telemetry._SESSION_ID,
        "is_streaming": bool(trusted_context.get("is_streaming", False)),
    }
    if agent_name:
        props["agent_name"] = agent_name
        props["agent_id"] = telemetry.agent_id(agent_name)
    if caller_agent_name:
        props["caller_agent_name"] = caller_agent_name
    for key in ("agent_run_id", "parent_run_id", "run_trace_id"):
        value = _safe_text(trusted_context.get(key))
        if value:
            props[key] = value
    _safe_capture("message_sent", props)


def _message_context_for(manager: Any) -> dict[str, Any]:
    context = dict(_trusted_message_context.get() or {})
    manager_context = _trusted_thread_managers.get(id(manager), {})
    agent_names = set(manager_context.get("agent_names") or set())
    agent_names.update(context.get("agent_names") or set())
    context["agent_names"] = agent_names
    return context


def _trusted_agent_name(context: dict[str, Any], known_agent_names: set[str]) -> str | None:
    agent_name = _safe_text(context.get("agent_name"))
    if not agent_name:
        return None
    if known_agent_names and agent_name not in known_agent_names:
        return None
    return agent_name


def _trusted_message_agent_name(value: Any, known_agent_names: set[str]) -> str | None:
    candidate = _safe_text(value)
    if not candidate or not known_agent_names:
        return None
    return candidate if candidate in known_agent_names else None


def _safe_message_type(value: Any) -> str:
    candidate = _safe_text(value)
    if candidate in _MESSAGE_TYPES:
        return candidate
    return "message"


def _set_trusted_message_context(props: dict[str, Any]) -> contextvars.Token[dict[str, Any] | None]:
    current = dict(_trusted_message_context.get() or {})
    merged = {**current, **props}
    if "agent_names" in current and "agent_names" not in props:
        merged["agent_names"] = current["agent_names"]
    return _trusted_message_context.set(merged)


def _reset_trusted_message_context(token: contextvars.Token[dict[str, Any] | None]) -> None:
    try:
        _trusted_message_context.reset(token)
    except Exception:
        logger.debug("Could not reset telemetry message context", exc_info=True)


def _swarm_props(agency: Any, args: tuple[Any, ...], kwargs: dict[str, Any], *, is_streaming: bool, status: str) -> dict[str, Any]:
    agent_name = _resolve_recipient_agent_name(agency, args, kwargs)
    props: dict[str, Any] = {
        "status": status,
        "is_streaming": is_streaming,
        "run_trace_id": uuid.uuid4().hex,
    }
    if agent_name:
        props["agent_name"] = agent_name
        props["agent_id"] = telemetry.agent_id(agent_name)
    return props


def _resolve_recipient_agent_name(agency: Any, args: tuple[Any, ...], kwargs: dict[str, Any]) -> str | None:
    recipient = kwargs.get("recipient_agent")
    if recipient is None and len(args) >= 2:
        recipient = args[1]
    if recipient is None:
        entry_points = getattr(agency, "entry_points", None) or []
        recipient = entry_points[0] if entry_points else None
    return _agent_name(recipient)


def _agent_props(context: Any, agent: Any, **extra: Any) -> dict[str, Any]:
    name = _agent_name(agent)
    props: dict[str, Any] = {
        "agent_name": name,
        "agent_id": telemetry.agent_id(name),
    }
    model = _model_name(agent)
    if model:
        props["model"] = model
        props["provider"] = telemetry.provider_from_model(model)
    run_context = getattr(context, "context", None)
    for source_key, target_key in (
        ("_current_agent_run_id", "agent_run_id"),
        ("_parent_run_id", "parent_run_id"),
        ("_run_trace_id", "run_trace_id"),
    ):
        value = _safe_text(getattr(run_context, source_key, None))
        if value:
            props[target_key] = value
    props.update({key: value for key, value in extra.items() if value is not None})
    return props


def _capture_tool_invoked(
    context: Any,
    agent: Any,
    tool_name: str,
    *,
    status: str,
    started_at: float | None,
) -> dict[str, Any]:
    props = _agent_props(context, agent, status=status, latency_ms=_elapsed_ms(started_at))
    props["tool_name"] = tool_name
    _safe_capture("tool_invoked", props)
    return props


def _capture_tool_failure(
    context: Any,
    agent: Any,
    tool_name: str,
    *,
    started_at: float | None,
    error: BaseException,
) -> None:
    props = _capture_tool_invoked(context, agent, tool_name, status="error", started_at=started_at)
    _safe_capture_error(error, category="tool", properties=props)


def _remember_tool_failure_logged(context: Any, agent: Any, tool_name: str) -> None:
    now = time.monotonic()
    stale_before = now - 300
    for key, logged_at in list(_logged_tool_failure_keys.items()):
        if logged_at < stale_before:
            _logged_tool_failure_keys.pop(key, None)
    _logged_tool_failure_keys[_context_tool_key(context, agent, tool_name)] = now


def _is_tool_error_result(result: Any) -> bool:
    if isinstance(result, str):
        return _is_tool_error_text(result)
    if isinstance(result, dict):
        status = _safe_text(result.get("status"))
        if status and status.strip().lower() in {"error", "failed", "failure"}:
            return True
        error_value = result.get("error")
        if isinstance(error_value, bool):
            return error_value
        return error_value is not None
    if isinstance(result, list | tuple):
        return any(_is_tool_error_result(item) for item in result)
    text = getattr(result, "text", None)
    if isinstance(text, str):
        return _is_tool_error_text(text)
    return False


def _is_tool_error_text(text: str) -> bool:
    normalized = text.strip().lower()
    return any(normalized.startswith(prefix) for prefix in _TOOL_ERROR_PREFIXES)


def _safe_capture(event: str, properties: dict[str, Any] | None = None) -> bool:
    try:
        return telemetry.capture(event, properties)
    except Exception:
        logger.debug("Telemetry capture failed for event %s", event, exc_info=True)
        return False


def _safe_capture_error(error: BaseException, *, category: str, properties: dict[str, Any] | None = None) -> bool:
    try:
        return telemetry.capture_error(error, category=category, properties=properties)
    except Exception:
        logger.debug("Telemetry error capture failed for category %s", category, exc_info=True)
        return False


def _model_name(agent: Any) -> str | None:
    try:
        from agency_swarm.agent.execution import get_model_name

        return get_model_name(getattr(agent, "model", None))
    except Exception:
        model = getattr(agent, "model", None)
        return str(model) if model is not None else None


def _usage_props_from_run_result(run_result: Any) -> dict[str, Any]:
    if run_result is None:
        return {}
    try:
        from agency_swarm.utils.usage_tracking import calculate_usage_with_cost, extract_usage_from_run_result

        usage = extract_usage_from_run_result(run_result)
        if usage is None:
            return {}
        usage = calculate_usage_with_cost(usage, run_result=run_result)
        return _usage_props(usage.input_tokens, usage.output_tokens, usage.total_cost)
    except Exception:
        logger.debug("Could not extract run usage for telemetry", exc_info=True)
        return {}


def _usage_props_from_response(response: Any) -> dict[str, Any]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return {}
    return _usage_props(
        getattr(usage, "input_tokens", None),
        getattr(usage, "output_tokens", None),
        None,
    )


def _usage_props(tokens_input: Any, tokens_output: Any, cost: Any) -> dict[str, Any]:
    props: dict[str, Any] = {}
    if isinstance(tokens_input, int):
        props["tokens_input"] = tokens_input
    if isinstance(tokens_output, int):
        props["tokens_output"] = tokens_output
    if isinstance(cost, int | float):
        props["cost_usd"] = float(cost)
    return props


def _stop_reason(response: Any) -> str | None:
    raw_items = getattr(response, "output", None) or getattr(response, "items", None) or []
    if not isinstance(raw_items, list):
        return None
    for item in raw_items:
        status = _safe_text(getattr(item, "status", None))
        if status:
            return status
        if isinstance(item, dict):
            status = _safe_text(item.get("status"))
            if status:
                return status
    return None


def _tool_name(tool: Any) -> str:
    return _safe_text(getattr(tool, "name", None) or getattr(tool, "__name__", None) or tool.__class__.__name__) or "unknown"


def _agent_name(agent: Any) -> str | None:
    if agent is None:
        return None
    if isinstance(agent, str):
        return agent
    return _safe_text(getattr(agent, "name", None))


def _context_agent_key(context: Any, agent: Any) -> tuple[int, str]:
    return (id(context), _agent_name(agent) or "unknown")


def _context_tool_key(context: Any, agent: Any, tool_name: str) -> tuple[int, str, str]:
    return (id(context), _agent_name(agent) or "unknown", tool_name)


def _elapsed_ms(started_at: float | None) -> int | None:
    if started_at is None:
        return None
    return max(0, int((time.monotonic() - started_at) * 1000))


def _safe_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value[:256]
    return str(value)[:256]
