import inspect
import os
from typing import Any

from composio import Composio
from composio_openai_agents import OpenAIAgentsProvider

from run_utils import _load_openswarm_dotenv

_load_openswarm_dotenv()

_composio_clients: dict[str, Composio] = {}

# Meta tools (COMPOSIO_*) require a Tool Router session.  Keep the session ID
# explicit at the tool boundary so callers can continue the same workflow
# across separate Agency Swarm tool calls.
_META_TOOL_PREFIX = "COMPOSIO_"


def _refresh_runtime_env() -> None:
    """Reload add-on keys written through the TUI into the running process."""
    _load_openswarm_dotenv(override=True)


def get_composio_user_id() -> str | None:
    _refresh_runtime_env()
    for key in ("COMPOSIO_USER_ID", "USER_ID"):
        value = os.getenv(key)
        if value:
            return str(value)
    return None


def get_composio_client() -> Composio | None:
    _refresh_runtime_env()
    api_key = os.getenv("COMPOSIO_API_KEY")
    if not api_key:
        return None
    if api_key in _composio_clients:
        return _composio_clients[api_key]
    client = Composio(provider=OpenAIAgentsProvider())
    _composio_clients[api_key] = client
    return client


def get_composio_session(session_id: str | None = None) -> Any | dict:
    """Create a Composio session or resume the supplied session."""
    composio = get_composio_client()
    user_id = get_composio_user_id()
    if not composio:
        return {"error": "COMPOSIO_API_KEY is not set."}
    if not user_id:
        return {"error": "COMPOSIO_USER_ID is not set."}

    try:
        if session_id:
            return composio.use(session_id)
        return composio.create(user_id=user_id)
    except AttributeError:
        return {
            "error": (
                "Composio sessions require composio>=0.13.0. "
                "Install the version pinned in requirements.txt."
            )
        }
    except Exception as exc:
        return {"error": f"Unable to create or resume the Composio session: {exc}"}


def execute_composio_session_tool(
    tool_name: str,
    arguments: dict,
    session_id: str | None = None,
):
    """Execute a Composio meta or app tool inside one Tool Router session."""
    session = get_composio_session(session_id)
    if isinstance(session, dict) and session.get("error"):
        return session

    try:
        result = session.execute(tool_name, arguments=arguments)
        return {"session_id": session.session_id, "result": result}
    except Exception as exc:
        return {"error": f"Composio session tool execution failed: {exc}"}


def execute_composio_tool(
    tool_name: str,
    arguments: dict,
    session_id: str | None = None,
):
    """Execute a Composio tool, using a session when one is required."""
    if session_id or tool_name.startswith(_META_TOOL_PREFIX):
        return execute_composio_session_tool(tool_name, arguments, session_id)

    composio = get_composio_client()
    user_id = get_composio_user_id()
    if not composio:
        return {"error": "COMPOSIO_API_KEY is not set."}
    if not user_id:
        return {"error": "COMPOSIO_USER_ID is not set."}

    kwargs = {"user_id": user_id, "arguments": arguments}
    # composio>=0.9.0 checks tool versions on execute; skip it when supported.
    # Older releases (0.8.x) have no such check and reject the keyword.
    try:
        parameters = inspect.signature(composio.tools.execute).parameters
    except (TypeError, ValueError):
        parameters = {}
    if "dangerously_skip_version_check" in parameters:
        kwargs["dangerously_skip_version_check"] = True

    return composio.tools.execute(tool_name, **kwargs)


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
