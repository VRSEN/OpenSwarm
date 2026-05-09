"""Switch the agency's LLM provider at runtime.

Writes DEFAULT_MODEL atomically to .env and signals run_utils.main() to
recreate the agency on the next TUI loop iteration. The user must exit the
TUI (`/quit` or Ctrl-C) for the switch to take effect — restart is automatic
from there.

Lives under orchestrator/tools/ rather than shared_tools/ because it
deliberately sits outside the orchestrator's "router only" contract — see
orchestrator/instructions.md for the documented carve-out. Specialist agents
should never have access to this tool.

NOTE: Provider switching only takes effect when running through
run_utils.main() (i.e. `python swarm.py` or the npm CLI). The FastAPI server
in server.py does not re-read DEFAULT_MODEL at runtime — switching from an
API client will appear to succeed but is a no-op for that surface.

Pre-existing provider credentials in .env are reused. To register new
credentials, run `python onboard.py`.
"""

import os
import re
import urllib.parse
from pathlib import Path

from agency_swarm.tools import BaseTool
from dotenv import dotenv_values, set_key
from pydantic import Field

from config import PROVIDER_REGISTRY

ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
SWITCH_FLAG_VAR = "OPENSWARM_SWITCH_FLAG"

# Allowlist for the user-supplied `model` field. Must start with a
# letter/digit (blocks `../...`, `.evil`, `/abs`); body allows the chars
# real model names use (dot, colon, dash, slash, underscore). Blocks
# newline injection into .env and shell metacharacters.
_SAFE_MODEL = re.compile(r"^[A-Za-z0-9][\w.:\-/]*$")


def _validate_openai_compat_base(url: str) -> str | None:
    """Return None when url is safe, else an error message.

    Defends against SSRF via attacker-controlled OPENAI_COMPAT_API_BASE: a
    prompt-injection chain that pre-positions the base URL would otherwise
    redirect all subsequent LLM traffic (with bearer tokens and conversation
    history) to an attacker server. Restrict to https:// with a real hostname.
    """
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        return "OPENAI_COMPAT_API_BASE is not a parseable URL."
    if parsed.scheme != "https":
        return f"OPENAI_COMPAT_API_BASE must use https:// (got '{parsed.scheme}://')."
    if not parsed.hostname:
        return "OPENAI_COMPAT_API_BASE has no hostname."
    return None


class SwitchProvider(BaseTool):
    """
    Switch the agency's LLM provider. Updates DEFAULT_MODEL in .env and signals
    the TUI loop to rebuild the agency on next restart.

    Use when the user says "switch to ollama", "use Azure", "use Claude",
    "switch provider", or types `/switch-provider`. Pre-existing credentials
    are reused. If credentials for the target provider are missing, returns a
    clear instruction to run `python onboard.py`.

    Provider slugs:
      - openai          OpenAI API (gpt-5.2, o3, etc.)
      - anthropic       Anthropic Claude via LiteLLM
      - google          Google Gemini via LiteLLM
      - azure           Azure OpenAI Service (your own gpt-* deployment)
      - azure_ai        Azure AI Foundry catalog (Claude on Azure, Llama,
                        Mistral, DeepSeek, ...)
      - ollama          Local Ollama server
      - openai_compat   Any OpenAI-compatible endpoint (Ollama Cloud, Groq,
                        Together AI, Mistral La Plateforme, OpenRouter, vLLM)
    """

    provider: str = Field(
        ...,
        description=(
            "Provider slug: openai, anthropic, google, azure, azure_ai, ollama, "
            "or openai_compat."
        ),
    )
    model: str = Field(
        ...,
        min_length=1,
        description=(
            "Model identifier. openai: 'gpt-5.2'. anthropic: 'claude-sonnet-4-6'. "
            "google: 'gemini-3-flash'. azure: deployment name. azure_ai: catalog "
            "model (e.g. 'claude-opus-4-1'). ollama: locally-pulled model "
            "(e.g. 'llama3.1'). openai_compat: vendor-advertised model id "
            "(e.g. 'qwen3-coder:480b-cloud')."
        ),
    )

    def run(self) -> str:
        slug = self.provider.strip().lower()
        if slug not in PROVIDER_REGISTRY:
            return (
                f"Unknown provider '{self.provider}'. Supported: "
                f"{', '.join(PROVIDER_REGISTRY)}."
            )

        # Defense against attacker-controlled model strings (path traversal,
        # newline injection, shell metacharacters).
        if not _SAFE_MODEL.match(self.model):
            return (
                f"Invalid model identifier '{self.model}'. Allowed characters: "
                "letters, digits, '.', ':', '-', '/', '_'."
            )

        prefix = PROVIDER_REGISTRY[slug]["prefix"]
        required_env = PROVIDER_REGISTRY[slug]["required_env"]

        # Read .env once; merge with process env so users who export keys
        # in the shell aren't forced to write them to disk first.
        on_disk = dotenv_values(str(ENV_PATH)) if ENV_PATH.exists() else {}
        merged = {**on_disk, **{k: os.environ[k] for k in required_env if os.environ.get(k)}}
        missing = [k for k in required_env if not merged.get(k)]
        if missing:
            return (
                f"Cannot switch to {slug}: missing credentials {missing}.\n"
                "Run `python onboard.py` to register them, then retry."
            )

        if slug == "openai_compat":
            err = _validate_openai_compat_base(merged.get("OPENAI_COMPAT_API_BASE", ""))
            if err:
                return f"Refusing switch: {err}"

        new_default_model = f"{prefix}{self.model}"

        # Touch the restart flag BEFORE rewriting .env. Reasoning:
        #
        # If we wrote .env first and were killed between the write and the
        # flag touch, the user would see "Provider switched" (already
        # returned), .env would carry the new model, but the TUI loop in
        # run_utils.main() would never pick it up — silent half-state.
        #
        # Touching the flag first means: if .env write fails afterward, the
        # next loop iteration just re-reads the unchanged .env (one extra
        # restart, no harm). If .env write succeeds, the flag is already in
        # place. Order matters here.
        flag_path = os.environ.get(SWITCH_FLAG_VAR)
        if not flag_path:
            return (
                "Cannot switch — no restart signal available. This tool only "
                "works when running through the OpenSwarm TUI loop "
                "(`python swarm.py` or the npm CLI), not the FastAPI server."
            )
        try:
            Path(flag_path).touch()
        except OSError as exc:
            return f"Refusing switch: could not write restart flag ({exc})."

        # set_key on a temp copy + os.replace gives us atomic .env replacement
        # on POSIX, so a concurrent reader can't see a half-written file.
        # We deliberately rewrite the *whole* file via the temp rather than
        # set_key-ing the live .env, since python-dotenv's set_key is not
        # crash-safe on its own.
        if not ENV_PATH.exists():
            ENV_PATH.write_text("", encoding="utf-8")
        tmp_path = ENV_PATH.with_suffix(ENV_PATH.suffix + ".tmp")
        try:
            tmp_path.write_text(ENV_PATH.read_text(encoding="utf-8"), encoding="utf-8")
            set_key(str(tmp_path), "DEFAULT_MODEL", new_default_model)
            os.replace(str(tmp_path), str(ENV_PATH))
        finally:
            # Clean up the temp on the failure path; on success os.replace
            # already consumed it (Path.exists() returns False then).
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)

        return (
            f"Provider switched to {slug} (DEFAULT_MODEL={new_default_model}).\n"
            "Exit the TUI (`/quit` or Ctrl-C) and OpenSwarm will automatically "
            "restart with the new provider."
        )
