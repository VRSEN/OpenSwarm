from __future__ import annotations

import importlib
import sys
import types

import pytest


class FakeAsyncOpenAI:
    def __init__(self, *, api_key, base_url):
        self.api_key = api_key
        self.base_url = base_url


class FakeChatCompletionsModel:
    def __init__(self, *, model, openai_client):
        self.model = model
        self.openai_client = openai_client


class FakeLitellmModel:
    def __init__(self, *, model):
        self.model = model


@pytest.fixture
def config_module(monkeypatch):
    agents = types.ModuleType("agents")
    agents.OpenAIChatCompletionsModel = FakeChatCompletionsModel
    openai = types.ModuleType("openai")
    openai.AsyncOpenAI = FakeAsyncOpenAI
    agency_swarm = types.ModuleType("agency_swarm")
    agency_swarm.LitellmModel = FakeLitellmModel
    monkeypatch.setitem(sys.modules, "agents", agents)
    monkeypatch.setitem(sys.modules, "openai", openai)
    monkeypatch.setitem(sys.modules, "agency_swarm", agency_swarm)
    sys.modules.pop("config", None)
    yield importlib.import_module("config")
    sys.modules.pop("config", None)


def test_atlascloud_model_uses_chat_completions_client(monkeypatch, config_module):
    monkeypatch.setenv("ATLASCLOUD_API_KEY", "test-key")
    monkeypatch.setenv("DEFAULT_MODEL", "atlascloud/deepseek-ai/deepseek-v4-pro")

    model = config_module.get_default_model()

    assert isinstance(model, FakeChatCompletionsModel)
    assert model.model == "deepseek-ai/deepseek-v4-pro"
    assert model.openai_client.api_key == "test-key"
    assert model.openai_client.base_url == "https://api.atlascloud.ai/v1"
    assert config_module.is_openai_provider() is False


def test_atlascloud_model_requires_api_key(monkeypatch, config_module):
    monkeypatch.delenv("ATLASCLOUD_API_KEY", raising=False)
    monkeypatch.setenv("DEFAULT_MODEL", "atlascloud/deepseek-ai/deepseek-v4-pro")

    with pytest.raises(RuntimeError, match="ATLASCLOUD_API_KEY"):
        config_module.get_default_model()


def test_atlascloud_model_requires_model_id(monkeypatch, config_module):
    monkeypatch.setenv("ATLASCLOUD_API_KEY", "test-key")
    monkeypatch.setenv("DEFAULT_MODEL", "atlascloud/")

    with pytest.raises(ValueError, match="model ID"):
        config_module.get_default_model()


def test_existing_litellm_route_is_unchanged(monkeypatch, config_module):
    monkeypatch.setenv("DEFAULT_MODEL", "anthropic/claude-sonnet")

    model = config_module.get_default_model()

    assert isinstance(model, FakeLitellmModel)
    assert model.model == "anthropic/claude-sonnet"
