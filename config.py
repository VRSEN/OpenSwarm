"""Shared model configuration helpers — read by all agents at startup.

PROVIDER_REGISTRY is the single source of truth for provider routing. Every
new provider added to OpenSwarm should be registered here; the onboarding
wizard and the SwitchProvider tool both derive their behavior from this
table.
"""
import os

# Slug -> routing spec. Adding a new provider means adding one entry here
# and (optionally) a UI entry in onboard.PROVIDERS.
#   prefix:        DEFAULT_MODEL prefix that identifies this provider
#   required_env:  env vars that must be set before a model call works
PROVIDER_REGISTRY: dict[str, dict] = {
    "openai":        {"prefix": "",                "required_env": ["OPENAI_API_KEY"]},
    # Anthropic models on LiteLLM are always named claude-*; using a more
    # specific prefix here means a stray litellm/cohere/... model won't be
    # misclassified as anthropic.
    "anthropic":     {"prefix": "litellm/claude",  "required_env": ["ANTHROPIC_API_KEY"]},
    "google":        {"prefix": "litellm/gemini/", "required_env": ["GOOGLE_API_KEY"]},
    "azure":         {"prefix": "azure/",          "required_env": ["AZURE_API_KEY", "AZURE_API_BASE", "AZURE_API_VERSION"]},
    "azure_ai":      {"prefix": "azure_ai/",       "required_env": ["AZURE_AI_API_KEY", "AZURE_AI_API_BASE"]},
    "ollama":        {"prefix": "ollama_chat/",    "required_env": []},
    # Only the base URL is strictly required — keyless endpoints (local vLLM,
    # some OpenRouter / Mistral setups) are valid; LiteLLM passes None safely.
    "openai_compat": {"prefix": "openai_compat/",  "required_env": ["OPENAI_COMPAT_API_BASE"]},
}


def get_default_model(fallback: str = "gpt-5.2"):
    """Return the configured default model for standard agents."""
    model = os.getenv("DEFAULT_MODEL", fallback)
    return _resolve(model)


def is_openai_provider() -> bool:
    """True when DEFAULT_MODEL routes to OpenAI's hosted API directly.

    OpenAI model IDs never contain a slash (e.g. 'gpt-5.2', 'o3'). Any
    'provider/model' string is treated as a LiteLLM-routed model.
    """
    return "/" not in os.getenv("DEFAULT_MODEL", "")


def get_active_provider() -> str:
    """Slug derived from DEFAULT_MODEL by prefix table lookup.

    Returns one of the slugs in PROVIDER_REGISTRY. Bare 'litellm/<model>'
    strings that don't match anthropic (litellm/) or google (litellm/gemini/)
    return 'unknown' so callers can distinguish 'I know this provider' from
    'I don't recognize this'.
    """
    model = os.getenv("DEFAULT_MODEL", "")
    if "/" not in model:
        return "openai"
    # Longest prefix wins so 'azure_ai/' matches before 'azure/' would.
    for slug, spec in sorted(
        PROVIDER_REGISTRY.items(), key=lambda kv: -len(kv[1]["prefix"])
    ):
        prefix = spec["prefix"]
        if prefix and model.startswith(prefix):
            return slug
    return "unknown"


def _resolve(model: str):
    """Route 'provider/model' strings through LitellmModel.

    Bare strings (no slash) pass through for OpenAI's hosted API. Strings
    with a slash are wrapped in LitellmModel. The 'openai_compat/<model>'
    sentinel unwraps to LiteLLM's openai/<model> route with dedicated
    OPENAI_COMPAT_* credentials, so the user's real OPENAI_API_KEY is
    never overwritten.

    Raises RuntimeError if 'openai_compat/' is configured without
    OPENAI_COMPAT_API_BASE — better to fail loudly at startup than give
    a cryptic LiteLLM error on first call.
    """
    if "/" not in model:
        return model

    if model.startswith("openai_compat/"):
        real_model = "openai/" + model[len("openai_compat/"):]
        api_key = os.getenv("OPENAI_COMPAT_API_KEY")
        api_base = os.getenv("OPENAI_COMPAT_API_BASE")
        if not api_base:
            raise RuntimeError(
                "DEFAULT_MODEL uses openai_compat/ but OPENAI_COMPAT_API_BASE "
                "is not set. Run `python onboard.py` to configure it."
            )
        try:
            from agency_swarm import LitellmModel  # noqa: PLC0415
        except ImportError:
            return real_model
        return LitellmModel(model=real_model, api_key=api_key, base_url=api_base)

    bare = model[len("litellm/"):] if model.startswith("litellm/") else model
    try:
        from agency_swarm import LitellmModel  # noqa: PLC0415
    except ImportError:
        return model

    # Thread Ollama's base URL explicitly. LiteLLM also reads OLLAMA_API_BASE
    # from env, but passing it via base_url is unambiguous and consistent
    # with the openai_compat branch.
    if bare.startswith(("ollama/", "ollama_chat/")):
        return LitellmModel(model=bare, base_url=os.getenv("OLLAMA_API_BASE"))
    return LitellmModel(model=bare)
