from agency_swarm import Agent, ModelSettings
from openai.types.shared import Reasoning

from config import get_default_model, is_openai_provider
from run_utils import _load_openswarm_dotenv

_load_openswarm_dotenv()


def create_sovereignty_orchestrator() -> Agent:
    return Agent(
        name="Sovereignty Orchestrator",
        description=(
            "Chief financial coordinator for self-employed wealth building. "
            "Assesses Survival→Sovereignty stage, routes to specialists, "
            "and generates mechanical roadmaps."
        ),
        instructions="./instructions.md",
        tools_folder="./tools",
        model=get_default_model(),
        model_settings=ModelSettings(
            reasoning=Reasoning(effort="medium", summary="auto") if is_openai_provider() else None,
        ),
        conversation_starters=[
            "I made $8,000 this month but still feel broke—what should I do?",
            "Assess my financial stage and give me a sovereignty roadmap.",
            "Where am I on the Survival to Sovereignty journey?",
            "Route me to the right specialist for tax reserves and runway.",
        ],
    )
