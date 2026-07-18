from agency_swarm.tools import BaseTool
from pydantic import Field

from helpers import execute_composio_tool


class ManageConnections(BaseTool):
    """
    Check and manage Composio app connections for the current user.

    Use this first when a task needs an external system (Gmail, Slack, Notion, etc.).
    """

    toolkits: list[str] = Field(
        default=[],
        description=(
            "Optional list of toolkits to check/connect (e.g., ['gmail', 'slack', 'notion']). "
            "If omitted, Composio decides based on context."
        ),
    )
    reinitiate_all: bool = Field(
        default=False,
        description="If true, force reconnection for the specified toolkits.",
    )
    session_id: str | None = Field(
        default=None,
        description="Optional session id from a previous SearchTools response.",
    )

    def run(self):
        arguments: dict = {}
        if self.toolkits:
            arguments["toolkits"] = self.toolkits
        if self.reinitiate_all:
            arguments["reinitiate_all"] = self.reinitiate_all
        result = execute_composio_tool(
            tool_name="COMPOSIO_MANAGE_CONNECTIONS",
            arguments=arguments,
            session_id=self.session_id,
        )
        return str(result)
