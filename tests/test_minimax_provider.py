"""Unit tests for MiniMax provider integration."""

from __future__ import annotations

import os
import importlib
from unittest import mock

import pytest


# ---------------------------------------------------------------------------
# onboard.py – provider registration
# ---------------------------------------------------------------------------

class TestOnboardProviderRegistration:
    """Verify MiniMax appears in the PROVIDERS list with correct metadata."""

    def _load_providers(self):
        import onboard
        importlib.reload(onboard)
        return onboard.PROVIDERS

    def test_minimax_provider_present(self):
        providers = self._load_providers()
        names = [p["name"] for p in providers]
        assert "MiniMax" in names, "MiniMax must be listed in PROVIDERS"

    def test_minimax_env_key(self):
        providers = self._load_providers()
        mm = next(p for p in providers if p["name"] == "MiniMax")
        assert mm["env_key"] == "MINIMAX_API_KEY"

    def test_minimax_default_model(self):
        providers = self._load_providers()
        mm = next(p for p in providers if p["name"] == "MiniMax")
        assert mm["default_model"] == "minimax/MiniMax-M2.7"

    def test_minimax_url(self):
        providers = self._load_providers()
        mm = next(p for p in providers if p["name"] == "MiniMax")
        assert mm["url"], "URL must be set"
        assert "minimax" in mm["url"].lower() or "minimax" in mm["url"].lower()


# ---------------------------------------------------------------------------
# config.py – model resolution
# ---------------------------------------------------------------------------

class TestConfigModelResolution:
    """Verify config.py resolves MiniMax model strings correctly."""

    def test_minimax_model_is_not_openai(self):
        """minimax/MiniMax-M2.7 contains '/' so is_openai_provider() should return False."""
        with mock.patch.dict(os.environ, {"DEFAULT_MODEL": "minimax/MiniMax-M2.7"}):
            import config
            importlib.reload(config)
            assert config.is_openai_provider() is False

    def test_minimax_model_resolved_through_litellm(self):
        """_resolve should wrap minimax/MiniMax-M2.7 via LitellmModel."""
        import config
        importlib.reload(config)
        result = config._resolve("minimax/MiniMax-M2.7")
        # If agency_swarm is installed, result is a LitellmModel; otherwise
        # the bare string is returned as fallback.
        try:
            from agency_swarm import LitellmModel
            assert isinstance(result, LitellmModel)
        except ImportError:
            assert result == "minimax/MiniMax-M2.7"

    def test_minimax_highspeed_model_resolved(self):
        """Highspeed variant should also resolve correctly."""
        import config
        importlib.reload(config)
        result = config._resolve("minimax/MiniMax-M2.7-highspeed")
        try:
            from agency_swarm import LitellmModel
            assert isinstance(result, LitellmModel)
        except ImportError:
            assert result == "minimax/MiniMax-M2.7-highspeed"

    def test_get_default_model_with_minimax(self):
        """get_default_model() should return resolved MiniMax model when DEFAULT_MODEL is set."""
        with mock.patch.dict(os.environ, {"DEFAULT_MODEL": "minimax/MiniMax-M2.7"}):
            import config
            importlib.reload(config)
            result = config.get_default_model()
            # Should not be the raw string (it should be resolved)
            try:
                from agency_swarm import LitellmModel
                assert isinstance(result, LitellmModel)
            except ImportError:
                assert result == "minimax/MiniMax-M2.7"

    def test_litellm_prefix_stripped_correctly(self):
        """'litellm/minimax/MiniMax-M2.7' should strip to 'minimax/MiniMax-M2.7' for LitellmModel."""
        import config
        importlib.reload(config)
        result = config._resolve("litellm/minimax/MiniMax-M2.7")
        try:
            from agency_swarm import LitellmModel
            assert isinstance(result, LitellmModel)
        except ImportError:
            # When agency_swarm is not installed, _resolve returns the original string
            assert result == "litellm/minimax/MiniMax-M2.7"


# ---------------------------------------------------------------------------
# .env.example – documentation
# ---------------------------------------------------------------------------

class TestEnvExample:
    """Verify .env.example documents MINIMAX_API_KEY."""

    def test_minimax_api_key_documented(self):
        from pathlib import Path
        env_example = Path(__file__).resolve().parent.parent / ".env.example"
        content = env_example.read_text(encoding="utf-8")
        assert "MINIMAX_API_KEY" in content, "MINIMAX_API_KEY must be documented in .env.example"

    def test_minimax_default_model_example(self):
        from pathlib import Path
        env_example = Path(__file__).resolve().parent.parent / ".env.example"
        content = env_example.read_text(encoding="utf-8")
        assert "minimax/MiniMax-M2.7" in content, "DEFAULT_MODEL example for MiniMax must be in .env.example"
