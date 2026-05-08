import os

from agency_swarm import Agent, ModelSettings
from agency_swarm.tools import IPythonInterpreter, PersistentShellTool
from openai.types.shared import Reasoning

from config import get_default_model, is_openai_provider
from trading_tools import IBKRAccountSnapshot, MarketDataSnapshot, TradingCapabilityDetector

current_dir = os.path.dirname(os.path.abspath(__file__))


def create_portfolio_manager_agent() -> Agent:
    return Agent(
        name="Portfolio Manager",
        description="Portfolio construction and allocation specialist for daily, short, medium, and long-horizon strategies.",
        instructions=os.path.join(current_dir, "instructions.md"),
        tools=[
            TradingCapabilityDetector,
            IBKRAccountSnapshot,
            MarketDataSnapshot,
            IPythonInterpreter,
            PersistentShellTool,
        ],
        model=get_default_model(),
        model_settings=ModelSettings(
            reasoning=Reasoning(effort="high", summary="auto") if is_openai_provider() else None,
            truncation="auto",
        ),
        conversation_starters=[
            "Review my portfolio allocation and suggest rebalancing priorities.",
            "Design a multi-horizon equity portfolio process.",
            "Rank trade candidates by expected ROI and risk.",
            "Create daily, swing, and long-term portfolio rules.",
        ],
    )
