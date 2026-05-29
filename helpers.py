import os

from composio import Composio
from composio_openai_agents import OpenAIAgentsProvider

from run_utils import _load_openswarm_dotenv

_load_openswarm_dotenv()

_composio_clients: dict[str, Composio] = {}


def get_composio_user_id() -> str | None:
    for key in ("COMPOSIO_USER_ID", "USER_ID"):
        value = os.getenv(key)
        if value:
            return str(value)
    return None


def get_composio_client() -> Composio | None:
    api_key = os.getenv("COMPOSIO_API_KEY")
    if not api_key:
        return None
    if api_key in _composio_clients:
        return _composio_clients[api_key]
    client = Composio(provider=OpenAIAgentsProvider())
    _composio_clients[api_key] = client
    return client


def execute_composio_tool(tool_name: str, arguments: dict):
    composio = get_composio_client()
    user_id = get_composio_user_id()
    if not composio:
        return {"error": "COMPOSIO_API_KEY is not set."}
    if not user_id:
        return {"error": "COMPOSIO_USER_ID is not set."}

    return composio.tools.execute(
        tool_name,
        user_id=user_id,
        arguments=arguments,
        dangerously_skip_version_check=True,
    )


def get_composio_tools(**kwargs):
    composio = get_composio_client()
    user_id = get_composio_user_id()
    if not composio:
        return {"error": "COMPOSIO_API_KEY is not set."}
    if not user_id:
        return {"error": "COMPOSIO_USER_ID is not set."}

    return composio.tools.get(user_id, **kwargs)


user_id = get_composio_user_id()
composio = get_composio_client()
