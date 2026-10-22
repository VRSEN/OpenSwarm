import os

from agency_swarm import Agent, ModelSettings
from openai.types.shared import Reasoning

from config import get_default_model, is_openai_provider
from run_utils import _load_openswarm_dotenv

_load_openswarm_dotenv()
current_dir = os.path.dirname(os.path.abspath(__file__))


def create_behavioral_mirror() -> Agent:
    return Agent(
        name="Behavioral Mirror",
        description=(
            "Scientific mirror of spending behavior. Detects invisible transactions, "
            "enforces the 72-hour Pause Rule, and sends identity-based notifications."
        ),
        instructions=os.path.join(current_dir, "instructions.md"),
        tools_folder=os.path.join(current_dir, "tools"),
        files_folder=os.path.join(current_dir, "files"),
        model=get_default_model(),
        model_settings=ModelSettings(
            reasoning=Reasoning(effort="medium", summary="auto") if is_openai_provider() else None,
        ),
        conversation_starters=[
            "I almost bought something impulsively—run the 72-hour pause.",
            "Mirror my last week of spending patterns.",
            "Was this transaction invisible to my budget?",
            "Send me an identity notification, not a savings alert.",
        ],
    )
