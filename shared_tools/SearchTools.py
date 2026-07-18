from agency_swarm.tools import BaseTool
from pydantic import Field

from helpers import execute_composio_tool


class SearchTools(BaseTool):
    """
    Search Composio tools for a task and return recommended tools + schemas.

    Use this when you need to discover tools for a new external workflow.
    """

    queries: list[dict] = Field(
        ...,
        description=(
            "List of query objects for COMPOSIO_SEARCH_TOOLS. "
            "Each item should usually include at least a 'use_case' key."
        ),
    )
    session_id: str | None = Field(
        default=None,
        description="Composio session id returned by a previous Composio tool call.",
    )
    session: dict | None = Field(
        default=None,
        description=(
            "Deprecated compatibility field. Use session_id instead; if this contains "
            "{'id': '...'}, that id is used to resume the Composio session."
        ),
    )
    model: str | None = Field(
        default=None,
        description="Optional model hint to pass through to COMPOSIO_SEARCH_TOOLS.",
    )

    def run(self):
        arguments: dict = {"queries": self.queries}
        if self.model:
            arguments["model"] = self.model

        session_id = self.session_id
        if not session_id and self.session:
            candidate = self.session.get("id")
            if isinstance(candidate, str):
                session_id = candidate

        result = execute_composio_tool(
            tool_name="COMPOSIO_SEARCH_TOOLS",
            arguments=arguments,
            session_id=session_id,
        )
        return str(result)
