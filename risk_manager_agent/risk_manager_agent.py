import os

from agency_swarm import Agent, ModelSettings
from agency_swarm.tools import IPythonInterpreter, PersistentShellTool
from openai.types.shared import Reasoning

from config import get_default_model, is_openai_provider
from trading_tools import IBKRAccountSnapshot, MarketDataSnapshot, TradingCapabilityDetector

current_dir = os.path.dirname(os.path.abspath(__file__))


def create_risk_manager_agent() -> Agent:
    return Agent(
        name="Risk Manager",
        description="Trading risk specialist for exposure, drawdown, liquidity, compliance, and pre-trade checks.",
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
            "Risk-check this proposed trade.",
            "Analyze portfolio drawdown and concentration risk.",
            "Create daily risk limits for my trading system.",
            "Review leverage, stop-loss, and exposure constraints.",
        ],
    )
