"""config.py — model resolution and provider classification."""

import pytest

import config


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for var in (
        "DEFAULT_MODEL",
        "OPENAI_COMPAT_API_KEY", "OPENAI_COMPAT_API_BASE",
    ):
        monkeypatch.delenv(var, raising=False)


def test_provider_registry_has_seven_slugs():
    assert set(config.PROVIDER_REGISTRY) == {
        "openai", "anthropic", "google",
        "azure", "azure_ai", "ollama", "openai_compat",
    }


@pytest.mark.parametrize(
    "model,expected_slug",
    [
        ("gpt-5.2",                                  "openai"),
        ("o3",                                       "openai"),
        ("litellm/claude-sonnet-4-6",                "anthropic"),
        ("litellm/gemini/gemini-3-flash",            "google"),
        ("azure/my-deployment",                       "azure"),
        # azure_ai/ must match before azure/ would (longest prefix wins).
        ("azure_ai/claude-opus-4-1",                 "azure_ai"),
        ("ollama_chat/llama3.1",                     "ollama"),
        ("openai_compat/qwen3-coder:480b-cloud",     "openai_compat"),
    ],
)
def test_get_active_provider_classifies_all_prefixes(model, expected_slug, monkeypatch):
    monkeypatch.setenv("DEFAULT_MODEL", model)
    assert config.get_active_provider() == expected_slug


def test_resolve_openai_compat_unwraps_correctly(monkeypatch):
    monkeypatch.setenv("OPENAI_COMPAT_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_COMPAT_API_BASE", "https://api.groq.com/openai/v1")
    monkeypatch.setenv("DEFAULT_MODEL", "openai_compat/llama-3.3-70b-versatile")

    result = config.get_default_model()
    # The conftest stub records constructor kwargs as attributes.
    assert result.model == "openai/llama-3.3-70b-versatile"
    assert result.api_key == "sk-test"
    assert result.base_url == "https://api.groq.com/openai/v1"


def test_resolve_openai_compat_raises_on_missing_base(monkeypatch):
    """Better to fail loudly at startup than give a cryptic LiteLLM error
    on the first model call."""
    monkeypatch.setenv("OPENAI_COMPAT_API_KEY", "sk-test")
    monkeypatch.delenv("OPENAI_COMPAT_API_BASE", raising=False)
    monkeypatch.setenv("DEFAULT_MODEL", "openai_compat/foo")

    with pytest.raises(RuntimeError, match="OPENAI_COMPAT_API_BASE"):
        config.get_default_model()


def test_bare_openai_model_passes_through_unchanged(monkeypatch):
    monkeypatch.setenv("DEFAULT_MODEL", "gpt-5.2")
    assert config.get_default_model() == "gpt-5.2"


def test_is_openai_provider_only_true_for_bare_models(monkeypatch):
    monkeypatch.setenv("DEFAULT_MODEL", "gpt-5.2")
    assert config.is_openai_provider() is True

    monkeypatch.setenv("DEFAULT_MODEL", "azure/anything")
    assert config.is_openai_provider() is False

    monkeypatch.setenv("DEFAULT_MODEL", "openai_compat/anything")
    assert config.is_openai_provider() is False


def test_resolve_threads_ollama_api_base(monkeypatch):
    """Ollama users who set OLLAMA_API_BASE in .env expect the URL to
    actually be used. Don't rely on LiteLLM's env-var fallback —
    pass it explicitly."""
    monkeypatch.setenv("DEFAULT_MODEL", "ollama_chat/llama3.1")
    monkeypatch.setenv("OLLAMA_API_BASE", "http://my-ollama-server:11434")
    result = config.get_default_model()
    assert result.model == "ollama_chat/llama3.1"
    assert result.base_url == "http://my-ollama-server:11434"


def test_resolve_typeerror_propagates(monkeypatch):
    """A misconfigured kwarg in LitellmModel construction should surface
    immediately, not silently degrade to a bare string."""
    import sys

    class _BrokenLitellmModel:
        def __init__(self, *args, **kwargs):
            raise TypeError("unsupported kwarg in LitellmModel signature")

    monkeypatch.setattr(sys.modules["agency_swarm"], "LitellmModel", _BrokenLitellmModel)
    monkeypatch.setenv("DEFAULT_MODEL", "litellm/claude-sonnet-4-6")

    with pytest.raises(TypeError, match="unsupported kwarg"):
        config.get_default_model()


def test_resolve_importerror_degrades_gracefully(monkeypatch):
    """When agency-swarm is genuinely missing, _resolve should return the
    original model string rather than crash. (Different from TypeError,
    which signals a programming error and must propagate.)"""
    import sys

    saved = sys.modules.pop("agency_swarm", None)
    try:
        # Block re-import attempts within this test
        monkeypatch.setitem(sys.modules, "agency_swarm", None)
        monkeypatch.setenv("DEFAULT_MODEL", "litellm/claude-sonnet-4-6")
        result = config.get_default_model()
        # ImportError swallowed; we get the original model string back
        # (unwrapped via the litellm/ strip the function does upstream).
        assert result == "litellm/claude-sonnet-4-6"
    finally:
        if saved is not None:
            sys.modules["agency_swarm"] = saved


def test_get_active_provider_unknown_for_unrecognized_litellm_models(monkeypatch):
    """A user with a custom litellm/<vendor>/<model> string should get
    'unknown' rather than the misleading 'litellm' slug that isn't in
    the registry."""
    monkeypatch.setenv("DEFAULT_MODEL", "litellm/cohere/command-r-plus")
    assert config.get_active_provider() == "unknown"
