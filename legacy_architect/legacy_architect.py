import os

from agency_swarm import Agent, ModelSettings
from openai.types.shared import Reasoning

from config import get_default_model, is_openai_provider
from run_utils import _load_openswarm_dotenv

_load_openswarm_dotenv()
current_dir = os.path.dirname(os.path.abspath(__file__))


def create_legacy_architect() -> Agent:
    return Agent(
        name="Legacy Architect",
        description=(
            "Generational wealth agent. Plans Buy-Borrow-Die strategy, documents Step-Up in Basis "
            "for heirs, and encrypts records in the Sovereign Vault."
        ),
        instructions=os.path.join(current_dir, "instructions.md"),
        tools_folder=os.path.join(current_dir, "tools"),
        files_folder=os.path.join(current_dir, "files"),
        model=get_default_model(),
        model_settings=ModelSettings(
            reasoning=Reasoning(effort="medium", summary="auto") if is_openai_provider() else None,
        ),
        conversation_starters=[
            "Document step-up in basis for my rental property.",
            "Outline a Buy-Borrow-Die plan for my appreciating assets.",
            "Store basis documentation in the encrypted Sovereign Vault.",
            "Generate a generational transfer checklist for my heirs.",
        ],
    )
