import os

from agency_swarm import Agent, ModelSettings
from openai.types.shared import Reasoning

from config import get_default_model, is_openai_provider
from run_utils import _load_openswarm_dotenv

_load_openswarm_dotenv()

current_dir = os.path.dirname(os.path.abspath(__file__))


def create_wealth_architect() -> Agent:
    return Agent(
        name="Wealth Architect",
        description=(
            "Long-term wealth builder for self-employed users: retirement account comparison, "
            "sovereignty number projection, and investment policy statements."
        ),
        instructions=os.path.join(current_dir, "instructions.md"),
        tools_folder=os.path.join(current_dir, "tools"),
        files_folder=os.path.join(current_dir, "files"),
        model=get_default_model(),
        model_settings=ModelSettings(
            reasoning=Reasoning(effort="medium", summary="auto") if is_openai_provider() else None,
        ),
        conversation_starters=[
            "SEP-IRA vs Solo 401(k)—which is better for me?",
            "Calculate my sovereignty number at $72,000 annual expenses.",
            "Draft an investment policy for Growth stage, moderate risk.",
            "How far am I from financial sovereignty?",
        ],
    )
