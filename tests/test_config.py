from __future__ import annotations

import importlib.util
import os
import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

ORCAROUTER_URL = "https://api.orcarouter.ai/v1"


class FakeLitellmModel:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        for key, value in kwargs.items():
            setattr(self, key, value)


def install_agency_swarm_stub() -> None:
    """Stub the agency_swarm package so config can import LitellmModel."""
    agency = types.ModuleType("agency_swarm")
    agency.LitellmModel = FakeLitellmModel
    sys.modules["agency_swarm"] = agency


def load_config():
    spec = importlib.util.spec_from_file_location("config", ROOT / "config.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["config"] = module
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class ConfigProviderRoutingTests(unittest.TestCase):
    def setUp(self):
        os.environ.pop("DEFAULT_MODEL", None)
        os.environ.pop("ORCAROUTER_API_KEY", None)
        sys.modules.pop("config", None)
        install_agency_swarm_stub()

    def test_bare_model_passes_through_unchanged(self):
        config = load_config()
        os.environ["DEFAULT_MODEL"] = "gpt-5.4"

        self.assertEqual(config.get_default_model(), "gpt-5.4")
        self.assertTrue(config.is_openai_provider())
        self.assertFalse(config.is_orcarouter_provider())

    def test_orcarouter_model_is_routed_to_litellm_with_gateway_credentials(self):
        config = load_config()
        os.environ["DEFAULT_MODEL"] = "orcarouter/gpt-5.6-luna"
        os.environ["ORCAROUTER_API_KEY"] = "orc-test-key"

        model = config.get_default_model()

        self.assertIsInstance(model, FakeLitellmModel)
        self.assertEqual(model.model, "gpt-5.6-luna")
        self.assertEqual(model.api_key, "orc-test-key")
        self.assertEqual(model.base_url, ORCAROUTER_URL)
        self.assertFalse(config.is_openai_provider())
        self.assertTrue(config.is_orcarouter_provider())

    def test_litellm_prefixed_model_preserves_legacy_behavior(self):
        config = load_config()
        os.environ["DEFAULT_MODEL"] = "litellm/anthropic/claude-sonnet-4-6"

        model = config.get_default_model()

        self.assertIsInstance(model, FakeLitellmModel)
        self.assertEqual(model.model, "anthropic/claude-sonnet-4-6")
        self.assertNotIn("base_url", model.kwargs)

    def test_other_provider_model_still_routes_through_litellm(self):
        config = load_config()
        os.environ["DEFAULT_MODEL"] = "anthropic/claude-sonnet-4-6"

        model = config.get_default_model()

        self.assertIsInstance(model, FakeLitellmModel)
        self.assertEqual(model.model, "anthropic/claude-sonnet-4-6")
        self.assertNotIn("api_key", model.kwargs)
        self.assertNotIn("base_url", model.kwargs)


if __name__ == "__main__":
    unittest.main()
