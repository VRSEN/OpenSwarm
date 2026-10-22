from __future__ import annotations

import asyncio
import importlib.util
import os
import sys
import types
import unittest
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OPENAI_URL = "https://api.openai.com/v1"
CODEX_URL = "https://chatgpt.com/backend-api/codex"
COMPATIBLE_URL = "https://codex.example.test/v1"
OPENROUTER_URL = "https://openrouter.ai/api/v1"


class FakeAgent:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.model = kwargs.get("model")


@dataclass(init=False)
class FakeModelSettings:
    reasoning: object | None = None
    verbosity: object | None = None
    store: object | None = None
    truncation: object | None = None

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        for name in ("reasoning", "verbosity", "store", "truncation"):
            setattr(self, name, kwargs.get(name))


class FakeReasoning:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class FakeAsyncOpenAI:
    def __init__(
        self,
        *,
        api_key="env-key",
        base_url=OPENAI_URL,
        organization=None,
        project=None,
        timeout=None,
        max_retries=2,
        default_headers=None,
        default_query=None,
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.organization = organization
        self.project = project
        self.timeout = timeout
        self.max_retries = max_retries
        self._custom_headers = default_headers
        self._custom_query = default_query


class FakeResponsesModel:
    def __init__(self, *, model, openai_client):
        self.model = model
        self._client = openai_client

    async def _fetch_response(self, _system, _input, settings, *args, **kwargs):
        return settings


class FakeChatModel:
    def __init__(
        self,
        *,
        model,
        openai_client,
        should_replay_reasoning_content=None,
    ):
        self.model = model
        self._client = openai_client
        self.should_replay_reasoning_content = should_replay_reasoning_content


class FakeLitellmModel:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        for key, value in kwargs.items():
            setattr(self, key, value)


class FakeBaseModel:
    @classmethod
    def model_validate(cls, value):
        return cls(**value)

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def model_dump(self):
        return self.__dict__.copy()


def fake_field(default=None, **_kwargs):
    return default


def install_stubs() -> None:
    agency = types.ModuleType("agency_swarm")
    agency.Agent = FakeAgent
    agency.LitellmModel = FakeLitellmModel
    agency.ModelSettings = FakeModelSettings
    agency.Reasoning = FakeReasoning

    agency_tools = types.ModuleType("agency_swarm.tools")
    agency_tools.BaseTool = object
    agency_tools.ToolOutputText = str
    agency_tools.tool_output_image_from_path = lambda path: path

    agency_messages = types.ModuleType("agency_swarm.messages")
    codex_input = types.ModuleType("agency_swarm.messages.codex_input")
    codex_input.is_codex_base_url = lambda value: bool(
        value and value.rstrip("/") == CODEX_URL
    )

    agency_utils = types.ModuleType("agency_swarm.utils")
    openrouter = types.ModuleType("agency_swarm.utils.openrouter")
    openrouter.is_openrouter_model_name = lambda value: value.startswith("openrouter/")
    openrouter.get_openrouter_model_name = lambda model: getattr(
        model,
        "_agency_swarm_openrouter_model_name",
        None,
    )

    def build_openrouter_chat_model(
        model_name,
        *,
        openai_client,
        should_replay_reasoning_content=None,
    ):
        actual = (
            model_name[len("openrouter/") :]
            if model_name.startswith("openrouter/")
            else model_name
        )
        model = FakeChatModel(
            model=actual,
            openai_client=openai_client,
            should_replay_reasoning_content=should_replay_reasoning_content,
        )
        model._agency_swarm_openrouter_model_name = f"openrouter/{actual}"
        return model

    openrouter.build_openrouter_chat_model = build_openrouter_chat_model

    agents = types.ModuleType("agents")
    agents.OpenAIResponsesModel = FakeResponsesModel
    agents.OpenAIChatCompletionsModel = FakeChatModel

    agents_extensions = types.ModuleType("agents.extensions")
    agents_models = types.ModuleType("agents.extensions.models")
    agents_litellm = types.ModuleType("agents.extensions.models.litellm_model")
    agents_litellm.LitellmModel = FakeLitellmModel
    agents_shared = types.ModuleType("agents.models._openai_shared")
    agents_shared.get_default_openai_client = lambda: None

    openai = types.ModuleType("openai")
    openai.AsyncOpenAI = FakeAsyncOpenAI

    pydantic = types.ModuleType("pydantic")
    pydantic.BaseModel = FakeBaseModel
    pydantic.Field = fake_field
    pydantic.ValidationError = ValueError

    run_utils = types.ModuleType("run_utils")
    run_utils._load_openswarm_dotenv = lambda *, override=False: False

    sys.modules.update(
        {
            "agency_swarm": agency,
            "agency_swarm.tools": agency_tools,
            "agency_swarm.messages": agency_messages,
            "agency_swarm.messages.codex_input": codex_input,
            "agency_swarm.utils": agency_utils,
            "agency_swarm.utils.openrouter": openrouter,
            "agents": agents,
            "agents.extensions": agents_extensions,
            "agents.extensions.models": agents_models,
            "agents.extensions.models.litellm_model": agents_litellm,
            "agents.models._openai_shared": agents_shared,
            "openai": openai,
            "pydantic": pydantic,
            "run_utils": run_utils,
        }
    )


def install_package_stubs() -> None:
    slides_agent = types.ModuleType("slides_agent")
    slides_agent.__path__ = [str(ROOT / "slides_agent")]
    tools = types.ModuleType("slides_agent.tools")
    tools.__path__ = [str(ROOT / "slides_agent" / "tools")]

    files = types.ModuleType("slides_agent.tools.slide_file_utils")
    files.get_project_dir = lambda name: Path(name)
    files.apply_renames = lambda _renames: None
    files.build_slide_name = lambda prefix, index, pad, suffix="": (
        f"{prefix}_{index:0{pad}d}{suffix}"
    )
    files.compute_pad_width = lambda _slides, extra_count=0: 2
    files.list_slide_files = lambda *_args, **_kwargs: []

    html = types.ModuleType("slides_agent.tools.slide_html_utils")
    html.ensure_full_html = lambda value: (value or "<html></html>", False)
    html.list_slide_filenames = lambda _project_dir: []
    html.validate_html = lambda *_args, **_kwargs: {"valid": True}
    html._strip_html_to_text = lambda value: value

    templates = types.ModuleType("slides_agent.tools.template_registry")
    templates.load_template_index = lambda _project_dir: {}
    templates.save_template_index = lambda *_args, **_kwargs: None
    templates.template_path = lambda project_dir, key: Path(project_dir) / key

    sys.modules.update(
        {
            "slides_agent": slides_agent,
            "slides_agent.tools": tools,
            "slides_agent.tools.slide_file_utils": files,
            "slides_agent.tools.slide_html_utils": html,
            "slides_agent.tools.template_registry": templates,
        }
    )


def load_module(name: str, relative: str):
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def load_slides_tools():
    internal = load_module(
        "slides_agent.tools.internal_model",
        "slides_agent/tools/internal_model.py",
    )
    modify = load_module(
        "slides_agent.tools.ModifySlide",
        "slides_agent/tools/ModifySlide.py",
    )
    insert = load_module(
        "slides_agent.tools.InsertNewSlides",
        "slides_agent/tools/InsertNewSlides.py",
    )
    return internal, modify, insert


def tool_for(model, *, run_model=None):
    agent = types.SimpleNamespace(model=model)
    master = types.SimpleNamespace(
        current_agent_name="Slides Agent",
        agents={"Slides Agent": agent},
    )
    return types.SimpleNamespace(
        _context=types.SimpleNamespace(
            context=master,
            run_config=types.SimpleNamespace(model=run_model),
        )
    )


def nested_agents(modify, insert, tool):
    writer, writer_codex = modify._make_html_writer_agent(tool=tool)
    planner, planner_codex = insert._make_planner_agent(tool=tool)
    return (writer, planner), (writer_codex, planner_codex)


class SlidesInternalModelTests(unittest.TestCase):
    def setUp(self):
        install_stubs()
        install_package_stubs()
        os.environ.pop("DEFAULT_MODEL", None)
        for name in (
            "config",
            "slides_agent.tools.internal_model",
            "slides_agent.tools.ModifySlide",
            "slides_agent.tools.InsertNewSlides",
        ):
            sys.modules.pop(name, None)

    def test_direct_openai_preserves_selected_model_and_client_config(self):
        _internal, modify, insert = load_slides_tools()
        client = FakeAsyncOpenAI(
            api_key="request-key",
            base_url=OPENAI_URL,
            organization="request-org",
            project="request-project",
            timeout=42,
            max_retries=4,
            default_headers={"X-Request": "slides"},
            default_query={"source": "request"},
        )
        source = FakeResponsesModel(model="gpt-5.4-mini", openai_client=client)

        agents, codex = nested_agents(modify, insert, tool_for(source))

        self.assertEqual(codex, (False, False))
        for agent in agents:
            self.assertIsInstance(agent.model, FakeResponsesModel)
            self.assertEqual(agent.model.model, "gpt-5.4-mini")
            nested = agent.model._client
            self.assertIsNot(nested, client)
            self.assertEqual(nested.api_key, "request-key")
            self.assertEqual(nested.base_url, OPENAI_URL)
            self.assertEqual(nested.organization, "request-org")
            self.assertEqual(nested.project, "request-project")
            self.assertEqual(nested.timeout, 42)
            self.assertEqual(nested.max_retries, 4)
            self.assertEqual(nested._custom_headers, {"X-Request": "slides"})
            self.assertEqual(nested._custom_query, {"source": "request"})
            self.assertEqual(agent.kwargs["model_settings"].verbosity, "medium")

    def test_only_verified_codex_url_uses_responses_stream_route(self):
        internal, modify, insert = load_slides_tools()
        source = FakeChatModel(
            model="gpt-5.4-mini",
            openai_client=FakeAsyncOpenAI(
                api_key="codex-key",
                base_url=f"{CODEX_URL}/",
            ),
        )

        agents, codex = nested_agents(modify, insert, tool_for(source))

        self.assertEqual(codex, (True, True))
        for agent in agents:
            self.assertIsInstance(agent.model, internal._CodexResponsesModel)
            self.assertEqual(agent.model.model, "gpt-5.4-mini")
            settings = agent.kwargs["model_settings"]
            self.assertIsNone(settings.verbosity)
            self.assertFalse(settings.store)

    def test_generic_openai_compatible_url_uses_chat_completions(self):
        _internal, modify, insert = load_slides_tools()
        source = FakeResponsesModel(
            model="custom-model",
            openai_client=FakeAsyncOpenAI(
                api_key="compatible-key",
                base_url=COMPATIBLE_URL,
            ),
        )

        agents, codex = nested_agents(modify, insert, tool_for(source))

        self.assertEqual(codex, (False, False))
        for agent in agents:
            self.assertIsInstance(agent.model, FakeChatModel)
            self.assertEqual(agent.model.model, "custom-model")
            self.assertEqual(agent.model._client.base_url, COMPATIBLE_URL)
            self.assertEqual(agent.kwargs["model_settings"].kwargs, {})

    def test_openrouter_wrapper_and_client_are_preserved(self):
        _internal, modify, insert = load_slides_tools()
        source = FakeChatModel(
            model="anthropic/claude-sonnet-4.6",
            openai_client=FakeAsyncOpenAI(
                api_key="openrouter-key",
                base_url=OPENROUTER_URL,
            ),
            should_replay_reasoning_content="replay",
        )
        source._agency_swarm_openrouter_model_name = (
            "openrouter/anthropic/claude-sonnet-4.6"
        )

        cases = (
            (None, "anthropic/claude-sonnet-4.6"),
            ("openai/gpt-5.4-mini", "openai/gpt-5.4-mini"),
        )
        for run_model, expected_model in cases:
            with self.subTest(run_model=run_model):
                agents, codex = nested_agents(
                    modify,
                    insert,
                    tool_for(source, run_model=run_model),
                )

                self.assertEqual(codex, (False, False))
                for agent in agents:
                    self.assertIsInstance(agent.model, FakeChatModel)
                    self.assertEqual(agent.model.model, expected_model)
                    self.assertEqual(
                        agent.model._agency_swarm_openrouter_model_name,
                        f"openrouter/{expected_model}",
                    )
                    self.assertEqual(agent.model._client.api_key, "openrouter-key")
                    self.assertEqual(
                        agent.model.should_replay_reasoning_content,
                        "replay",
                    )
                    settings = agent.kwargs["model_settings"]
                    self.assertEqual(
                        settings.reasoning.kwargs,
                        {"effort": "high", "summary": None},
                    )
                    self.assertIsNone(settings.verbosity)
                    self.assertIsNone(settings.store)

    def test_litellm_and_ollama_routes_preserve_wrapper_config(self):
        _internal, modify, insert = load_slides_tools()
        cases = (
            FakeLitellmModel(
                model="openrouter/anthropic/claude-sonnet-4.6",
                api_key="litellm-key",
                base_url=OPENROUTER_URL,
                should_replay_reasoning_content="litellm-replay",
            ),
            FakeLitellmModel(
                model="ollama_chat/gemma4:e4b",
                api_key="ollama",
                base_url="http://localhost:11434",
            ),
        )

        for source in cases:
            with self.subTest(model=source.model):
                agents, codex = nested_agents(modify, insert, tool_for(source))
                self.assertEqual(codex, (False, False))
                for agent in agents:
                    self.assertIsInstance(agent.model, FakeLitellmModel)
                    self.assertEqual(agent.model.model, source.model)
                    self.assertEqual(agent.model.api_key, source.api_key)
                    self.assertEqual(agent.model.base_url, source.base_url)
                    self.assertEqual(
                        getattr(agent.model, "should_replay_reasoning_content", None),
                        getattr(source, "should_replay_reasoning_content", None),
                    )
                    self.assertEqual(agent.kwargs["model_settings"].kwargs, {})

    def test_run_config_model_keeps_caller_chat_transport(self):
        _internal, modify, insert = load_slides_tools()
        source = FakeChatModel(
            model="agent-model",
            openai_client=FakeAsyncOpenAI(
                api_key="gateway-key",
                base_url=COMPATIBLE_URL,
            ),
        )

        agents, codex = nested_agents(
            modify,
            insert,
            tool_for(source, run_model="request-model"),
        )

        self.assertEqual(codex, (False, False))
        for agent in agents:
            self.assertIsInstance(agent.model, FakeChatModel)
            self.assertEqual(agent.model.model, "request-model")
            self.assertEqual(agent.model._client.api_key, "gateway-key")

    def test_streamed_text_is_returned_when_final_result_is_empty(self):
        internal, _modify, insert = load_slides_tools()

        class Stream:
            def __init__(self):
                self.events = iter(
                    (
                        types.SimpleNamespace(
                            data=types.SimpleNamespace(
                                type="response.output_text.delta",
                                delta='{"slides":',
                            )
                        ),
                        types.SimpleNamespace(
                            data=types.SimpleNamespace(
                                type="response.output_text.delta",
                                delta="[]}",
                            )
                        ),
                    )
                )

            def __aiter__(self):
                return self

            async def __anext__(self):
                try:
                    return next(self.events)
                except StopIteration as exc:
                    raise StopAsyncIteration from exc

            async def wait_final_result(self):
                raise RuntimeError("structured parser returned no result")

        agent = types.SimpleNamespace(
            get_response_stream=lambda _prompt: Stream(),
        )
        result = asyncio.run(
            internal.get_internal_agent_response(
                agent,
                "plan",
                use_stream=True,
            )
        )

        self.assertEqual(result.final_output, '{"slides":[]}')
        self.assertEqual(
            insert._coerce_plan_response(result.final_output).slides,
            [],
        )

    def test_codex_model_strips_unsupported_fetch_settings(self):
        internal, _modify, _insert = load_slides_tools()
        model = internal._CodexResponsesModel(
            model="gpt-5.4-mini",
            openai_client=FakeAsyncOpenAI(base_url=CODEX_URL),
        )
        settings = FakeModelSettings(
            reasoning=FakeReasoning(effort="high", summary="auto"),
            store=False,
            truncation="auto",
            verbosity="low",
        )

        resolved = asyncio.run(
            model._fetch_response(None, [], settings),
        )

        self.assertIsNone(resolved.truncation)
        self.assertIsNone(resolved.verbosity)
        self.assertFalse(resolved.store)


if __name__ == "__main__":
    unittest.main()
