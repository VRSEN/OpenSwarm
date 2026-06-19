from agency_swarm import Agent, ModelSettings
from agency_swarm.tools import WebSearchTool, IPythonInterpreter
from openai.types.shared import Reasoning
from virtual_assistant.tools.ScholarSearch import ScholarSearch

from config import get_default_model, is_openai_provider, openai_hosted_tools


def create_deep_research() -> Agent:
    return Agent(
        name="Deep Research Agent",
        description="Comprehensive deep research agent that conducts thorough research on any topic.",
        instructions="./instructions.md",
        files_folder="./files",
        tools=[*openai_hosted_tools(WebSearchTool), ScholarSearch, IPythonInterpreter],
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
