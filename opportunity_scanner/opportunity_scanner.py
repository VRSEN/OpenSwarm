import os

from agency_swarm import Agent, ModelSettings
from agency_swarm.tools import WebSearchTool
from openai.types.shared import Reasoning

from config import get_default_model, is_openai_provider
from run_utils import _load_openswarm_dotenv

_load_openswarm_dotenv()
current_dir = os.path.dirname(os.path.abspath(__file__))


def create_opportunity_scanner() -> Agent:
    return Agent(
        name="Opportunity Scanner",
        description=(
            "Scans five Invisible Gaps (Convenience, Information, Connection, Skill, Attention). "
            "Prioritizes Money Velocity over volume and structures micro-investment projects."
        ),
        instructions=os.path.join(current_dir, "instructions.md"),
        tools_folder=os.path.join(current_dir, "tools"),
        files_folder=os.path.join(current_dir, "files"),
        model=get_default_model(),
        tools=[WebSearchTool()],
        model_settings=ModelSettings(
            reasoning=Reasoning(effort="medium", summary="auto") if is_openai_provider() else None,
            response_include=["web_search_call.action.sources"] if is_openai_provider() else None,
        ),
        conversation_starters=[
            "Scan Invisible Gaps with $25/day for 7 days.",
            "Score Money Velocity on my last project recycle.",
            "Fund a $1,500 project with $25 micro-investments.",
            "Show my velocity pipeline ranked by recycle speed.",
        ],
    )
