from agency_swarm import Agent, ModelSettings
from agency_swarm.tools import LoadFileAttachment
from openai.types.shared import Reasoning
from virtual_assistant.tools.ScholarSearch import ScholarSearch

from config import get_default_model, is_openai_provider


def _hosted_tools():
    """Return hosted OpenAI tools only when using the Responses API."""
    if not is_openai_provider():
        return []
    from agency_swarm.tools import WebSearchTool, IPythonInterpreter
    return [WebSearchTool(), IPythonInterpreter]


def create_deep_research() -> Agent:
    return Agent(
        name="Deep Research Agent",
        description="Comprehensive deep research agent that conducts thorough research on any topic.",
        instructions="./instructions.md",
        files_folder="./files",
        tools=[*_hosted_tools(), ScholarSearch],
        model=get_default_model(),
        model_settings=ModelSettings(
            reasoning=Reasoning(effort="high", summary="auto") if is_openai_provider() else None,
            response_include=["web_search_call.action.sources"] if is_openai_provider() else None,
        ),
        conversation_starters=[
            "Research the latest trends in renewable energy for 2026.",
            "Give me a comprehensive analysis of the AI agent market landscape.",
            "Find recent academic papers on large language model reasoning.",
            "Compare the top 5 project management tools with pros and cons.",
        ],
    )
