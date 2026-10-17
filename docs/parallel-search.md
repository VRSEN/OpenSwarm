# Optional Parallel search for Deep Research

Give the Deep Research Agent web search and page fetching with
[Parallel Search MCP](https://docs.parallel.ai/integrations/mcp/search-mcp).
The anonymous endpoint is free for exploration and light use, with no Parallel
account or API key. Search uses Fast mode. OpenSwarm still needs its usual model
provider configuration.

This is a customization recipe for a working local checkout of OpenSwarm. It adds
tools to the existing agent; it keeps `WebSearchTool`, `ScholarSearch`, model
selection, and model settings in place. ScholarSearch still needs `SEARCH_API_KEY`.

## Connect the research agent

In [`deep_research/deep_research.py`](../deep_research/deep_research.py), add this
import:

```python
from agents.mcp import MCPServerStreamableHttp
from agency_swarm.tools import ToolFactory
```

At the start of `create_deep_research()`, before `return Agent(...)`, load and
rename the MCP tools:

```python
parallel_tools = ToolFactory.from_mcp([
    MCPServerStreamableHttp(
        name="Parallel Search",
        params={
            "url": "https://search.parallel.ai/mcp",
            "headers": {"User-Agent": "OpenSwarm/1.1.3 (+https://github.com/VRSEN/OpenSwarm)"},
            "timeout": 30,
        },
        cache_tools_list=True,
        client_session_timeout_seconds=60,
    ),
])
for tool in parallel_tools:
    tool.name = f"parallel_{tool.name}"
```

Then append `*parallel_tools` to the existing `tools` argument:

```python
tools=[WebSearchTool(), ScholarSearch, IPythonInterpreter, *parallel_tools],
```

The prefix matters: the existing `WebSearchTool` and Parallel both use the name
`web_search`. Agency Swarm skips duplicate names. Converting and renaming before
registration gives the agent `parallel_web_search` and `parallel_web_fetch` while
preserving its existing tools. The connection uses Streamable HTTP, with no
`mcp-remote` or authorization header. The SDK and `ToolFactory` are already
included in OpenSwarm's pinned Agency Swarm dependency.

In [`deep_research/instructions.md`](../deep_research/instructions.md), add this
bullet under **Conducting Research → Select the appropriate research tool**:

> - **Parallel Search**: When requested, use `parallel_web_search` for current web sources,
>   then `parallel_web_fetch` to read relevant URLs. Include source links in the report.
>   If the service returns a limit or connection error, report the limitation;
>   do not present the failed call as evidence.

## Check the connection

From the repository root, with your OpenSwarm Python environment activated, run
this after applying the customization. It loads the research agent and calls its
converted tools directly without a model request:

```bash
python - <<'PY'
import asyncio
import json
import uuid

from agents import RunContextWrapper
from deep_research.deep_research import create_deep_research


async def main():
    agent = create_deep_research()
    tools = {tool.name: tool for tool in agent.tools}
    print("Tools:", sorted(tools))
    assert {"parallel_web_search", "parallel_web_fetch"} <= tools.keys()
    session_id = str(uuid.uuid4())
    calls = [
        ("parallel_web_search", {
            "objective": "Find Agency Swarm documentation about MCP integration.",
            "search_queries": ["Agency Swarm MCP integration"],
            "session_id": session_id,
        }),
        ("parallel_web_fetch", {
            "urls": ["https://agency-swarm.ai/core-framework/tools/mcp-integration"],
            "objective": "How do agents connect to Streamable HTTP MCP servers?",
            "session_id": session_id,
        }),
    ]
    for name, arguments in calls:
        result = await tools[name].on_invoke_tool(
            RunContextWrapper(context=None), json.dumps(arguments)
        )
        print(f"{name}: {str(result)[:1000]}")


asyncio.run(main())
PY
```

Expect both tool names and source excerpts. A quota response is a failed request,
not a successful search. Anonymous access has lower rate limits; follow any retry
guidance before trying again. See the [Parallel setup and limits](https://docs.parallel.ai/integrations/mcp/search-mcp)
for higher-volume use.

Restart OpenSwarm after editing the factory and instructions. Try asking:

> Ask Deep Research to use Parallel Search to research recent changes in the
> Model Context Protocol. Read the primary sources and cite their URLs.

The connection check above does not run this model-driven research request.
To undo the customization, remove the added loading/renaming block, `*parallel_tools`,
imports, and instruction bullet. For other MCP transports, see the existing
[MCP customization guide](../.cursor/commands/add-mcp.md).
