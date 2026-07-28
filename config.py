"""Shared model configuration helpers — read by all agents at startup."""
import os


_ATLAS_CLOUD_PREFIX = "atlascloud/"
_ATLAS_CLOUD_BASE_URL = "https://api.atlascloud.ai/v1"


def get_default_model(fallback: str = "gpt-5.4"):
    """Return the configured default model for standard agents."""
    model = os.getenv("DEFAULT_MODEL", fallback)
    return _resolve(model)


def is_openai_provider() -> bool:
    """Return True when the configured provider is OpenAI (not LiteLLM).

    OpenAI model IDs never contain a slash (e.g. 'gpt-5.4', 'o3').
    Any provider-prefixed model, including Atlas Cloud and LiteLLM routes,
    must not receive Responses API-only reasoning or web-search settings.
    """
    return "/" not in os.getenv("DEFAULT_MODEL", "")


def _resolve(model: str):
    """Resolve Atlas Cloud and LiteLLM provider-prefixed model strings."""
    if model.startswith(_ATLAS_CLOUD_PREFIX):
        model_id = model[len(_ATLAS_CLOUD_PREFIX) :]
        if not model_id:
            raise ValueError("Atlas Cloud model ID is required after 'atlascloud/'")
        api_key = os.getenv("ATLASCLOUD_API_KEY")
        if not api_key:
            raise RuntimeError("ATLASCLOUD_API_KEY environment variable is required")

        from agents import OpenAIChatCompletionsModel
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=api_key, base_url=_ATLAS_CLOUD_BASE_URL)
        return OpenAIChatCompletionsModel(model=model_id, openai_client=client)

    if "/" not in model:
        return model
    bare = model[len("litellm/"):] if model.startswith("litellm/") else model
    try:
        from agency_swarm import LitellmModel  # noqa: PLC0415
        return LitellmModel(model=bare)
    except ImportError:
        return model
