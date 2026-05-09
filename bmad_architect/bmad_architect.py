from agency_swarm import Agent, ModelSettings
from agency_swarm.tools import PersistentShellTool
from openai.types.shared import Reasoning
from dotenv import load_dotenv

from config import get_default_model, is_openai_provider
from bmad_shared_tools import (
    BmadBrownfieldSupport,
    BmadInstantiateTemplate,
    BmadQaCheck,
    BmadValidateArtifact,
    BmadValidateDirectory,
)

load_dotenv()


def create_bmad_architect() -> Agent:
    return Agent(
        name="BMAD Architect",
        description=(
            "System architecture specialist for BMAD workflows. Produces architecture documents, "
            "project context, and epics/stories readiness outputs."
        ),
        instructions="./instructions.md",
        files_folder="./files",
        tools_folder="../virtual_assistant/tools",
        model=get_default_model(),
        model_settings=ModelSettings(
            reasoning=Reasoning(effort="medium", summary="auto") if is_openai_provider() else None,
        ),
        tools=[
            PersistentShellTool,
            BmadInstantiateTemplate,
            BmadValidateArtifact,
            BmadValidateDirectory,
            BmadBrownfieldSupport,
            BmadQaCheck,
        ],
        conversation_starters=[
            "Crea l'architettura tecnica per questa applicazione.",
            "Genera epiche e storie a partire dal PRD.",
            "Verifica la readiness di implementazione del progetto.",
        ],
    )
