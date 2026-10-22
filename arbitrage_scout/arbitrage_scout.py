import os

from agency_swarm import Agent, ModelSettings
from agency_swarm.tools import WebSearchTool
from openai.types.shared import Reasoning

from config import get_default_model, is_openai_provider
from run_utils import _load_openswarm_dotenv

_load_openswarm_dotenv()

current_dir = os.path.dirname(os.path.abspath(__file__))


def create_arbitrage_scout() -> Agent:
    return Agent(
        name="Arbitrage Scout",
        description=(
            "Hunts high-velocity arbitrage for self-employed operators: "
            "vendor pricing gaps, subscription savings, and quick-ROI opportunities."
        ),
        instructions=os.path.join(current_dir, "instructions.md"),
        tools_folder=os.path.join(current_dir, "tools"),
        files_folder=os.path.join(current_dir, "files"),
        model=get_default_model(),
        tools=[WebSearchTool()],
        model_settings=ModelSettings(
            reasoning=Reasoning(effort="medium", summary="auto") if is_openai_provider() else None,
            response_include=["web_search_call.action.sources"] if is_openai_provider() else None,
        ),
        conversation_starters=[
            "Find arbitrage opportunities with $2,000 and 30-day horizon.",
            "Compare my payment processing fees to cheaper alternatives.",
            "Score this opportunity: $800 gain, $500 capital, 14 days.",
            "Show my arbitrage pipeline ranked by velocity.",
        ],
    )
