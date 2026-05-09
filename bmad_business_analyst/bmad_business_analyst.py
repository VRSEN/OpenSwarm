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


def create_bmad_business_analyst() -> Agent:
    return Agent(
        name="BMAD Business Analyst",
        description=(
            "Business analysis specialist for BMAD workflows. Creates product briefs, PRFAQs, "
            "discovery outputs, and project scans for software initiatives."
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
            "Crea un product brief BMAD per una nuova app SaaS.",
            "Analizza questo progetto software e prepara discovery, obiettivi e vincoli.",
            "Trasforma questa idea in un brief pronto per il PM.",
        ],
    )
