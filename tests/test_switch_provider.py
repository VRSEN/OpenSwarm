"""SwitchProvider — the runtime provider switch tool."""

import importlib
import os
from pathlib import Path

import pytest
from dotenv import dotenv_values
from pydantic import ValidationError

# Import the module explicitly to avoid the shadowing in
# orchestrator/tools/__init__.py, which re-exports the SwitchProvider
# *class* under the same dotted path as the submodule.
sp_module = importlib.import_module("orchestrator.tools.SwitchProvider")
SwitchProvider = sp_module.SwitchProvider


@pytest.fixture
def env_path(tmp_path, monkeypatch):
    """Redirect the module-level ENV_PATH to a temp file."""
    env = tmp_path / ".env"
    env.write_text("", encoding="utf-8")
    monkeypatch.setattr(sp_module, "ENV_PATH", env)
    return env


@pytest.fixture
def flag_path(tmp_path, monkeypatch):
    """Wire the restart flag to a temp path the test can inspect."""
    flag = tmp_path / "switch.flag"
    monkeypatch.setenv("OPENSWARM_SWITCH_FLAG", str(flag))
    return flag


@pytest.fixture(autouse=True)
def clear_provider_env(monkeypatch):
    """Strip provider keys from the test process so tests start clean."""
    for var in (
        "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY",
        "AZURE_API_KEY", "AZURE_API_BASE", "AZURE_API_VERSION",
        "AZURE_AI_API_KEY", "AZURE_AI_API_BASE",
        "OPENAI_COMPAT_API_KEY", "OPENAI_COMPAT_API_BASE",
        "OLLAMA_API_BASE",
    ):
        monkeypatch.delenv(var, raising=False)


def test_unknown_provider_returns_supported_list(env_path, flag_path):
    result = SwitchProvider(provider="bedrock", model="nova-pro").run()
    assert "Unknown provider" in result
    assert "openai_compat" in result  # the registry's full vocabulary surfaces


def test_empty_model_rejected_by_pydantic(env_path):
    # min_length=1 on the Field ensures the validation error surfaces
    # before run() executes — no .env mutation can happen.
    with pytest.raises(ValidationError):
        SwitchProvider(provider="openai", model="")


