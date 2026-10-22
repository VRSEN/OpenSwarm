import os

from agency_swarm import Agent, ModelSettings
from openai.types.shared import Reasoning

from config import get_default_model, is_openai_provider
from run_utils import _load_openswarm_dotenv

_load_openswarm_dotenv()
current_dir = os.path.dirname(os.path.abspath(__file__))


def create_leverage_strategist() -> Agent:
    return Agent(
        name="Leverage Strategist",
        description=(
            "Mathematical leverage agent. Calculates Spread (Asset Yield − Cost of Capital), "
            "applies the Asset Formula, validates acquisition-only debt, and models Skill Stacking ROI."
        ),
        instructions=os.path.join(current_dir, "instructions.md"),
        tools_folder=os.path.join(current_dir, "tools"),
        files_folder=os.path.join(current_dir, "files"),
        model=get_default_model(),
        model_settings=ModelSettings(
            reasoning=Reasoning(effort="medium", summary="auto") if is_openai_provider() else None,
        ),
        conversation_starters=[
            "Calculate spread on a 12% yield asset with 6% debt.",
            "Can I use debt for this purchase—or is it ego?",
            "Model income density if I invest 40 hours in a new skill.",
            "Does this asset pass the Asset Formula?",
        ],
    )
