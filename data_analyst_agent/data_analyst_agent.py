import os
from agency_swarm import Agent, ModelSettings
from openai.types.shared.reasoning import Reasoning
from agency_swarm.tools import (
    PersistentShellTool,
    LoadFileAttachment,
)
from shared_tools import CopyFile, ExecuteTool, FindTools, ManageConnections, SearchTools

from config import get_default_model, is_openai_provider

current_dir = os.path.dirname(os.path.abspath(__file__))
instructions_path = os.path.join(current_dir, "instructions.md")


def _hosted_tools():
    """Return hosted OpenAI tools only when using the Responses API."""
    if not is_openai_provider():
        return []
    from agency_swarm.tools import WebSearchTool, IPythonInterpreter
    return [WebSearchTool(), IPythonInterpreter]


def create_data_analyst() -> Agent:
    tools = [
        * _hosted_tools(),
        PersistentShellTool,
        LoadFileAttachment,
        CopyFile,
        ExecuteTool,
        FindTools,
        ManageConnections,
        SearchTools,
    ]
    return Agent(
        name="Data Analyst",
        description="Advanced data analytics agent that generates charts and provides actionable insights.",
        instructions=instructions_path,
        tools_folder=os.path.join(current_dir, "tools"),
        model=get_default_model(),
        tools=tools,
        model_settings=ModelSettings(
            reasoning=Reasoning(effort="medium", summary="auto") if is_openai_provider() else None,
            truncation="auto",
            response_include=["web_search_call.action.sources"] if is_openai_provider() else None,
        ),
        conversation_starters=[
            "Analyze this CSV file and show me the key trends.",
            "Create a dashboard with charts from my sales data.",
            "Connect to my Google Analytics and summarize last month's traffic.",
            "Find hidden patterns in this dataset and visualize them.",
        ],
    )
