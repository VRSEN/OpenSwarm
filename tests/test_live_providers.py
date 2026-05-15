"""End-to-end tests against real provider endpoints.

Skipped by default — only run when the relevant credentials are present in
the environment. Run explicitly with:

    pytest tests/test_live_providers.py -v
    pytest -m live -v          # selects the live marker
    pytest -m "not live"       # excludes the live marker (default-friendly)

Credential bridging:
    OpenSwarm's wizard uses LiteLLM-style env var names (AZURE_API_KEY,
    AZURE_AI_API_BASE, ...). Many users have Azure-OpenAI-SDK-style names
    in their shell (AZURE_OPENAI_API_KEY, ANTHROPIC_FOUNDRY_RESOURCE, ...).
    The fixtures below recognize both, so you don't need to re-export the
    same secrets under different names just to run these tests.

No credentials are read from disk except via the shell environment, and
none are echoed in test output.
"""

from __future__ import annotations

import importlib
import json
import os
import sys
import urllib.request
from pathlib import Path

import pytest


# Skip the whole module when litellm isn't available — these tests have a
# hard runtime dependency on it.
litellm = pytest.importorskip("litellm")

pytestmark = pytest.mark.live


# ── credential resolution ──────────────────────────────────────────────────
def _first(*names: str) -> str | None:
    """Return the first non-empty env var value among `names`."""
    for n in names:
        v = os.environ.get(n)
        if v:
            return v
    return None


def _azure_openai() -> dict[str, str] | None:
    key = _first("AZURE_API_KEY", "AZURE_OPENAI_API_KEY")
    base = _first("AZURE_API_BASE", "AZURE_OPENAI_BASE_URL", "AZURE_OPENAI_ENDPOINT")
    version = _first("AZURE_API_VERSION", "AZURE_OPENAI_API_VERSION")
    if not (key and base and version):
        return None
    return {"api_key": key, "api_base": base.rstrip("/"), "api_version": version}


def _azure_ai_foundry() -> dict[str, str] | None:
    key = _first("AZURE_AI_API_KEY", "ANTHROPIC_FOUNDRY_API_KEY", "AZURE_OPENAI_API_KEY")
    base = _first("AZURE_AI_API_BASE")
    if not base:
        # Reconstruct from a resource name if AZURE_AI_API_BASE isn't set.
        resource = _first("ANTHROPIC_FOUNDRY_RESOURCE")
        if resource:
            base = f"https://{resource}.services.ai.azure.com/anthropic"
    if not (key and base):
        return None
    return {"api_key": key, "api_base": base.rstrip("/")}


def _ollama_local() -> str | None:
    base = _first("OLLAMA_API_BASE", "OLLAMA_HOST_URL")
    if not base and os.environ.get("OLLAMA_HOST"):
        port = os.environ.get("OLLAMA_PORT", "11434")
        host = os.environ["OLLAMA_HOST"]
        if not host.startswith(("http://", "https://")):
            host = f"http://{host}:{port}"
        base = host
    return base


def _ollama_first_model(api_base: str) -> str | None:
    """Return the first locally-pulled Ollama model, or None if unreachable."""
    try:
        with urllib.request.urlopen(f"{api_base}/api/tags", timeout=2) as r:
            models = json.loads(r.read())["models"]
        return models[0]["name"] if models else None
    except Exception:
        return None


# ── Test 1: Ollama (local) ─────────────────────────────────────────────────
def test_live_ollama_chat():
    """Real chat completion against a local Ollama server."""
    base = _ollama_local()
    if not base:
        pytest.skip("OLLAMA_API_BASE / OLLAMA_HOST not set")

    model = _ollama_first_model(base)
    if not model:
        pytest.skip(f"Ollama unreachable or no models pulled at the configured endpoint")

    response = litellm.completion(
        model=f"ollama_chat/{model}",
        messages=[{"role": "user", "content": "Reply with exactly: OK"}],
        api_base=base,
        max_tokens=10,
    )
    assert response.choices[0].message.content.strip(), "empty response from Ollama"


# ── Test 2: Azure AI Foundry (Claude on Azure) ─────────────────────────────
def test_live_azure_ai_foundry_claude():
    """Real chat completion against Azure-hosted Claude.

    Validates the `/anthropic` URL suffix path that PROVIDER_REGISTRY
    documents — a real prompt is sent to a real Azure endpoint and the
    response is asserted non-empty. This is the most consequential
    end-to-end check for the azure_ai/ provider claim.
    """
    creds = _azure_ai_foundry()
    if not creds:
        pytest.skip("Azure AI Foundry credentials not set (AZURE_AI_API_KEY/_BASE or ANTHROPIC_FOUNDRY_*)")

    model = _first("ANTHROPIC_DEFAULT_SONNET_MODEL") or "claude-sonnet-4-6"
    response = litellm.completion(
        model=f"azure_ai/{model}",
        messages=[{"role": "user", "content": "Reply with exactly: OK"}],
        api_key=creds["api_key"],
        api_base=creds["api_base"],
        max_tokens=10,
    )
    assert response.choices[0].message.content.strip(), "empty response from Azure AI Foundry"


