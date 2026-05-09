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


def create_bmad_developer() -> Agent:
    return Agent(
        name="BMAD Developer",
        description=(
            "Implementation specialist for BMAD workflows. Creates stories, executes development tasks, "
            "reviews code, and maintains sprint progress artifacts."
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
            "Crea una user story pronta per lo sviluppo.",
            "Implementa una feature seguendo il flusso BMAD.",
            "Fai code review e proponi correzioni.",
        ],
    )
