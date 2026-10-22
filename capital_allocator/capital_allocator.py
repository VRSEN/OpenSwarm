import os

from agency_swarm import Agent, ModelSettings
from openai.types.shared import Reasoning

from config import get_default_model, is_openai_provider
from run_utils import _load_openswarm_dotenv

_load_openswarm_dotenv()
current_dir = os.path.dirname(os.path.abspath(__file__))


def create_capital_allocator() -> Agent:
    return Agent(
        name="Capital Allocator",
        description=(
            "Decides where the next surplus dollar goes after two-key underwriting: "
            "Stability Fund, tax, business reinvestment, or a capped speculative bet."
        ),
        instructions=os.path.join(current_dir, "instructions.md"),
        tools_folder=os.path.join(current_dir, "tools"),
        files_folder=os.path.join(current_dir, "files"),
        model=get_default_model(),
        model_settings=ModelSettings(
            reasoning=Reasoning(effort="medium", summary="auto") if is_openai_provider() else None,
        ),
        conversation_starters=[
            "Where should this month's surplus go?",
            "Is my risk budget big enough for this flip?",
            "Business reinvest vs a Kalshi TEST — which dollar wins?",
        ],
    )
