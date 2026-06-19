"""Smoke test that OpenAI hosted tools follow the selected model route."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager, redirect_stderr, redirect_stdout
import importlib
import io
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agency_swarm.tools import WebSearchTool  # noqa: E402

AGENTS: tuple[tuple[str, str], ...] = (
    ("deep_research.deep_research", "create_deep_research"),
    ("virtual_assistant.virtual_assistant", "create_virtual_assistant"),
    ("docs_agent.docs_agent", "create_docs_agent"),
    ("slides_agent.slides_agent", "create_slides_agent"),
    ("data_analyst_agent.data_analyst_agent", "create_data_analyst"),
)


@contextmanager
def _default_model(model: str) -> Iterator[None]:
    previous = os.environ.get("DEFAULT_MODEL")
    os.environ["DEFAULT_MODEL"] = model
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("DEFAULT_MODEL", None)
        else:
            os.environ["DEFAULT_MODEL"] = previous


def _assert_helper_is_lazy() -> None:
    import config

    called: list[object] = []

    def factory() -> object:
        called.append(object())
        return object()

    with _default_model("litellm/ollama_chat/gemma4:e4b"):
        tools = config.openai_hosted_tools(factory)
    if tools or called:
        raise AssertionError("Hosted tool factory ran for a non-OpenAI route")

    with _default_model("gpt-5.2"):
        tools = config.openai_hosted_tools(factory)
    if len(tools) != 1 or len(called) != 1:
        raise AssertionError("Hosted tool factory did not run once for OpenAI")


def _assert_hosted_tool_count(model: str, expected: int) -> None:
    with _default_model(model):
        for module_name, factory_name in AGENTS:
            agent = _create_agent(module_name, factory_name)
            actual = sum(isinstance(tool, WebSearchTool) for tool in agent.tools)
            if actual != expected:
                raise AssertionError(
                    f"{module_name} expected {expected} WebSearchTool instances, got {actual}"
                )


def _create_agent(module_name: str, factory_name: str) -> object:
    stdout = io.StringIO()
    stderr = io.StringIO()
    try:
        with redirect_stdout(stdout), redirect_stderr(stderr):
            module = importlib.import_module(module_name)
            return getattr(module, factory_name)()
    except Exception:
        sys.stdout.write(stdout.getvalue())
        sys.stderr.write(stderr.getvalue())
        raise


def main() -> None:
    _assert_helper_is_lazy()
    _assert_hosted_tool_count("gpt-5.2", 1)
    _assert_hosted_tool_count("litellm/ollama_chat/gemma4:e4b", 0)
    _assert_hosted_tool_count("litellm/gemini/gemini-3-flash", 0)
    _assert_hosted_tool_count("openrouter/openai/gpt-4o-mini", 0)
    print("Hosted tool gating smoke passed")


if __name__ == "__main__":
    main()
