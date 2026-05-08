import os

from agency_swarm import Agent, ModelSettings
from agency_swarm.tools import IPythonInterpreter, PersistentShellTool
from openai.types.shared import Reasoning

from config import get_default_model, is_openai_provider
from trading_tools import IBKRAccountSnapshot, IBKROrderTool, MarketDataSnapshot, TradingCapabilityDetector

current_dir = os.path.dirname(os.path.abspath(__file__))


def create_trade_execution_agent() -> Agent:
    return Agent(
        name="Trade Execution Agent",
        description="IBKR execution specialist for account snapshots, market-data checks, order previews, and gated live order routing.",
        instructions=os.path.join(current_dir, "instructions.md"),
        tools=[
            TradingCapabilityDetector,
            IBKRAccountSnapshot,
            IBKROrderTool,
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
            "Check which IBKR and market-data capabilities are available.",
            "Show my IBKR account snapshot and current positions.",
            "Preview a risk-checked order for SPY.",
            "Probe whether live data is available for AAPL and QQQ.",
        ],
    )
