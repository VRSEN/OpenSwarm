from agency_swarm import Agent, ModelSettings
from openai.types.shared import Reasoning

from config import get_default_model, is_openai_provider
from run_utils import _load_openswarm_dotenv

_load_openswarm_dotenv()


def create_architect_orchestrator() -> Agent:
    return Agent(
        name="Architect Orchestrator",
        description=(
            "Routes Cash Flow Mastery requests across the Architect Blueprint swarm. "
            "Assesses Stability → Skill Stacking → Asset Acquisition → Sovereignty stage "
            "and enforces mandatory sequence gates."
        ),
        instructions="./instructions.md",
        tools_folder="./tools",
        model=get_default_model(),
        model_settings=ModelSettings(
            reasoning=Reasoning(effort="medium", summary="auto") if is_openai_provider() else None,
        ),
        conversation_starters=[
            "Assess my stage in the Cash Flow Mastery sequence.",
            "Build my Architect roadmap for the next 6 months.",
            "Which modules am I allowed to access right now?",
            "I earn $7,200/month with no Stability Fund—where do I start?",
        ],
    )
