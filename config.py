"""Shared model configuration helpers — read by all agents at startup."""
import os


def get_default_model(fallback: str = "gpt-5.2"):
    """Return the configured default model for standard agents."""
    model = os.getenv("DEFAULT_MODEL", fallback)
    return _resolve(model)


def is_openai_provider() -> bool:
    """Return True only for plain OpenAI usage (no custom base, no LiteLLM).

    Returns False when:
      - OPENAI_BASE_URL is set (a local router/proxy is in front of us, e.g.
        a Claude-subscription router, which won't accept OpenAI-only options
        like reasoning summaries).
      - DEFAULT_MODEL contains a slash (LiteLLM-routed).
      - DEFAULT_MODEL is a bare claude-* / gemini-* name (auto-routed via
        LiteLLM by _resolve below).
    """
    if os.getenv("OPENAI_BASE_URL"):
        return False
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
      - OPENAI_BASE_URL set (router mode) → return string as-is so the
        OpenAI client hits the router, regardless of model-name shape.
      - 'litellm/<provider>/<model>'  → LiteLLM with provider/model
      - 'litellm/<bare-model>'        → LiteLLM, provider inferred from name
      - '<provider>/<model>'          → LiteLLM as-is
      - bare claude-* / gemini-*      → LiteLLM with inferred provider
      - everything else (e.g. 'gpt-5.2', 'o3') → returned unchanged for OpenAI
    """
    # Router mode: OpenAI-compatible local proxy handles all calls.
    if os.getenv("OPENAI_BASE_URL"):
        if model.startswith("litellm/"):
            model = model[len("litellm/"):]
        return model

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
