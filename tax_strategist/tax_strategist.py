import os

from agency_swarm import Agent, ModelSettings
from openai.types.shared import Reasoning

from config import get_default_model, is_openai_provider
from run_utils import _load_openswarm_dotenv

_load_openswarm_dotenv()

current_dir = os.path.dirname(os.path.abspath(__file__))


def create_tax_strategist() -> Agent:
    return Agent(
        name="Tax Strategist",
        description=(
            "Self-employment tax specialist: SE tax estimates, quarterly payment schedules, "
            "and deduction audits for freelancers and solopreneurs."
        ),
        instructions=os.path.join(current_dir, "instructions.md"),
        tools_folder=os.path.join(current_dir, "tools"),
        files_folder=os.path.join(current_dir, "files"),
        model=get_default_model(),
        model_settings=ModelSettings(
            reasoning=Reasoning(effort="medium", summary="auto") if is_openai_provider() else None,
        ),
        conversation_starters=[
            "Estimate my self-employment tax on $95,000 net profit.",
            "Build my quarterly estimated tax schedule for this year.",
            "Audit my business expenses for missed deductions.",
            "How much should I set aside monthly for taxes?",
        ],
    )
