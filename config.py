"""Shared model configuration helpers — read by all agents at startup."""
import os


def get_default_model(fallback: str = "gpt-5.2"):
    """Return the configured default model for standard agents."""
    model = os.getenv("DEFAULT_MODEL", fallback)
    return _resolve(model)


def is_router_mode() -> bool:
    """True when a local OpenAI-compatible router is in front of us."""
    return bool(os.getenv("OPENAI_BASE_URL"))


def is_oauth_mode() -> bool:
    """True when we should route through the local `claude` CLI via
    claude_agent_sdk (Claude Pro/Max/Claude Code subscription).

    Triggers in priority order:
      1. CLAUDE_USE_AGENT_SDK=1 explicitly.
      2. ANTHROPIC_BASE_URL set (legacy router compat).
      3. CLAUDE_CODE_OAUTH_TOKEN set or ANTHROPIC_API_KEY starts with
         sk-ant-oat (legacy aliases).
      4. claude-agent-sdk is installed AND DEFAULT_MODEL looks like a
         Claude id and no other backend is configured — auto-detect
         path so the default workflow "just works" for users with the
         claude CLI logged in.
    """
    if os.getenv("CLAUDE_USE_AGENT_SDK", "").lower() in ("1", "true", "yes"):
        return True
    if os.getenv("ANTHROPIC_BASE_URL"):
        return True
    if os.getenv("CLAUDE_CODE_OAUTH_TOKEN"):
        return True
    key = os.getenv("ANTHROPIC_API_KEY", "")
    if key.startswith("sk-ant-oat"):
        return True

    # Auto-detect: if the user has claude_agent_sdk installed AND has
    # asked for a Claude model AND has not configured any other
    # backend, default to the SDK path.
    if os.getenv("OPENAI_BASE_URL"):
        return False
    if key:  # explicit ANTHROPIC_API_KEY → use direct Anthropic
        return False
    raw = os.getenv("DEFAULT_MODEL", "")
    if not raw.lower().startswith(("claude", "cc/")):
        return False
    try:
        import claude_agent_sdk  # noqa: F401, PLC0415
        return True
    except ImportError:
        return False


def is_openai_provider() -> bool:
    """Return True only for plain OpenAI usage (no custom base, no LiteLLM,
    no OAuth path).
    """
    if os.getenv("OPENAI_BASE_URL"):
        return False
    if is_oauth_mode():
        return False
    raw = os.getenv("DEFAULT_MODEL", "")
    if "/" in raw:
        return False
    lowered = raw.lower()
    if lowered.startswith(("claude", "gemini")):
        return False
    return True


def filter_hosted_tools(tools: list) -> list:
    """Drop OpenAI-hosted tools (WebSearchTool, FileSearchTool, etc.) when
    the model is reached via Chat Completions — hosted tools only run on
    the Responses API and against api.openai.com.

    In router mode we use Chat Completions, so a hosted tool would raise
    'Hosted tools are not supported with the ChatCompletions API'.
    """
    if not (is_router_mode() or is_oauth_mode()):
        return tools
    try:
        from agents.tool import (  # noqa: PLC0415
            WebSearchTool,
            FileSearchTool,
            HostedMCPTool,
            ImageGenerationTool,
            CodeInterpreterTool,
            ComputerTool,
        )
        hosted_types = (
            WebSearchTool,
            FileSearchTool,
            HostedMCPTool,
            ImageGenerationTool,
            CodeInterpreterTool,
            ComputerTool,
        )
    except ImportError:
        return tools
    return [t for t in tools if not isinstance(t, hosted_types)]


def _infer_provider_prefix(model: str) -> str:
    """Map a bare model name to the LiteLLM provider it belongs to."""
    lowered = model.lower()
    if lowered.startswith("claude"):
        return f"anthropic/{model}"
    if lowered.startswith("gemini"):
        return f"gemini/{model}"
    return model


def _resolve(model: str):
    """Route 'provider/model' strings through the right backend.

    Precedence:
      1. CLAUDE_CODE_OAUTH_TOKEN (or sk-ant-oat... in ANTHROPIC_API_KEY)
         → ClaudeOAuthModel: direct Anthropic Messages API + Bearer +
         oauth-2025-04-20 beta header. Subscription billing.
      2. OPENAI_BASE_URL set → wrap in OpenAIChatCompletionsModel bound
         to a router-aware AsyncOpenAI client.
      3. 'litellm/...' or '<provider>/<model>' / bare claude-* / gemini-*
         → LiteLLM via LitellmModel.
      4. Everything else (gpt-5.2, o3, ...) → returned unchanged for OpenAI.
    """
    # OAuth mode: route through the local `claude` CLI via
    # claude_agent_sdk so we use the user's subscription auth.
    # Strip 'cc/' / 'litellm/anthropic/' prefixes — the SDK wants the
    # bare Anthropic model id.
    if is_oauth_mode():
        bare = model
        for prefix in ("litellm/", "anthropic/", "cc/"):
            if bare.startswith(prefix):
                bare = bare[len(prefix):]
        try:
            from claude_oauth_model import ClaudeAgentSDKModel  # noqa: PLC0415
            return ClaudeAgentSDKModel(model=bare)
        except ImportError:
            return bare

    # Router mode: OpenAI-compatible local proxy handles all calls.
    # Use Chat Completions (not Responses) — its response shape is universally
    # implemented by routers/proxies, while Responses-API output-items often
    # come back as None and trip SDK validation.
    if os.getenv("OPENAI_BASE_URL"):
        if model.startswith("litellm/"):
            model = model[len("litellm/"):]
        try:
            from agents import OpenAIChatCompletionsModel  # noqa: PLC0415
            from openai import AsyncOpenAI  # noqa: PLC0415
            client = AsyncOpenAI()  # reads OPENAI_BASE_URL + OPENAI_API_KEY
            return OpenAIChatCompletionsModel(model=model, openai_client=client)
        except ImportError:
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