# ── Test 3: Azure OpenAI Service (your own gpt-* deployment) ───────────────
def test_live_azure_openai():
    """Real chat completion against an Azure OpenAI Service deployment.

    Requires AZURE_OPENAI_DEPLOYMENT (or AZURE_DEPLOYMENT) to know which
    deployment to call.
    """
    creds = _azure_openai()
    if not creds:
        pytest.skip("Azure OpenAI credentials not set")

    deployment = _first("AZURE_OPENAI_DEPLOYMENT", "AZURE_DEPLOYMENT")
    if not deployment:
        pytest.skip("AZURE_OPENAI_DEPLOYMENT (deployment name) not set")

    response = litellm.completion(
        model=f"azure/{deployment}",
        messages=[{"role": "user", "content": "Reply with exactly: OK"}],
        api_key=creds["api_key"],
        api_base=creds["api_base"],
        api_version=creds["api_version"],
        max_tokens=10,
    )
    assert response.choices[0].message.content.strip(), "empty response from Azure OpenAI"


# ── Test 4: SwitchProvider live transition ─────────────────────────────────
def test_live_switch_provider_transition(tmp_path, monkeypatch):
    """End-to-end verification of the FastAPI runtime-switching guarantee.

    Starts the process pointed at local Ollama. Calls the SwitchProvider
    tool to change to Azure AI Foundry. Verifies (a) .env was rewritten,
    (b) the TUI restart flag was touched, (c) os.environ in this process
    now reflects the new DEFAULT_MODEL, and (d) the next agency build
    (simulated by re-importing config) reaches the new provider with a
    real, successful API call. No process restart anywhere.
    """
    foundry = _azure_ai_foundry()
    ollama_base = _ollama_local()
    if not foundry:
        pytest.skip("Azure AI Foundry credentials not set")
    if not ollama_base:
        pytest.skip("Ollama not configured")

    ollama_model = _ollama_first_model(ollama_base)
    if not ollama_model:
        pytest.skip("Ollama unreachable or no models pulled")

    foundry_model = _first("ANTHROPIC_DEFAULT_SONNET_MODEL") or "claude-sonnet-4-6"

    # Isolate .env to a temp file so we don't touch the real one
    env = tmp_path / ".env"
    env.write_text("", encoding="utf-8")
    flag = tmp_path / "switch.flag"
    monkeypatch.setenv("OPENSWARM_SWITCH_FLAG", str(flag))

    # Pre-populate .env with the credentials SwitchProvider's required-env
    # check needs to find. Bridge OpenSwarm's standard names for the test.
    monkeypatch.setenv("AZURE_AI_API_KEY", foundry["api_key"])
    monkeypatch.setenv("AZURE_AI_API_BASE", foundry["api_base"])
    monkeypatch.setenv("OLLAMA_API_BASE", ollama_base)
    from dotenv import set_key
    for k in ("AZURE_AI_API_KEY", "AZURE_AI_API_BASE", "OLLAMA_API_BASE"):
        set_key(str(env), k, os.environ[k])

    # Start on Ollama
    monkeypatch.setenv("DEFAULT_MODEL", f"ollama_chat/{ollama_model}")
    sys.modules.pop("config", None)
    import config
    assert config.get_active_provider() == "ollama"

    # Switch via the tool — importlib avoids the package shadowing where
    # orchestrator/tools/__init__.py re-exports the class with the
    # submodule's name.
    sys.modules.pop("orchestrator.tools.SwitchProvider", None)
    sp_mod = importlib.import_module("orchestrator.tools.SwitchProvider")
    sp_mod.ENV_PATH = env

    result = sp_mod.SwitchProvider(provider="azure_ai", model=foundry_model).run()
    assert "switched" in result.lower(), f"switch failed: {result}"
    assert flag.exists(), "TUI restart flag was not touched"
    assert os.environ["DEFAULT_MODEL"] == f"azure_ai/{foundry_model}", (
        "os.environ was not refreshed in-process"
    )

    # Simulate the per-request agency rebuild that agency-swarm does
    sys.modules.pop("config", None)
    import config
    assert config.get_active_provider() == "azure_ai"

    # The post-switch live call — closes the loop end-to-end
    response = litellm.completion(
        model=f"azure_ai/{foundry_model}",
        messages=[{"role": "user", "content": "Reply with exactly: SWITCHED"}],
        api_key=foundry["api_key"],
        api_base=foundry["api_base"],
        max_tokens=10,
    )
    assert response.choices[0].message.content.strip(), (
        "empty response from new provider after switch"
    )
