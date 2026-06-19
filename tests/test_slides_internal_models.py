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
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OPENAI_BASE_URL = "https://api.openai.com/v1"
CODEX_COMPATIBLE_BASE_URL = "https://codex.example.test/v1"
OPENAI_COMPATIBLE_BASE_URL = "https://gateway.example.test/v1"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


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
        self.reasoning = kwargs.get("reasoning")
        self.verbosity = kwargs.get("verbosity")
        self.store = kwargs.get("store")
        self.truncation = kwargs.get("truncation")
        self.kwargs = kwargs


class FakeReasoning:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class FakeAsyncOpenAI:
    def __init__(
        self,
        *,
        api_key="env-key",
        base_url=OPENAI_BASE_URL,
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
        self.default_query = default_query
        self._custom_query = default_query


class FakeOpenAIResponsesModel:
    def __init__(self, *, model, openai_client):
        self.model = model
        self.openai_client = openai_client

    async def _fetch_response(self, _system, _input, model_settings, *args, **kwargs):
        return model_settings


class FakeLitellmModel:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.model = kwargs.get("model")


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

    agents = types.ModuleType("agents")
    agents.OpenAIResponsesModel = FakeOpenAIResponsesModel

    agents_extensions = types.ModuleType("agents.extensions")
    agents_models = types.ModuleType("agents.extensions.models")
    agents_litellm = types.ModuleType("agents.extensions.models.litellm_model")
    agents_litellm.LitellmModel = FakeLitellmModel

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
            "agents": agents,
            "agents.extensions": agents_extensions,
            "agents.extensions.models": agents_models,
            "agents.extensions.models.litellm_model": agents_litellm,
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

    slide_file_utils = types.ModuleType("slides_agent.tools.slide_file_utils")
    slide_file_utils.get_project_dir = lambda name: Path(name)
    slide_file_utils.apply_renames = lambda _renames: None
    slide_file_utils.build_slide_name = (
        lambda prefix, idx, pad, suffix="": f"{prefix}_{idx:0{pad}d}{suffix}"
    )
    slide_file_utils.compute_pad_width = lambda _slides, extra_count=0: 2
    slide_file_utils.list_slide_files = lambda *_args, **_kwargs: []

    slide_html_utils = types.ModuleType("slides_agent.tools.slide_html_utils")
    slide_html_utils.ensure_full_html = lambda html: (html or "<html></html>", [])
    slide_html_utils.list_slide_filenames = lambda _project_dir: []
    slide_html_utils.validate_html = lambda *_args, **_kwargs: {"valid": True}
    slide_html_utils._strip_html_to_text = lambda html: html

    template_registry = types.ModuleType("slides_agent.tools.template_registry")
    template_registry.load_template_index = lambda _project_dir: {}
    template_registry.save_template_index = lambda *_args, **_kwargs: None
    template_registry.template_path = lambda project_dir, key: Path(project_dir) / key

    sys.modules.update(
        {
            "slides_agent": slides_agent,
            "slides_agent.tools": tools,
            "slides_agent.tools.slide_file_utils": slide_file_utils,
            "slides_agent.tools.slide_html_utils": slide_html_utils,
            "slides_agent.tools.template_registry": template_registry,
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
    load_module("slides_agent.tools.internal_model", "slides_agent/tools/internal_model.py")
    modify = load_module(
        "slides_agent.tools.ModifySlide",
        "slides_agent/tools/ModifySlide.py",
    )
    insert = load_module(
        "slides_agent.tools.InsertNewSlides",
        "slides_agent/tools/InsertNewSlides.py",
    )
    return modify, insert


def tool_for(model):
    agent = types.SimpleNamespace(model=model)
    master = types.SimpleNamespace(
        current_agent_name="Slides Agent",
        agents={"Slides Agent": agent},
    )
    return types.SimpleNamespace(_context=types.SimpleNamespace(context=master))


def settings_for(agent):
    return agent.kwargs["model_settings"].kwargs


class SlidesInternalModelTests(unittest.TestCase):
    def setUp(self):
        install_stubs()
        install_package_stubs()
        os.environ.pop("DEFAULT_MODEL", None)
        for name in (
            "slides_agent.tools.internal_model",
            "slides_agent.tools.ModifySlide",
            "slides_agent.tools.InsertNewSlides",
        ):
            sys.modules.pop(name, None)

    def assert_openai_settings(self, agent, *, is_codex=False):
        settings = settings_for(agent)
        self.assertEqual(
            settings["reasoning"].kwargs,
            {"effort": "high", "summary": "auto"},
        )
        self.assertEqual(settings["verbosity"], None if is_codex else "medium")
        self.assertEqual(settings["store"], False if is_codex else None)

    def assert_no_openai_settings(self, agent):
        self.assertEqual(settings_for(agent), {})

    def test_internal_agents_inherit_selected_openai_model_and_client_config(self):
        modify, insert = load_slides_tools()

        client = FakeAsyncOpenAI(
            api_key="request-key",
            base_url=OPENAI_BASE_URL,
            organization="request-org",
            project="request-project",
            timeout=42,
            max_retries=4,
            default_headers={"X-Request": "slides"},
            default_query={"source": "request"},
        )
        selected = FakeOpenAIResponsesModel(
            model="gpt-5.4-mini",
            openai_client=client,
        )

        writer, writer_codex = modify._make_html_writer_agent(tool=tool_for(selected))
        planner, planner_codex = insert._make_planner_agent(tool=tool_for(selected))

        self.assertFalse(writer_codex)
        self.assertFalse(planner_codex)
        self.assertEqual(writer.model.model, "gpt-5.4-mini")
        self.assertEqual(planner.model.model, "gpt-5.4-mini")
        for nested in (writer.model.openai_client, planner.model.openai_client):
            self.assertIsNot(nested, client)
            self.assertEqual(nested.api_key, "request-key")
            self.assertEqual(nested.base_url, OPENAI_BASE_URL)
            self.assertEqual(nested.organization, "request-org")
            self.assertEqual(nested.project, "request-project")
            self.assertEqual(nested.timeout, 42)
            self.assertEqual(nested.max_retries, 4)
            self.assertEqual(nested._custom_headers, {"X-Request": "slides"})
            self.assertEqual(nested.default_query, {"source": "request"})
        self.assert_openai_settings(writer)
        self.assert_openai_settings(planner)

    def test_codex_compatible_client_keeps_model_and_uses_stream_settings(self):
        modify, insert = load_slides_tools()

        client = FakeAsyncOpenAI(
            api_key="request-key",
            base_url=CODEX_COMPATIBLE_BASE_URL,
        )
        selected = types.SimpleNamespace(model="gpt-5.4-mini", _client=client)

        writer, writer_codex = modify._make_html_writer_agent(tool=tool_for(selected))
        planner, planner_codex = insert._make_planner_agent(tool=tool_for(selected))

        self.assertTrue(writer_codex)
        self.assertTrue(planner_codex)
        self.assertEqual(writer.model.model, "gpt-5.4-mini")
        self.assertEqual(planner.model.model, "gpt-5.4-mini")
        self.assertEqual(writer.model.openai_client.api_key, "request-key")
        self.assertEqual(planner.model.openai_client.base_url, CODEX_COMPATIBLE_BASE_URL)
        self.assert_openai_settings(writer, is_codex=True)
        self.assert_openai_settings(planner, is_codex=True)

    def test_openai_compatible_plain_client_is_not_treated_as_codex(self):
        modify, insert = load_slides_tools()

        client = FakeAsyncOpenAI(
            api_key="request-compatible-key",
            base_url=OPENAI_COMPATIBLE_BASE_URL,
        )
        selected = FakeOpenAIResponsesModel(
            model="custom-chat-model",
            openai_client=client,
        )

        writer, writer_codex = modify._make_html_writer_agent(tool=tool_for(selected))
        planner, planner_codex = insert._make_planner_agent(tool=tool_for(selected))

        self.assertFalse(writer_codex)
        self.assertFalse(planner_codex)
        self.assertIsInstance(writer.model, FakeOpenAIResponsesModel)
        self.assertIsInstance(planner.model, FakeOpenAIResponsesModel)
        self.assertEqual(writer.model.model, "custom-chat-model")
        self.assertEqual(planner.model.model, "custom-chat-model")
        self.assertEqual(writer.model.openai_client.base_url, OPENAI_COMPATIBLE_BASE_URL)
        self.assertEqual(planner.model.openai_client.base_url, OPENAI_COMPATIBLE_BASE_URL)
        self.assert_no_openai_settings(writer)
        self.assert_no_openai_settings(planner)

    def test_litellm_selected_model_and_config_are_preserved(self):
        modify, insert = load_slides_tools()

        selected = FakeLitellmModel(
            model="openrouter/anthropic/claude-sonnet-4-6",
            api_key="request-openrouter-key",
            base_url=OPENROUTER_BASE_URL,
        )

        writer, writer_codex = modify._make_html_writer_agent(tool=tool_for(selected))
        planner, planner_codex = insert._make_planner_agent(tool=tool_for(selected))

        self.assertFalse(writer_codex)
        self.assertFalse(planner_codex)
        self.assertEqual(writer.model.model, "openrouter/anthropic/claude-sonnet-4-6")
        self.assertEqual(planner.model.model, "openrouter/anthropic/claude-sonnet-4-6")
        self.assertEqual(writer.model.kwargs["api_key"], "request-openrouter-key")
        self.assertEqual(planner.model.kwargs["api_key"], "request-openrouter-key")
        self.assertEqual(writer.model.kwargs["base_url"], OPENROUTER_BASE_URL)
        self.assertEqual(planner.model.kwargs["base_url"], OPENROUTER_BASE_URL)
        self.assert_no_openai_settings(writer)
        self.assert_no_openai_settings(planner)

    def test_openai_wrapper_provider_model_routes_to_litellm_with_client_config(self):
        modify, insert = load_slides_tools()

        client = FakeAsyncOpenAI(
            api_key="request-openrouter-key",
            base_url=OPENROUTER_BASE_URL,
        )
        selected = FakeOpenAIResponsesModel(
            model="openrouter/anthropic/claude-sonnet-4-6",
            openai_client=client,
        )

        writer, writer_codex = modify._make_html_writer_agent(tool=tool_for(selected))
        planner, planner_codex = insert._make_planner_agent(tool=tool_for(selected))

        self.assertFalse(writer_codex)
        self.assertFalse(planner_codex)
        self.assertIsInstance(writer.model, FakeLitellmModel)
        self.assertIsInstance(planner.model, FakeLitellmModel)
        self.assertEqual(writer.model.model, "openrouter/anthropic/claude-sonnet-4-6")
        self.assertEqual(planner.model.model, "openrouter/anthropic/claude-sonnet-4-6")
        self.assertEqual(writer.model.kwargs["api_key"], "request-openrouter-key")
        self.assertEqual(planner.model.kwargs["api_key"], "request-openrouter-key")
        self.assertEqual(writer.model.kwargs["base_url"], OPENROUTER_BASE_URL)
        self.assertEqual(planner.model.kwargs["base_url"], OPENROUTER_BASE_URL)
        self.assert_no_openai_settings(writer)
        self.assert_no_openai_settings(planner)

    def test_internal_agents_fall_back_to_default_model_env(self):
        os.environ["DEFAULT_MODEL"] = "gpt-5.2"
        modify, insert = load_slides_tools()

        writer, writer_codex = modify._make_html_writer_agent(tool=None)
        planner, planner_codex = insert._make_planner_agent(tool=None)

        self.assertFalse(writer_codex)
        self.assertFalse(planner_codex)
        self.assertEqual(writer.model.model, "gpt-5.2")
        self.assertEqual(planner.model.model, "gpt-5.2")
        self.assert_openai_settings(writer)
        self.assert_openai_settings(planner)

    def test_codex_model_strips_unsupported_settings_at_fetch_boundary(self):
        modify, insert = load_slides_tools()

        settings = FakeModelSettings(
            reasoning=FakeReasoning(effort="high", summary="auto"),
            store=False,
            truncation="auto",
            verbosity="low",
        )

        writer = modify._CodexResponsesModel(
            model="gpt-5.4-mini",
            openai_client=FakeAsyncOpenAI(base_url=CODEX_COMPATIBLE_BASE_URL),
        )
        planner = insert._CodexResponsesModel(
            model="gpt-5.4-mini",
            openai_client=FakeAsyncOpenAI(base_url=CODEX_COMPATIBLE_BASE_URL),
        )

        writer_settings = asyncio.run(
            writer._fetch_response(None, [], settings, [], None, [])
        )
        planner_settings = asyncio.run(
            planner._fetch_response(None, [], settings, [], None, [])
        )

        for nested in (writer_settings, planner_settings):
            self.assertIsNone(nested.truncation)
            self.assertIsNone(nested.verbosity)
            self.assertFalse(nested.store)
            self.assertEqual(
                nested.reasoning.kwargs,
                {"effort": "high", "summary": "auto"},
            )


if __name__ == "__main__":
    unittest.main()
