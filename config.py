"""Shared model configuration helpers — read by all agents at startup."""
import os


def get_default_model(fallback: str = "gpt-5.2"):
    """Return the configured default model for standard agents."""
    model = os.getenv("DEFAULT_MODEL", fallback)
    return _resolve(model)


def is_openai_provider() -> bool:
    """Return True when the configured provider is OpenAI (not LiteLLM).

    OpenAI model IDs never contain a slash (e.g. 'gpt-5.2', 'o3') and never
    start with a known non-OpenAI family prefix (claude*, gemini*).
    Any 'provider/model' string (e.g. 'anthropic/claude-sonnet-4-6',
    'litellm/gemini/gemini-3-flash') is treated as a LiteLLM-routed model.
    """
    raw = os.getenv("DEFAULT_MODEL", "")
    if "/" in raw:
        return False
    lowered = raw.lower()
    if lowered.startswith(("claude", "gemini")):
        return False
    return True


def _infer_provider_prefix(model: str) -> str:
    """Map a bare model name to the LiteLLM provider it belongs to."""
    lowered = model.lower()
    if lowered.startswith("claude"):
        return f"anthropic/{model}"
    if lowered.startswith("gemini"):
        return f"gemini/{model}"
    return model


def _resolve(model: str):
    """Route 'provider/model' strings through LitellmModel.

    Handles:
      - 'litellm/<provider>/<model>'  → LiteLLM with provider/model
      - 'litellm/<bare-model>'        → LiteLLM, provider inferred from name
      - '<provider>/<model>'          → LiteLLM as-is
      - bare claude-* / gemini-*      → LiteLLM with inferred provider
      - everything else (e.g. 'gpt-5.2', 'o3') → returned unchanged for OpenAI
    """
    # Strip optional 'litellm/' prefix.
    if model.startswith("litellm/"):
        model = model[len("litellm/"):]

    # If we still have no slash, infer provider from a known model-name prefix.
    if "/" not in model:
        inferred = _infer_provider_prefix(model)
        if inferred == model:
            # Plain OpenAI model name — return unchanged.
            return model
        model = inferred

    try:
        from agency_swarm import LitellmModel  # noqa: PLC0415
        return LitellmModel(model=model)
    except ImportError:
        return model
