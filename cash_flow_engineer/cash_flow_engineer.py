import os

from agency_swarm import Agent, ModelSettings
from openai.types.shared import Reasoning

from config import get_default_model, is_openai_provider
from run_utils import _load_openswarm_dotenv

_load_openswarm_dotenv()
current_dir = os.path.dirname(os.path.abspath(__file__))


def create_cash_flow_engineer() -> Agent:
    return Agent(
        name="Cash Flow Engineer",
        description=(
            "Mechanical cash-flow executor. Runs 15/65/20 allocation, assigns jobs to every dollar, "
            "automates Stability Fund tracking, and executes debt snowball for high-APR debt."
        ),
        instructions=os.path.join(current_dir, "instructions.md"),
        tools_folder=os.path.join(current_dir, "tools"),
        files_folder=os.path.join(current_dir, "files"),
        model=get_default_model(),
        model_settings=ModelSettings(
            reasoning=Reasoning(effort="medium", summary="auto") if is_openai_provider() else None,
        ),
        conversation_starters=[
            "Split my $6,500 deposit using 15/65/20.",
            "How close am I to a 4-month Stability Fund?",
            "Assign jobs to every dollar I expect this month.",
            "Run debt snowball on my 9% credit card with $400 surplus.",
        ],
    )
