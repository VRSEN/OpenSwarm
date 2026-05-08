import os

from agency_swarm import Agent, ModelSettings
from agency_swarm.tools import IPythonInterpreter, PersistentShellTool
from openai.types.shared import Reasoning

from config import get_default_model, is_openai_provider
from trading_tools import MarketDataSnapshot, QuantBacktest, TradingCapabilityDetector

current_dir = os.path.dirname(os.path.abspath(__file__))


def create_quantitative_analyst_agent() -> Agent:
    return Agent(
        name="Quantitative Analyst",
        description="Quantitative research specialist for factor analysis, backtesting, signals, and algorithm design.",
        instructions=os.path.join(current_dir, "instructions.md"),
        tools=[
            TradingCapabilityDetector,
            MarketDataSnapshot,
            QuantBacktest,
            IPythonInterpreter,
            PersistentShellTool,
        ],
        model=get_default_model(),
        model_settings=ModelSettings(
            reasoning=Reasoning(effort="high", summary="auto") if is_openai_provider() else None,
            truncation="auto",
        ),
        conversation_starters=[
            "Backtest a moving-average strategy on SPY.",
            "Build a factor screen for large-cap stocks.",
            "Analyze volatility and drawdown for my watchlist.",
            "Design an intraday algorithm research plan.",
        ],
    )
