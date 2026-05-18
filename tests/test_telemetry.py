from __future__ import annotations

import hashlib
import asyncio
import os
from types import SimpleNamespace

import pytest

import telemetry
import telemetry_hooks
from agents.lifecycle import AgentHooksBase, RunHooksBase


class FakePostHog:
    def __init__(self, api_key: str, host: str, events: list[dict]) -> None:
        self.api_key = api_key
        self.host = host
        self.events = events

    def capture(self, *, event: str, distinct_id: str, properties: dict) -> None:
        self.events.append(
            {
                "event": event,
                "distinct_id": distinct_id,
                "properties": properties,
                "api_key": self.api_key,
                "host": self.host,
            }
        )


@pytest.fixture
def telemetry_events(monkeypatch: pytest.MonkeyPatch, tmp_path):
    for key in (
        "POSTHOG_API_KEY",
        "POSTHOG_HOST",
        "OPENSWARM_TELEMETRY",
        "DO_NOT_TRACK",
        "CI",
        "PYTEST_VERSION",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("OPENSWARM_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("OPENSWARM_TELEMETRY_ALLOW_TESTS", "1")
    monkeypatch.setattr(telemetry, "_MODULE_DIR", tmp_path)
    telemetry._reset_for_tests()
    telemetry_hooks._trusted_thread_managers.clear()
    telemetry_hooks._logged_tool_failure_keys.clear()
    telemetry_hooks._trusted_message_context.set(None)
    events: list[dict] = []
    telemetry.set_posthog_factory_for_tests(lambda api_key, host: FakePostHog(api_key, host, events))
    yield events
    telemetry._reset_for_tests()
    telemetry_hooks._trusted_thread_managers.clear()
    telemetry_hooks._logged_tool_failure_keys.clear()
    telemetry_hooks._trusted_message_context.set(None)


def test_env_key_enables_telemetry(monkeypatch: pytest.MonkeyPatch, telemetry_events: list[dict]) -> None:
    monkeypatch.setenv("POSTHOG_API_KEY", "ph_env")

    assert telemetry.capture("app_started", {"install_source": "env"})

    assert telemetry_events[0]["event"] == "app_started"
    assert telemetry_events[0]["api_key"] == "ph_env"
    assert telemetry_events[0]["host"] == telemetry.DEFAULT_POSTHOG_HOST


def test_generated_npm_config_enables_when_env_absent(tmp_path, telemetry_events: list[dict]) -> None:
    (tmp_path / "openswarm_telemetry_config.py").write_text(
        "POSTHOG_API_KEY = 'ph_generated'\nPOSTHOG_HOST = 'https://eu.i.posthog.com'\n",
        encoding="utf-8",
    )

    assert telemetry.capture("app_started", {"install_source": "npm_config"})

    assert telemetry_events[0]["api_key"] == "ph_generated"
    assert telemetry_events[0]["host"] == "https://eu.i.posthog.com"


def test_env_key_overrides_generated_config(monkeypatch: pytest.MonkeyPatch, tmp_path, telemetry_events: list[dict]) -> None:
    (tmp_path / "openswarm_telemetry_config.py").write_text(
        "POSTHOG_API_KEY = 'ph_generated'\nPOSTHOG_HOST = 'https://generated.example'\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("POSTHOG_API_KEY", "ph_env")
    monkeypatch.setenv("POSTHOG_HOST", "https://env.example")

    assert telemetry.capture("app_started")

    assert telemetry_events[0]["api_key"] == "ph_env"
    assert telemetry_events[0]["host"] == "https://env.example"


def test_source_install_without_key_is_noop(telemetry_events: list[dict]) -> None:
    assert not telemetry.capture("app_started")
    assert telemetry_events == []


def test_unknown_event_is_rejected_before_client_or_state_creation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    telemetry_events: list[dict],
) -> None:
    config_dir = tmp_path / "unknown-event-config"
    monkeypatch.setenv("OPENSWARM_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("POSTHOG_API_KEY", "ph_env")
    telemetry._reset_for_tests()
    telemetry.set_posthog_factory_for_tests(lambda api_key, host: FakePostHog(api_key, host, telemetry_events))

    assert not telemetry.capture("user_supplied_event_name", {"agent_name": "Docs Agent"})
    assert telemetry_events == []
    assert not (config_dir / "telemetry.json").exists()


@pytest.mark.parametrize(
    ("env_key", "env_value"),
    [
        ("OPENSWARM_TELEMETRY", "false"),
        ("OPENSWARM_TELEMETRY", "0"),
        ("OPENSWARM_TELEMETRY", "no"),
        ("OPENSWARM_TELEMETRY", "off"),
        ("DO_NOT_TRACK", "1"),
        ("CI", "1"),
    ],
)
def test_opt_out_and_ci_suppress_captures(
    monkeypatch: pytest.MonkeyPatch,
    telemetry_events: list[dict],
    env_key: str,
    env_value: str,
) -> None:
    monkeypatch.setenv("POSTHOG_API_KEY", "ph_env")
    if env_key == "CI":
        monkeypatch.delenv("OPENSWARM_TELEMETRY_ALLOW_TESTS", raising=False)
    monkeypatch.setenv(env_key, env_value)
    telemetry._reset_for_tests()
    telemetry.set_posthog_factory_for_tests(lambda api_key, host: FakePostHog(api_key, host, telemetry_events))

    assert not telemetry.capture("app_started")
    assert telemetry_events == []


def test_pytest_mode_suppresses_without_explicit_allow(monkeypatch: pytest.MonkeyPatch, telemetry_events: list[dict]) -> None:
    monkeypatch.setenv("POSTHOG_API_KEY", "ph_env")
    monkeypatch.delenv("OPENSWARM_TELEMETRY_ALLOW_TESTS", raising=False)
    telemetry._reset_for_tests()
    telemetry.set_posthog_factory_for_tests(lambda api_key, host: FakePostHog(api_key, host, telemetry_events))

    assert not telemetry.capture("app_started")
    assert telemetry_events == []


def test_agent_name_is_raw_on_relevant_events(telemetry_events: list[dict], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POSTHOG_API_KEY", "ph_env")
    relevant_events = [
        "message_sent",
        "agent_run_started",
        "agent_run_completed",
        "llm_generation_completed",
        "tool_invoked",
        "handoff",
        "error",
    ]

    for event in relevant_events:
        telemetry.capture(event, {"agent_name": "Docs Agent", "agent_id": telemetry.agent_id("Docs Agent")})

    assert [entry["event"] for entry in telemetry_events] == relevant_events
    for entry in telemetry_events:
        props = entry["properties"]
        assert props["agent_name"] == "Docs Agent"
        assert props["agent_id"] != "Docs Agent"


def test_safe_model_and_provider_are_sent(monkeypatch: pytest.MonkeyPatch, telemetry_events: list[dict]) -> None:
    monkeypatch.setenv("POSTHOG_API_KEY", "ph_env")
    model = "litellm/anthropic/claude-sonnet-4-6"

    telemetry.capture(
        "agent_run_started",
        {
            "agent_name": "Research",
            "model": model,
            "provider": telemetry.provider_from_model(model),
        },
    )

    props = telemetry_events[0]["properties"]
    assert props["model"] == model
    assert props["provider"] == "anthropic"


def test_unsafe_model_values_are_dropped(monkeypatch: pytest.MonkeyPatch, telemetry_events: list[dict]) -> None:
    monkeypatch.setenv("POSTHOG_API_KEY", "ph_env")
    cases = [
        ("/Users/mike/private-model", None),
        ("model user@example.com", None),
        ("C:\\Users\\mike\\private-model", None),
        ("https://example.com/private-model", None),
        ("litellm/openai/sk-secret1234567890", "openai"),
        ("gpt-5.2 api_key=secret", None),
    ]

    for model, expected_provider in cases:
        telemetry.capture(
            "agent_run_started",
            {
                "agent_name": "Research",
                "model": model,
                "provider": telemetry.provider_from_model(model),
            },
        )
        props = telemetry_events[-1]["properties"]
        assert "model" not in props
        if expected_provider:
            assert props["provider"] == expected_provider
        else:
            assert "provider" not in props
        assert "@" not in str(props)
        assert "/Users" not in str(props)
        assert "sk-secret" not in str(props)
        assert "api_key" not in str(props)


def test_configured_provider_ignores_unsafe_default_model(
    monkeypatch: pytest.MonkeyPatch,
    telemetry_events: list[dict],
) -> None:
    monkeypatch.setenv("DEFAULT_MODEL", "gpt-5.2 api_key=secret")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    assert telemetry.configured_provider() is None


def test_numeric_and_boolean_properties_are_type_gated(
    monkeypatch: pytest.MonkeyPatch,
    telemetry_events: list[dict],
) -> None:
    monkeypatch.setenv("POSTHOG_API_KEY", "ph_env")

    telemetry.capture(
        "error",
        {
            "error_type": "ValueError",
            "error_category": "test",
            "http_status": "429",
            "latency_ms": "/Users/mike/private",
            "tokens_input": "10",
            "tokens_output": "20",
            "cost_usd": "1.25",
            "is_streaming": "true",
            "has_provider_key": "true",
        },
    )
    unsafe_props = telemetry_events[0]["properties"]
    for key in (
        "http_status",
        "latency_ms",
        "tokens_input",
        "tokens_output",
        "cost_usd",
        "is_streaming",
        "has_provider_key",
    ):
        assert key not in unsafe_props

    telemetry.capture(
        "error",
        {
            "error_type": "ValueError",
            "error_category": "test",
            "http_status": 429,
            "latency_ms": 12,
            "tokens_input": 10,
            "tokens_output": 20,
            "cost_usd": 1.25,
            "is_streaming": False,
            "has_provider_key": True,
        },
    )
    safe_props = telemetry_events[1]["properties"]
    assert safe_props["http_status"] == 429
    assert safe_props["latency_ms"] == 12
    assert safe_props["tokens_input"] == 10
    assert safe_props["tokens_output"] == 20
    assert safe_props["cost_usd"] == 1.25
    assert safe_props["is_streaming"] is False
    assert safe_props["has_provider_key"] is True


def test_workspace_id_is_hmac_not_plain_path_hash(telemetry_events: list[dict], tmp_path) -> None:
    workspace = tmp_path / "secret-project"
    workspace.mkdir()
    derived = telemetry.workspace_id(workspace)
    plain_hash = hashlib.sha256(str(workspace.resolve()).encode("utf-8")).hexdigest()

    assert derived != str(workspace.resolve())
    assert derived != plain_hash
    assert derived == telemetry.workspace_id(workspace)


def test_error_event_excludes_messages_traces_and_paths(monkeypatch: pytest.MonkeyPatch, telemetry_events: list[dict]) -> None:
    monkeypatch.setenv("POSTHOG_API_KEY", "ph_env")
    error = ValueError("secret prompt in /Users/person/project")

    telemetry.capture_error(
        error,
        category="swarm_run",
        properties={
            "agent_name": "Orchestrator",
            "message": "secret",
            "traceback": "stack",
            "file_path": "/Users/person/project/file.py",
            "http_status": 429,
        },
    )

    props = telemetry_events[0]["properties"]
    assert props["error_type"] == "ValueError"
    assert props["error_category"] == "swarm_run"
    assert props["http_status"] == 429
    assert "secret prompt" not in str(props)
    assert "traceback" not in props
    assert "file_path" not in props
    assert "message" not in props


def test_agent_hook_composition_preserves_existing_hook(monkeypatch: pytest.MonkeyPatch, telemetry_events: list[dict]) -> None:
    monkeypatch.setenv("POSTHOG_API_KEY", "ph_env")
    calls: list[str] = []

    class ExistingHooks(AgentHooksBase):
        async def on_start(self, context, agent):
            calls.append("existing")

    async def run_hook() -> None:
        hooks = telemetry_hooks.compose_agent_hooks(ExistingHooks())
        await hooks.on_start(SimpleNamespace(context=SimpleNamespace()), SimpleNamespace(name="Research", model="gpt-5.2"))

    asyncio.run(run_hook())

    assert calls == ["existing"]
    assert telemetry_events[0]["event"] == "agent_run_started"
    assert telemetry_events[0]["properties"]["agent_name"] == "Research"


def test_run_hook_composition_preserves_existing_hook() -> None:
    calls: list[str] = []

    class ExistingRunHooks(RunHooksBase):
        async def on_agent_start(self, context, agent):
            calls.append("existing")

    async def run_hook() -> None:
        hooks = telemetry_hooks.compose_run_hooks(ExistingRunHooks())
        await hooks.on_agent_start(None, SimpleNamespace(name="Research"))

    asyncio.run(run_hook())

    assert calls == ["existing"]


def test_positional_hooks_override_is_composed() -> None:
    class ExistingRunHooks(RunHooksBase):
        pass

    hook = ExistingRunHooks()
    args = ("message", None, None, hook)
    kwargs = {}

    composed_args = telemetry_hooks._compose_hooks_override(args, kwargs)

    assert composed_args[:3] == args[:3]
    assert isinstance(composed_args[3], telemetry_hooks.CompositeRunHooks)


class TwoItemStream:
    def __init__(self) -> None:
        self.items = iter(["first", "second"])
        self.final_result = SimpleNamespace()

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self.items)
        except StopIteration:
            raise StopAsyncIteration

    async def aclose(self):
        return None

    async def wait_final_result(self):
        return self.final_result


def test_streaming_completion_fires_on_consumption(monkeypatch: pytest.MonkeyPatch, telemetry_events: list[dict]) -> None:
    monkeypatch.setenv("POSTHOG_API_KEY", "ph_env")
    stream = telemetry_hooks.TelemetryStreamingRunResponse(
        TwoItemStream(),
        {"agent_name": "Orchestrator", "is_streaming": True},
        telemetry_hooks.time.monotonic(),
    )

    async def consume_stream() -> list[str]:
        consumed = []
        async for item in stream:
            consumed.append(item)
            assert telemetry_events == []
        return consumed

    consumed = asyncio.run(consume_stream())

    assert consumed == ["first", "second"]
    assert telemetry_events[0]["event"] == "swarm_run_completed"
    assert telemetry_events[0]["properties"]["agent_name"] == "Orchestrator"


class ErrorStream:
    final_result = None

    def __aiter__(self):
        return self

    async def __anext__(self):
        raise RuntimeError("private path /Users/person/project")

    async def aclose(self):
        return None


def test_streaming_error_fires_on_consumption(monkeypatch: pytest.MonkeyPatch, telemetry_events: list[dict]) -> None:
    monkeypatch.setenv("POSTHOG_API_KEY", "ph_env")
    stream = telemetry_hooks.TelemetryStreamingRunResponse(
        ErrorStream(),
        {"agent_name": "Orchestrator", "is_streaming": True},
        telemetry_hooks.time.monotonic(),
    )

    async def consume_stream() -> None:
        await stream.__anext__()

    with pytest.raises(RuntimeError):
        asyncio.run(consume_stream())

    assert telemetry_events[0]["event"] == "error"
    props = telemetry_events[0]["properties"]
    assert props["error_type"] == "RuntimeError"
    assert "private path" not in str(props)


def test_message_sent_extracts_only_safe_fields(monkeypatch: pytest.MonkeyPatch, telemetry_events: list[dict]) -> None:
    monkeypatch.setenv("POSTHOG_API_KEY", "ph_env")
    token = telemetry_hooks._trusted_message_context.set(
        {
            "agent_name": "Docs Agent",
            "agent_run_id": "trusted_run",
            "run_trace_id": "trusted_trace",
            "agent_names": {"Docs Agent", "Orchestrator"},
        }
    )
    message = {
        "role": "assistant",
        "type": "message",
        "content": [{"type": "output_text", "text": "do not send"}],
        "agent": "user controlled secret",
        "callerAgent": "Orchestrator",
        "agent_run_id": "/Users/private/run",
        "run_trace_id": "secret_trace",
    }

    try:
        telemetry_hooks._capture_message_sent(message, manager=object())
    finally:
        telemetry_hooks._trusted_message_context.reset(token)

    props = telemetry_events[0]["properties"]
    assert props["agent_name"] == "Docs Agent"
    assert props["caller_agent_name"] == "Orchestrator"
    assert props["agent_run_id"] == "trusted_run"
    assert props["run_trace_id"] == "trusted_trace"
    assert props["message_role"] == "assistant"
    assert "content" not in props
    assert "do not send" not in str(props)
    assert "user controlled secret" not in str(props)
    assert "/Users/private" not in str(props)


def test_message_sent_without_trusted_agent_context_drops_message_agent(
    monkeypatch: pytest.MonkeyPatch,
    telemetry_events: list[dict],
) -> None:
    monkeypatch.setenv("POSTHOG_API_KEY", "ph_env")

    telemetry_hooks._capture_message_sent(
        {
            "role": "assistant",
            "type": "arbitrary-private-type",
            "agent": "private user text",
            "callerAgent": "private caller text",
            "agent_run_id": "private run",
        },
        manager=object(),
    )

    props = telemetry_events[0]["properties"]
    assert props["message_type"] == "message"
    assert "agent_name" not in props
    assert "caller_agent_name" not in props
    assert "agent_run_id" not in props
    assert "private" not in str(props)


def test_thread_manager_wrapper_ignores_message_telemetry_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    telemetry_hooks.install_thread_manager_telemetry()
    from agency_swarm.utils.thread import ThreadManager

    def fail_capture(*args, **kwargs):
        raise RuntimeError("telemetry failure")

    monkeypatch.setattr(telemetry_hooks, "_capture_message_sent", fail_capture)
    manager = ThreadManager()

    manager.add_message({"role": "user", "type": "message", "content": "product path still works"})


def test_streaming_completion_ignores_telemetry_capture_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_capture(*args, **kwargs):
        raise RuntimeError("telemetry failure")

    monkeypatch.setattr(telemetry_hooks.telemetry, "capture", fail_capture)
    stream = telemetry_hooks.TelemetryStreamingRunResponse(
        TwoItemStream(),
        {"agent_name": "Orchestrator", "is_streaming": True},
        telemetry_hooks.time.monotonic(),
    )

    async def consume_stream() -> list[str]:
        consumed = []
        async for item in stream:
            consumed.append(item)
        return consumed

    assert asyncio.run(consume_stream()) == ["first", "second"]


def test_agency_run_wrapper_ignores_telemetry_capture_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeAgency:
        entry_points = [SimpleNamespace(name="Orchestrator")]

        async def get_response(self, *args, **kwargs):
            return SimpleNamespace()

        def get_response_stream(self, *args, **kwargs):
            return TwoItemStream()

    def fail_capture(*args, **kwargs):
        raise RuntimeError("telemetry failure")

    agency = FakeAgency()
    monkeypatch.setattr(telemetry_hooks.telemetry, "capture", fail_capture)
    telemetry_hooks._wrap_agency_methods(agency)

    result = asyncio.run(agency.get_response("hello"))

    assert isinstance(result, SimpleNamespace)


def test_tool_invoked_payload_drops_content_like_properties(monkeypatch: pytest.MonkeyPatch, telemetry_events: list[dict]) -> None:
    monkeypatch.setenv("POSTHOG_API_KEY", "ph_env")

    telemetry.capture(
        "tool_invoked",
        {
            "agent_name": "Slides Agent",
            "tool_name": "create_slide",
            "tool_args": {"prompt": "secret"},
            "tool_result": "secret output",
            "latency_ms": 5,
        },
    )

    props = telemetry_events[0]["properties"]
    assert props["agent_name"] == "Slides Agent"
    assert props["tool_name"] == "create_slide"
    assert "tool_args" not in props
    assert "tool_result" not in props
    assert "secret" not in str(props)


def test_tool_returned_error_emits_tool_failure_events(
    monkeypatch: pytest.MonkeyPatch,
    telemetry_events: list[dict],
) -> None:
    monkeypatch.setenv("POSTHOG_API_KEY", "ph_env")
    hooks = telemetry_hooks.OpenSwarmTelemetryAgentHooks()
    context = SimpleNamespace(context=SimpleNamespace())
    agent = SimpleNamespace(name="Slides Agent", model="gpt-5.2")
    tool = SimpleNamespace(name="InsertNewSlides")

    async def run_hooks() -> None:
        await hooks.on_tool_start(context, agent, tool)
        await hooks.on_tool_end(context, agent, tool, "❌ private error output /Users/person/project")

    asyncio.run(run_hooks())

    assert [entry["event"] for entry in telemetry_events] == ["tool_invoked", "error"]
    tool_props = telemetry_events[0]["properties"]
    error_props = telemetry_events[1]["properties"]
    assert tool_props["status"] == "error"
    assert tool_props["tool_name"] == "InsertNewSlides"
    assert error_props["error_category"] == "tool"
    assert error_props["error_type"] == "ToolReturnedError"
    assert error_props["tool_name"] == "InsertNewSlides"
    assert "private error output" not in str(telemetry_events)
    assert "/Users/person/project" not in str(telemetry_events)


def test_tool_returned_error_detects_error_without_colon(
    monkeypatch: pytest.MonkeyPatch,
    telemetry_events: list[dict],
) -> None:
    monkeypatch.setenv("POSTHOG_API_KEY", "ph_env")
    hooks = telemetry_hooks.OpenSwarmTelemetryAgentHooks()
    context = SimpleNamespace(context=SimpleNamespace())
    agent = SimpleNamespace(name="Virtual Assistant", model="gpt-5.2")
    tool = SimpleNamespace(name="FindEmails")

    async def run_hooks() -> None:
        await hooks.on_tool_start(context, agent, tool)
        await hooks.on_tool_end(context, agent, tool, "Error searching Gmail: private")

    asyncio.run(run_hooks())

    assert [entry["event"] for entry in telemetry_events] == ["tool_invoked", "error"]
    assert telemetry_events[0]["properties"]["status"] == "error"
    assert telemetry_events[1]["properties"]["error_type"] == "ToolReturnedError"
    assert "private" not in str(telemetry_events)


def test_tool_returned_error_detects_modify_slide_validation_failure(
    monkeypatch: pytest.MonkeyPatch,
    telemetry_events: list[dict],
) -> None:
    monkeypatch.setenv("POSTHOG_API_KEY", "ph_env")
    hooks = telemetry_hooks.OpenSwarmTelemetryAgentHooks()
    context = SimpleNamespace(context=SimpleNamespace())
    agent = SimpleNamespace(name="Slides Agent", model="gpt-5.2")
    tool = SimpleNamespace(name="ModifySlide")

    async def run_hooks() -> None:
        await hooks.on_tool_start(context, agent, tool)
        await hooks.on_tool_end(context, agent, tool, "HTML validation failed after 3 attempts:\nprivate details")

    asyncio.run(run_hooks())

    assert [entry["event"] for entry in telemetry_events] == ["tool_invoked", "error"]
    assert telemetry_events[0]["properties"]["status"] == "error"
    assert telemetry_events[1]["properties"]["error_type"] == "ToolReturnedError"
    assert "private details" not in str(telemetry_events)


def test_tool_success_still_emits_completed_invocation(
    monkeypatch: pytest.MonkeyPatch,
    telemetry_events: list[dict],
) -> None:
    monkeypatch.setenv("POSTHOG_API_KEY", "ph_env")
    hooks = telemetry_hooks.OpenSwarmTelemetryAgentHooks()
    context = SimpleNamespace(context=SimpleNamespace())
    agent = SimpleNamespace(name="Slides Agent", model="gpt-5.2")
    tool = SimpleNamespace(name="InsertNewSlides")

    async def run_hooks() -> None:
        await hooks.on_tool_start(context, agent, tool)
        await hooks.on_tool_end(context, agent, tool, "Created slide")

    asyncio.run(run_hooks())

    assert [entry["event"] for entry in telemetry_events] == ["tool_invoked"]
    props = telemetry_events[0]["properties"]
    assert props["status"] == "completed"
    assert props["tool_name"] == "InsertNewSlides"


def test_tool_invoke_exception_emits_tool_failure_and_reraises(
    monkeypatch: pytest.MonkeyPatch,
    telemetry_events: list[dict],
) -> None:
    monkeypatch.setenv("POSTHOG_API_KEY", "ph_env")

    async def invoke_tool(context, args_json):
        raise RuntimeError("secret prompt in /Users/person/project")

    tool = SimpleNamespace(name="InsertNewSlides", on_invoke_tool=invoke_tool)
    agent = SimpleNamespace(name="Slides Agent", model="gpt-5.2", tools=[tool])
    context = SimpleNamespace(context=SimpleNamespace())

    telemetry_hooks._wrap_agent_tools([agent])

    with pytest.raises(RuntimeError):
        asyncio.run(tool.on_invoke_tool(context, '{"task_brief":"secret"}'))

    assert [entry["event"] for entry in telemetry_events] == ["tool_invoked", "error"]
    tool_props = telemetry_events[0]["properties"]
    error_props = telemetry_events[1]["properties"]
    assert tool_props["status"] == "error"
    assert tool_props["tool_name"] == "InsertNewSlides"
    assert error_props["error_category"] == "tool"
    assert error_props["error_type"] == "RuntimeError"
    assert "secret prompt" not in str(telemetry_events)
    assert "task_brief" not in str(telemetry_events)
    assert "/Users/person/project" not in str(telemetry_events)


def test_tool_invoke_sdk_error_result_emits_tool_failure(
    monkeypatch: pytest.MonkeyPatch,
    telemetry_events: list[dict],
) -> None:
    monkeypatch.setenv("POSTHOG_API_KEY", "ph_env")

    async def invoke_tool(context, args_json):
        return "An error occurred while running the tool. Please try again. Error: private"

    tool = SimpleNamespace(name="TelemetryRaiseError", on_invoke_tool=invoke_tool)
    agent = SimpleNamespace(name="General Agent", model="gpt-5.2", tools=[tool])
    context = SimpleNamespace(context=SimpleNamespace())

    telemetry_hooks._wrap_agent_tools([agent])

    result = asyncio.run(tool.on_invoke_tool(context, '{"label":"private"}'))

    assert result.startswith("An error occurred")
    assert [entry["event"] for entry in telemetry_events] == ["tool_invoked", "error"]
    assert telemetry_events[0]["properties"]["status"] == "error"
    assert telemetry_events[0]["properties"]["tool_name"] == "TelemetryRaiseError"
    assert telemetry_events[1]["properties"]["error_type"] == "ToolReturnedError"
    assert "private" not in str(telemetry_events)


def test_tool_invocation_wrapper_is_idempotent(
    monkeypatch: pytest.MonkeyPatch,
    telemetry_events: list[dict],
) -> None:
    monkeypatch.setenv("POSTHOG_API_KEY", "ph_env")
    calls = 0

    async def invoke_tool(context, args_json):
        nonlocal calls
        calls += 1
        raise ValueError("private")

    tool = SimpleNamespace(name="InsertNewSlides", on_invoke_tool=invoke_tool)
    agent = SimpleNamespace(name="Slides Agent", model="gpt-5.2", tools=[tool])

    telemetry_hooks._wrap_agent_tools([agent])
    telemetry_hooks._wrap_agent_tools([agent])

    with pytest.raises(ValueError):
        asyncio.run(tool.on_invoke_tool(SimpleNamespace(context=SimpleNamespace()), "{}"))

    assert calls == 1
    assert [entry["event"] for entry in telemetry_events] == ["tool_invoked", "error"]


def test_tool_failure_wrapper_suppresses_duplicate_on_tool_end_error(
    monkeypatch: pytest.MonkeyPatch,
    telemetry_events: list[dict],
) -> None:
    monkeypatch.setenv("POSTHOG_API_KEY", "ph_env")

    async def invoke_tool(context, args_json):
        raise RuntimeError("private")

    tool = SimpleNamespace(name="InsertNewSlides", on_invoke_tool=invoke_tool)
    agent = SimpleNamespace(name="Slides Agent", model="gpt-5.2", tools=[tool])
    context = SimpleNamespace(context=SimpleNamespace())
    hooks = telemetry_hooks.OpenSwarmTelemetryAgentHooks()

    telemetry_hooks._wrap_agent_tools([agent])

    async def run_tool_and_hook() -> None:
        await hooks.on_tool_start(context, agent, tool)
        with pytest.raises(RuntimeError):
            await tool.on_invoke_tool(context, "{}")
        await hooks.on_tool_end(context, agent, tool, "Error: private")

    asyncio.run(run_tool_and_hook())

    assert [entry["event"] for entry in telemetry_events] == ["tool_invoked", "error"]


def test_tool_returned_error_wrapper_suppresses_duplicate_on_tool_end_error(
    monkeypatch: pytest.MonkeyPatch,
    telemetry_events: list[dict],
) -> None:
    monkeypatch.setenv("POSTHOG_API_KEY", "ph_env")

    async def invoke_tool(context, args_json):
        return "An error occurred while running the tool. Please try again. Error: private"

    tool = SimpleNamespace(name="TelemetryRaiseError", on_invoke_tool=invoke_tool)
    agent = SimpleNamespace(name="General Agent", model="gpt-5.2", tools=[tool])
    context = SimpleNamespace(context=SimpleNamespace())
    hooks = telemetry_hooks.OpenSwarmTelemetryAgentHooks()

    telemetry_hooks._wrap_agent_tools([agent])

    async def run_tool_and_hook() -> None:
        await hooks.on_tool_start(context, agent, tool)
        result = await tool.on_invoke_tool(context, "{}")
        await hooks.on_tool_end(context, agent, tool, result)

    asyncio.run(run_tool_and_hook())

    assert [entry["event"] for entry in telemetry_events] == ["tool_invoked", "error"]
