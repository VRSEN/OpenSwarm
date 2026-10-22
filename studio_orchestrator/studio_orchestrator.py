from agency_swarm import Agent, ModelSettings
from openai.types.shared import Reasoning

from config import get_default_model, is_openai_provider
from run_utils import _load_openswarm_dotenv

_load_openswarm_dotenv()


def create_studio_orchestrator() -> Agent:
    return Agent(
        name="Orchestrator",
        description=(
            "Studio coordinator for Architect Blueprint deliverables — routes to Docs, Slides, "
            "Image, and Video specialists. Uses financial profile from user_context when present."
        ),
        instructions="./instructions.md",
        model=get_default_model(),
        model_settings=ModelSettings(
            reasoning=Reasoning(effort="medium", summary="auto") if is_openai_provider() else None,
        ),
        conversation_starters=[
            "Create a financial summary PDF from my intake numbers.",
            "Build a pitch deck for my business.",
            "Generate a brand hero image.",
            "Create a short promo video for my offer.",
        ],
    )
