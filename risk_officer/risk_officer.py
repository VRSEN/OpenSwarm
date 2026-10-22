import os

from agency_swarm import Agent, ModelSettings
from openai.types.shared import Reasoning

from config import get_default_model, is_openai_provider
from run_utils import _load_openswarm_dotenv

_load_openswarm_dotenv()
current_dir = os.path.dirname(os.path.abspath(__file__))


def create_risk_officer() -> Agent:
    return Agent(
        name="Risk Officer",
        description=(
            "Adversarial underwriter. Tries to kill a deal — max loss, weak exits, seller claims — "
            "so you only take bets that survive a second key."
        ),
        instructions=os.path.join(current_dir, "instructions.md"),
        tools_folder=os.path.join(current_dir, "tools"),
        files_folder=os.path.join(current_dir, "files"),
        model=get_default_model(),
        model_settings=ModelSettings(
            reasoning=Reasoning(effort="medium", summary="auto") if is_openai_provider() else None,
        ),
        conversation_starters=[
            "Kill-case this $800 Kalshi contract.",
            "What's the worst realistic loss on this flip?",
            "Is my exit plan real or hope?",
        ],
    )
