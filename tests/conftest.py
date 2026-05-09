"""Test scaffolding.

These tests target configuration and tool-routing logic that lives in
config.py, orchestrator/tools/SwitchProvider.py, and onboard.py. The
production code imports `agency_swarm` (and the wider OpenAI Agents SDK
ecosystem), but the logic under test does not actually need any of that —
SwitchProvider only needs `BaseTool` as a Pydantic-shaped base class, and
config._resolve only needs `LitellmModel` as a constructable callable.

Stubbing those two surfaces here keeps the test suite runnable from a bare
Python install (`pip install pytest python-dotenv pydantic`) without
requiring the multi-hundred-megabyte agency-swarm + openai-agents-sdk +
LiteLLM dependency chain.
"""

import sys
import types

from pydantic import BaseModel


def _install_agency_swarm_stubs() -> None:
    """Register fake `agency_swarm` and supporting modules in sys.modules.

    Production code does:
        from agency_swarm.tools import BaseTool
        from agency_swarm import LitellmModel, Agent, ModelSettings
        from openai.types.shared import Reasoning

    The orchestrator package imports Agent/ModelSettings/Reasoning at module
    load time (via `from .orchestrator import create_orchestrator` in
    orchestrator/__init__.py). Importing `orchestrator.tools.SwitchProvider`
    therefore triggers that chain. Stub all of them — none are exercised by
    the test logic; they only need to be importable.
    """
    pkg = sys.modules.get("agency_swarm")
    if pkg is not None and getattr(pkg, "_openswarm_test_stub", False):
        return  # already installed

    pkg = types.ModuleType("agency_swarm")
    pkg._openswarm_test_stub = True  # type: ignore[attr-defined]

    class _Agent:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

    class _ModelSettings:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

    class _LitellmModel:
        """Records constructor kwargs as attributes for test assertions."""

        def __init__(self, model, api_key=None, base_url=None, **kwargs):
            self.model = model
            self.api_key = api_key
            self.base_url = base_url
            self.kwargs = kwargs

    pkg.Agent = _Agent  # type: ignore[attr-defined]
    pkg.ModelSettings = _ModelSettings  # type: ignore[attr-defined]
    pkg.LitellmModel = _LitellmModel  # type: ignore[attr-defined]

    tools = types.ModuleType("agency_swarm.tools")

    class _BaseTool(BaseModel):
        def run(self):
            raise NotImplementedError

    tools.BaseTool = _BaseTool  # type: ignore[attr-defined]

    sys.modules["agency_swarm"] = pkg
    sys.modules["agency_swarm.tools"] = tools

    # openai.types.shared.Reasoning — orchestrator imports this directly.
    # Real openai package may already be installed, so only stub the path
    # if it doesn't resolve.
    try:
        from openai.types.shared import Reasoning  # noqa: F401
    except (ImportError, ModuleNotFoundError):
        openai_pkg = sys.modules.get("openai") or types.ModuleType("openai")
        openai_types = sys.modules.get("openai.types") or types.ModuleType("openai.types")
        openai_shared = types.ModuleType("openai.types.shared")

        class _Reasoning:
            def __init__(self, **kwargs):
                for k, v in kwargs.items():
                    setattr(self, k, v)

        openai_shared.Reasoning = _Reasoning  # type: ignore[attr-defined]
        sys.modules["openai"] = openai_pkg
        sys.modules["openai.types"] = openai_types
        sys.modules["openai.types.shared"] = openai_shared


_install_agency_swarm_stubs()
