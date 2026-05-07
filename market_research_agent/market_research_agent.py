import os

from agency_swarm import Agent, ModelSettings
from agency_swarm.tools import IPythonInterpreter, WebSearchTool
from openai.types.shared import Reasoning

from config import get_default_model, is_openai_provider
from trading_tools import MarketDataSnapshot, TradingCapabilityDetector
from virtual_assistant.tools.ScholarSearch import ScholarSearch

current_dir = os.path.dirname(os.path.abspath(__file__))


def create_market_research_agent() -> Agent:
    return Agent(
        name="Market Research Analyst",
        description="Market, fundamental, sentiment, politics, macro, and paid-research synthesis specialist.",
        instructions=os.path.join(current_dir, "instructions.md"),
        tools=[
            WebSearchTool(),
            ScholarSearch,
            TradingCapabilityDetector,
            MarketDataSnapshot,
            IPythonInterpreter,
        ],
        model=get_default_model(),
        model_settings=ModelSettings(
            reasoning=Reasoning(effort="high", summary="auto") if is_openai_provider() else None,
            truncation="auto",
            response_include=["web_search_call.action.sources"] if is_openai_provider() else None,
        ),
        conversation_starters=[
            "Research the market setup for semiconductors this week.",
            "Analyze sentiment and political risk around a stock.",
            "Compare analyst, news, and macro factors for my watchlist.",
            "Detect which paid research APIs are available and use them if possible.",
        ],
    )
