"""Shared model configuration helpers — read by all agents at startup."""
import os


# MiniMax exposes matching OpenAI-compatible and Anthropic-compatible endpoints
# on both a global and a mainland-China region. Selecting a region swaps the
# whole endpoint set so the same model strings work from either location.
MINIMAX_ENDPOINTS = {
    "global": {
        "openai_base_url": "https://api.minimax.io/v1",
        "anthropic_base_url": "https://api.minimax.io/anthropic",
    },
    "cn": {
        "openai_base_url": "https://api.minimaxi.com/v1",
        "anthropic_base_url": "https://api.minimaxi.com/anthropic",
    },
}


def get_default_model(fallback: str = "gpt-5.4"):
    """Return the configured default model for standard agents."""
    model = os.getenv("DEFAULT_MODEL", fallback)
    return _resolve(model)


def is_openai_provider() -> bool:
    """Return True when the configured provider is OpenAI (not LiteLLM).

    OpenAI model IDs never contain a slash (e.g. 'gpt-5.4', 'o3').
    Any 'provider/model' string (e.g. 'anthropic/claude-sonnet-4-6',
    'litellm/gemini/gemini-3-flash', 'minimax/MiniMax-M3') is treated as a
    LiteLLM-routed model.
    """
    return "/" not in os.getenv("DEFAULT_MODEL", "")


def is_minimax_model(model: str) -> bool:
    """Return True when ``model`` targets a MiniMax model on either routing style.

    Covers the OpenAI-compatible form ('minimax/MiniMax-M3') and the
    Anthropic-compatible form ('anthropic/MiniMax-M3'), regardless of case.
    """
    return "minimax" in model.lower()


def minimax_region() -> str:
    """Return the selected MiniMax region ('global' or 'cn')."""
    region = os.getenv("MINIMAX_REGION", "global").strip().lower()
    return "cn" if region in {"cn", "cn_zh", "china"} else "global"


def minimax_base_url(model: str) -> str:
    """Return the MiniMax base URL for ``model`` in the configured region.

    Uses the Anthropic-compatible endpoint when the model is routed through the
    'anthropic/' provider, otherwise the OpenAI-compatible endpoint. Explicit
    ``MINIMAX_ANTHROPIC_BASE`` / ``MINIMAX_API_BASE`` overrides win when set.
    """
    endpoints = MINIMAX_ENDPOINTS[minimax_region()]
    if model.startswith("anthropic/"):
        return os.getenv("MINIMAX_ANTHROPIC_BASE") or endpoints["anthropic_base_url"]
    return os.getenv("MINIMAX_API_BASE") or endpoints["openai_base_url"]


def _minimax_kwargs(model: str) -> dict:
    """Build LitellmModel keyword arguments for a MiniMax model."""
    kwargs = {"api_base": minimax_base_url(model)}
    api_key = os.getenv("MINIMAX_API_KEY")
    if api_key:
        kwargs["api_key"] = api_key
    return kwargs


def _resolve(model: str):
    """Route 'provider/model' strings through LitellmModel.

    Handles both explicit 'litellm/<model>' and bare 'provider/model' forms.
    OpenAI model IDs contain no slash, so they pass through unchanged. MiniMax
    models additionally receive the region-selected base URL so both the
    OpenAI-compatible and Anthropic-compatible endpoints route correctly.
    """
    if "/" not in model:
        return model
    bare = model[len("litellm/"):] if model.startswith("litellm/") else model
    try:
        from agency_swarm import LitellmModel  # noqa: PLC0415
    except ImportError:
        return model
    if is_minimax_model(bare):
        return LitellmModel(model=bare, **_minimax_kwargs(bare))
    return LitellmModel(model=bare)
