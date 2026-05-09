from openai import OpenAI


def get_caller_openai_credentials(tool) -> tuple[str, str] | None:
    ctx = getattr(tool, "_context", None)
    master = getattr(ctx, "context", None)
    agent_name = getattr(master, "current_agent_name", None)
    agents = getattr(master, "agents", {})
    agent = agents.get(agent_name) if agent_name else None
    model = getattr(agent, "model", None)
    for attr in ("_client", "openai_client", "client"):
        maybe = getattr(model, attr, None)
        api_key = getattr(maybe, "api_key", None)
        base_url = getattr(maybe, "base_url", None)
        if api_key and base_url:
            return api_key, str(base_url)
    return None


def get_openai_client(tool=None) -> OpenAI:
    if tool is not None:
        creds = get_caller_openai_credentials(tool)
        if creds:
            return OpenAI(api_key=creds[0], base_url=creds[1])
    import os
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is required")
    base_url = os.getenv("OPENAI_BASE_URL")
    if base_url:
        return OpenAI(api_key=api_key, base_url=base_url)
    return OpenAI(api_key=api_key)
