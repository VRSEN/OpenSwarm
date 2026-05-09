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


def create_bmad_technical_writer() -> Agent:
    return Agent(
        name="BMAD Technical Writer",
        description=(
            "Technical writing specialist for BMAD workflows. Produces developer-facing documents, "
            "project documentation, and structured technical explanations."
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
            "Documenta questo progetto software in stile BMAD.",
            "Spiega questo componente tecnico in modo strutturato.",
            "Crea documentazione per sviluppatori e stakeholder.",
        ],
    )
