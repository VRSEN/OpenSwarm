import os

from agency_swarm import Agent, ModelSettings
from openai.types.shared import Reasoning

from config import get_default_model, is_openai_provider
from run_utils import _load_openswarm_dotenv

_load_openswarm_dotenv()

current_dir = os.path.dirname(os.path.abspath(__file__))


def create_discipline_controller() -> Agent:
    return Agent(
        name="Discipline Controller",
        description=(
            "Mechanical cash-flow enforcer for self-employed operators. "
            "Profit First allocations, runway tracking, expense validation, and discipline protocols."
        ),
        instructions=os.path.join(current_dir, "instructions.md"),
        tools_folder=os.path.join(current_dir, "tools"),
        files_folder=os.path.join(current_dir, "files"),
        model=get_default_model(),
        model_settings=ModelSettings(
            reasoning=Reasoning(effort="medium", summary="auto") if is_openai_provider() else None,
        ),
        conversation_starters=[
            "Split my $5,000 client payment using Profit First.",
            "How many months of runway do I have?",
            "Can I afford a $400/month software subscription?",
            "Create my weekly financial discipline checklist.",
        ],
    )
