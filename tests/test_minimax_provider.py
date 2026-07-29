"""Unit tests for MiniMax provider configuration in config.py.

These tests avoid any network calls and do not require ``agency_swarm`` to be
installed: ``config._resolve`` falls back to returning the raw model string when
the dependency is absent, so the region/endpoint selection logic is exercised
directly through the public helpers.
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config  # noqa: E402


@pytest.fixture(autouse=True)
def _reload_config():
    """Reload config with a clean MiniMax environment for each test."""
    for key in ("DEFAULT_MODEL", "MINIMAX_REGION", "MINIMAX_API_BASE",
                "MINIMAX_ANTHROPIC_BASE", "MINIMAX_API_KEY"):
        os.environ.pop(key, None)
    importlib.reload(config)
    yield
    importlib.reload(config)


class TestMiniMaxDetection:
    def test_openai_compatible_form_detected(self):
        assert config.is_minimax_model("minimax/MiniMax-M3") is True

    def test_anthropic_compatible_form_detected(self):
        assert config.is_minimax_model("anthropic/MiniMax-M2.7") is True

    def test_case_insensitive(self):
        assert config.is_minimax_model("MINIMAX/MINIMAX-M3") is True

    def test_other_providers_not_detected(self):
        assert config.is_minimax_model("anthropic/claude-sonnet-4-6") is False
        assert config.is_minimax_model("litellm/gemini/gemini-3-flash") is False


class TestMiniMaxRegion:
    def test_default_region_is_global(self):
        assert config.minimax_region() == "global"

    def test_cn_region_selected(self):
        with mock.patch.dict(os.environ, {"MINIMAX_REGION": "cn"}):
            assert config.minimax_region() == "cn"

    def test_cn_zh_alias(self):
        with mock.patch.dict(os.environ, {"MINIMAX_REGION": "cn_zh"}):
            assert config.minimax_region() == "cn"


class TestMiniMaxBaseUrl:
    def test_global_openai_endpoint(self):
        assert config.minimax_base_url("minimax/MiniMax-M3") == "https://api.minimax.io/v1"

    def test_global_anthropic_endpoint(self):
        assert config.minimax_base_url("anthropic/MiniMax-M3") == "https://api.minimax.io/anthropic"

    def test_cn_openai_endpoint(self):
        with mock.patch.dict(os.environ, {"MINIMAX_REGION": "cn"}):
            assert config.minimax_base_url("minimax/MiniMax-M2.7") == "https://api.minimaxi.com/v1"

    def test_cn_anthropic_endpoint(self):
        with mock.patch.dict(os.environ, {"MINIMAX_REGION": "cn"}):
            assert config.minimax_base_url("anthropic/MiniMax-M3") == "https://api.minimaxi.com/anthropic"

    def test_explicit_openai_override_wins(self):
        with mock.patch.dict(os.environ, {"MINIMAX_API_BASE": "https://proxy.example/v1"}):
            assert config.minimax_base_url("minimax/MiniMax-M3") == "https://proxy.example/v1"

    def test_explicit_anthropic_override_wins(self):
        with mock.patch.dict(os.environ, {"MINIMAX_ANTHROPIC_BASE": "https://proxy.example/anthropic"}):
            assert config.minimax_base_url("anthropic/MiniMax-M3") == "https://proxy.example/anthropic"


class TestMiniMaxKwargs:
    def test_api_base_always_present(self):
        kwargs = config._minimax_kwargs("minimax/MiniMax-M3")
        assert kwargs["api_base"] == "https://api.minimax.io/v1"
        assert "api_key" not in kwargs

    def test_api_key_included_when_set(self):
        with mock.patch.dict(os.environ, {"MINIMAX_API_KEY": "unit-test-placeholder"}):
            kwargs = config._minimax_kwargs("anthropic/MiniMax-M3")
        assert kwargs["api_base"] == "https://api.minimax.io/anthropic"
        assert kwargs["api_key"] == "unit-test-placeholder"


class TestResolveAndDefaultModel:
    def test_minimax_openai_route_resolves(self):
        result = config._resolve("minimax/MiniMax-M3")
        try:
            from agency_swarm import LitellmModel
            assert isinstance(result, LitellmModel)
        except ImportError:
            assert result == "minimax/MiniMax-M3"

    def test_minimax_anthropic_route_resolves(self):
        result = config._resolve("anthropic/MiniMax-M2.7")
        try:
            from agency_swarm import LitellmModel
            assert isinstance(result, LitellmModel)
        except ImportError:
            assert result == "anthropic/MiniMax-M2.7"

    def test_minimax_model_is_not_openai_provider(self):
        with mock.patch.dict(os.environ, {"DEFAULT_MODEL": "minimax/MiniMax-M3"}):
            importlib.reload(config)
            assert config.is_openai_provider() is False

    def test_get_default_model_with_minimax(self):
        with mock.patch.dict(os.environ, {"DEFAULT_MODEL": "minimax/MiniMax-M2.7"}):
            importlib.reload(config)
            result = config.get_default_model()
            try:
                from agency_swarm import LitellmModel
                assert isinstance(result, LitellmModel)
            except ImportError:
                assert result == "minimax/MiniMax-M2.7"


class TestEnvExample:
    def _content(self):
        return (ROOT / ".env.example").read_text(encoding="utf-8")

    def test_api_key_documented(self):
        assert "MINIMAX_API_KEY" in self._content()

    def test_region_documented(self):
        assert "MINIMAX_REGION" in self._content()

    def test_both_models_documented(self):
        content = self._content()
        assert "MiniMax-M3" in content
        assert "MiniMax-M2.7" in content

    def test_both_routes_documented(self):
        content = self._content()
        assert "minimax/MiniMax-M3" in content
        assert "anthropic/MiniMax-M3" in content

    def test_both_regions_documented(self):
        content = self._content()
        assert "api.minimax.io" in content
        assert "api.minimaxi.com" in content
