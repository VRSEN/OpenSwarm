"""Model availability hints for tools that depend on provider add-ons."""

from __future__ import annotations

import os

from run_utils import _load_openswarm_dotenv

from shared_tools.openai_client_utils import get_caller_openai_credentials


def _refresh_runtime_env() -> None:
    """Reload add-on keys written through the TUI into the running process."""
    _load_openswarm_dotenv()


def _configured(value: bool) -> str:
    return "available" if value else "missing key / unavailable"


def direct_openai_available(tool=None) -> bool:
    """Return whether OpenAI media endpoints are usable for this tool call.

    Browser/Codex auth supplies an OpenAI-compatible client, but media endpoints
    such as Images and Videos are not supported through that base URL.
    """
    _refresh_runtime_env()
    creds = get_caller_openai_credentials(tool) if tool is not None else None
    if creds:
        return creds[1].startswith("https://api.openai.com")
    return bool(os.getenv("OPENAI_API_KEY"))


def google_available() -> bool:
    _refresh_runtime_env()
    return bool(os.getenv("GOOGLE_API_KEY"))


def fal_available() -> bool:
    _refresh_runtime_env()
    return bool(os.getenv("FAL_KEY"))


def image_model_availability_message(tool=None, *, failed_requirement: str | None = None) -> str:
    lines = []
    if failed_requirement:
        lines.append(f"{failed_requirement}")
    lines.extend(
        [
            "",
            "Available image models/providers in this environment:",
            f"- gemini-2.5-flash-image: {_configured(google_available())} (requires GOOGLE_API_KEY add-on)",
            f"- gemini-3-pro-image-preview: {_configured(google_available())} (requires GOOGLE_API_KEY add-on)",
            f"- gpt-image-1.5: {_configured(direct_openai_available(tool))} (requires OpenAI API key auth; not Codex browser auth)",
            f"- background removal / Pixelcut: {_configured(fal_available())} (requires FAL_KEY add-on)",
            "",
            "If the requested model is unavailable, switch to an available model above or ask the user to run /auth and add the missing add-on key.",
        ]
    )
    return "\n".join(lines)


def video_model_availability_message(tool=None, *, failed_requirement: str | None = None) -> str:
    lines = []
    if failed_requirement:
        lines.append(f"{failed_requirement}")
    lines.extend(
        [
            "",
            "Available video models/providers in this environment:",
            f"- veo-3.1-generate-preview: {_configured(google_available())} (requires GOOGLE_API_KEY add-on)",
            f"- veo-3.1-fast-generate-preview: {_configured(google_available())} (requires GOOGLE_API_KEY add-on)",
            f"- seedance-1.5-pro: {_configured(fal_available())} (requires FAL_KEY add-on)",
            f"- sora-2: {_configured(direct_openai_available(tool))} (requires OpenAI API key auth; not Codex browser auth)",
            f"- sora-2-pro: {_configured(direct_openai_available(tool))} (requires OpenAI API key auth; not Codex browser auth)",
            "",
            "If the requested model is unavailable, switch to an available model above or ask the user to run /auth and add the missing add-on key.",
        ]
    )
    return "\n".join(lines)
