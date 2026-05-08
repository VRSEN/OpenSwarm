from agency_swarm import Agent, ModelSettings
from openai.types.shared import Reasoning
from dotenv import load_dotenv

from config import get_default_model, is_openai_provider

load_dotenv()


def create_orchestrator() -> Agent:
    return Agent(
        name="Orchestrator",
        description=(
            "Primary coordinator for trading, portfolio management, market research, risk, quant analysis, "
            "and IBKR execution workflows."
        ),
        instructions="./instructions.md",
        model=get_default_model(),
        model_settings=ModelSettings(
            reasoning=Reasoning(effort="medium", summary="auto") if is_openai_provider() else None,
        ),
        conversation_starters=[
            "Check what trading APIs and market-data subscriptions are available.",
            "Review my IBKR portfolio and suggest risk-adjusted trade priorities.",
            "Research and backtest a trade idea before order preview.",
            "Build daily, swing, medium-term, and long-term trading workflows.",
        ],
    )


if __name__ == "__main__":
    from agency_swarm import Agency
    Agency(create_orchestrator()).terminal_demo()