def test_model_field_blocks_newline_injection(env_path, flag_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    result = SwitchProvider(provider="openai", model="x\nMALICIOUS=1").run()
    assert "Invalid model" in result
    # .env must not have been written
    assert dotenv_values(str(env_path)).get("DEFAULT_MODEL") in (None, "")


def test_openai_compat_rejects_http_url(env_path, flag_path, monkeypatch):
    monkeypatch.setenv("OPENAI_COMPAT_API_KEY", "sk-evil")
    monkeypatch.setenv("OPENAI_COMPAT_API_BASE", "http://attacker.example.com/v1")
    result = SwitchProvider(
        provider="openai_compat", model="qwen3-coder:480b-cloud"
    ).run()
    assert "must use https" in result
    # .env must not have been written
    assert dotenv_values(str(env_path)).get("DEFAULT_MODEL") in (None, "")


def test_openai_compat_rejects_no_hostname(env_path, flag_path, monkeypatch):
    monkeypatch.setenv("OPENAI_COMPAT_API_KEY", "sk")
    monkeypatch.setenv("OPENAI_COMPAT_API_BASE", "https:///")
    result = SwitchProvider(
        provider="openai_compat", model="qwen3-coder"
    ).run()
    assert "no hostname" in result.lower()


def test_missing_credentials_surfaces_env_var_names(env_path, flag_path):
    result = SwitchProvider(provider="azure", model="my-deployment").run()
    assert "missing credentials" in result
    # All three Azure vars should be named so the user knows what to set.
    for var in ("AZURE_API_KEY", "AZURE_API_BASE", "AZURE_API_VERSION"):
        assert var in result


def test_successful_switch_writes_env_and_touches_flag(
    env_path, flag_path, monkeypatch
):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    result = SwitchProvider(provider="openai", model="gpt-5.2").run()
    assert "switched" in result.lower()
    assert flag_path.exists()
    # dotenv_values strips quotes — round-trip should preserve the slash form.
    assert dotenv_values(str(env_path)).get("DEFAULT_MODEL") == "gpt-5.2"


def test_openai_compat_writes_correct_default_model(
    env_path, flag_path, monkeypatch
):
    monkeypatch.setenv("OPENAI_COMPAT_API_KEY", "sk")
    monkeypatch.setenv("OPENAI_COMPAT_API_BASE", "https://api.groq.com/openai/v1")
    result = SwitchProvider(
        provider="openai_compat", model="llama-3.3-70b-versatile"
    ).run()
    assert "switched" in result.lower()
    assert dotenv_values(str(env_path)).get("DEFAULT_MODEL") == (
        "openai_compat/llama-3.3-70b-versatile"
    )


def test_atomic_write_leaves_no_tmp_file(env_path, flag_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    SwitchProvider(provider="openai", model="gpt-5.2").run()
    tmp = env_path.with_suffix(env_path.suffix + ".tmp")
    assert not tmp.exists(), ".env.tmp left over after atomic write"


def test_no_flag_env_var_refuses_switch(env_path, monkeypatch):
    """When OPENSWARM_SWITCH_FLAG isn't set the tool must refuse outright,
    not write .env and pretend it succeeded — flag is touched BEFORE the
    .env mutation by design."""
    monkeypatch.delenv("OPENSWARM_SWITCH_FLAG", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    result = SwitchProvider(provider="openai", model="gpt-5.2").run()
    assert "Cannot switch" in result
    # .env must NOT have been mutated — the new ordering enforces this.
    assert dotenv_values(str(env_path)).get("DEFAULT_MODEL") in (None, "")


def test_oserror_on_flag_touch_aborts_switch(env_path, flag_path, monkeypatch):
    """If the flag can't be written (disk full, permissions), the tool
    must refuse before touching .env."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    def boom(self):
        raise OSError("simulated disk full")

    monkeypatch.setattr(Path, "touch", boom)
    result = SwitchProvider(provider="openai", model="gpt-5.2").run()
    assert "Refusing switch" in result
    assert "disk full" in result
    # .env must NOT have been mutated.
    assert dotenv_values(str(env_path)).get("DEFAULT_MODEL") in (None, "")


def test_atomic_write_recovers_when_set_key_fails(env_path, flag_path, monkeypatch):
    """If set_key blows up mid-write, the original .env stays intact and
    no .env.tmp is left over."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    env_path.write_text("EXISTING_KEY=preserved\n", encoding="utf-8")

    def boom(*a, **kw):
        raise RuntimeError("simulated set_key failure")

    monkeypatch.setattr(sp_module, "set_key", boom)

    with pytest.raises(RuntimeError, match="simulated set_key failure"):
        SwitchProvider(provider="openai", model="gpt-5.2").run()

    # Original .env unchanged
    contents = env_path.read_text(encoding="utf-8")
    assert "EXISTING_KEY=preserved" in contents
    # No .env.tmp leftover
    assert not env_path.with_suffix(env_path.suffix + ".tmp").exists()


def test_openai_compat_works_without_api_key(env_path, flag_path, monkeypatch):
    """Local vLLM and some OpenRouter setups are keyless — the registry
    only requires OPENAI_COMPAT_API_BASE, not the key."""
    monkeypatch.delenv("OPENAI_COMPAT_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_COMPAT_API_BASE", "https://my-vllm.local/v1")
    result = SwitchProvider(provider="openai_compat", model="qwen3-coder").run()
    assert "switched" in result.lower()
    assert dotenv_values(str(env_path)).get("DEFAULT_MODEL") == (
        "openai_compat/qwen3-coder"
    )


def test_dotenv_round_trip_preserves_slash_models(env_path, flag_path, monkeypatch):
    """python-dotenv quotes some values when writing — verify load_dotenv
    and dotenv_values both unquote consistently. A regression here would
    silently break the credential check on the next switch."""
    from dotenv import load_dotenv

    monkeypatch.setenv("OPENAI_COMPAT_API_KEY", "sk")
    monkeypatch.setenv("OPENAI_COMPAT_API_BASE", "https://api.groq.com/openai/v1")
    SwitchProvider(
        provider="openai_compat", model="qwen3-coder:480b-cloud"
    ).run()

    # Both readers should return the unquoted form.
    via_values = dotenv_values(str(env_path))["DEFAULT_MODEL"]
    monkeypatch.delenv("DEFAULT_MODEL", raising=False)
    load_dotenv(str(env_path), override=True)
    via_loadenv = os.environ["DEFAULT_MODEL"]

    assert via_values == via_loadenv == "openai_compat/qwen3-coder:480b-cloud"
