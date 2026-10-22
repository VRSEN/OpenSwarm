import os

from agency_swarm import Agent, ModelSettings
from openai.types.shared import Reasoning

from config import get_default_model, is_openai_provider
from run_utils import _load_openswarm_dotenv

_load_openswarm_dotenv()
current_dir = os.path.dirname(os.path.abspath(__file__))


def create_reputation_validator() -> Agent:
    return Agent(
        name="Reputation Validator",
        description=(
            "Manages the Reputation Credit System. Scores behavioral trust, vets service providers, "
            "and treats character as an economic asset that travels ahead of the user."
        ),
        instructions=os.path.join(current_dir, "instructions.md"),
        tools_folder=os.path.join(current_dir, "tools"),
        files_folder=os.path.join(current_dir, "files"),
        model=get_default_model(),
        model_settings=ModelSettings(
            reasoning=Reasoning(effort="medium", summary="auto") if is_openai_provider() else None,
        ),
        conversation_starters=[
            "Calculate my Reputation Credit score from last 90 days.",
            "Vet this contractor before I pay $2,000.",
            "Update my Reputation Credit dashboard.",
            "Audit a provider's behavioral trust record.",
        ],
    )
