"""Shared model configuration helpers — read by all agents at startup."""
import os

_ORCAROUTER_BASE_URL = "https://api.orcarouter.ai/v1"
_ORCAROUTER_PREFIX = "orcarouter/"


def get_default_model(fallback: str = "gpt-5.4"):
    """Return the configured default model for standard agents."""
    model = os.getenv("DEFAULT_MODEL", fallback)
    return _resolve(model)


def is_openai_provider() -> bool:
    """Return True when the configured provider is OpenAI (not LiteLLM).

    OpenAI model IDs never contain a slash (e.g. 'gpt-5.4', 'o3').
    Any 'provider/model' string (e.g. 'anthropic/claude-sonnet-4-6',
    'litellm/gemini/gemini-3-flash', 'orcarouter/gpt-5.6-luna') is
    treated as a LiteLLM-routed model.
    """
    return "/" not in os.getenv("DEFAULT_MODEL", "")


def is_orcarouter_provider() -> bool:
    """Return True when the configured provider is OrcaRouter."""
    return os.getenv("DEFAULT_MODEL", "").startswith(_ORCAROUTER_PREFIX)


def _resolve(model: str):
    """Route 'provider/model' strings through LitellmModel.

    Handles both explicit 'litellm/<model>' and bare 'provider/model' forms.
    OpenAI model IDs contain no slash, so they pass through unchanged.
    """
    if "/" not in model:
        return model
    if model.startswith(_ORCAROUTER_PREFIX):
        return _make_orcarouter_model(model[len(_ORCAROUTER_PREFIX):])
    bare = model[len("litellm/"):] if model.startswith("litellm/") else model
    try:
        from agency_swarm import LitellmModel  # noqa: PLC0415
        return LitellmModel(model=bare)
    except ImportError:
        return model


def _make_orcarouter_model(model: str):
    """Build a LiteLLM model pinned to the OrcaRouter gateway.

    OrcaRouter has its own credential namespace, so it is wired to the
    ORCAROUTER_API_KEY add-on instead of the OpenAI/Anthropic keys that
    LiteLLM would otherwise pick up from the environment.
    """
    try:
        from agency_swarm import LitellmModel  # noqa: PLC0415
        return LitellmModel(
            model=model,
            api_key=os.getenv("ORCAROUTER_API_KEY"),
            base_url=_ORCAROUTER_BASE_URL,
        )
    except ImportError:
        return f"{_ORCAROUTER_PREFIX}{model}"
