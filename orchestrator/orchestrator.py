from agency_swarm import Agent, ModelSettings
from openai.types.shared import Reasoning

from config import get_default_model, is_openai_provider
from run_utils import _load_openswarm_dotenv

_load_openswarm_dotenv()


def create_orchestrator() -> Agent:
    return Agent(
        name="Orchestrator",
        description=(
            "Primary coordinator that plans multi-agent workflows, runs independent workstreams in parallel, "
            "and hands off to a specialist when tight user iteration is needed."
        ),
        instructions="./instructions.md",
        model=get_default_model(),
        model_settings=ModelSettings(
            reasoning=Reasoning(effort="medium", summary="auto") if is_openai_provider() else None,
        ),
        conversation_starters=[
            "What can this agency do?",
            "Build a full launch package: research, slides, docs, and creative assets.",
            "Analyze my data and then turn insights into a polished executive deck.",
            "Coordinate a workflow for proposal doc + promo visuals + short product video.",
        ],
    )


if __name__ == "__main__":
    from agency_swarm import Agency
    Agency(create_orchestrator()).terminal_demo()
