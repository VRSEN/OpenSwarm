import os

from agency_swarm import Agent, ModelSettings
from agency_swarm.tools import IPythonInterpreter, LoadFileAttachment, PersistentShellTool
from openai.types.shared import Reasoning

from config import get_default_model, is_openai_provider
from run_utils import _load_openswarm_dotenv
from shared_tools import CopyFile, ExecuteTool, FindTools, ManageConnections, SearchTools

_load_openswarm_dotenv()

current_dir = os.path.dirname(os.path.abspath(__file__))


def create_financial_analyst() -> Agent:
    return Agent(
        name="Financial Analyst",
        description=(
            "Quantitative analyst for self-employed financial data: "
            "CSV ingestion, KPI computation, and dashboard generation."
        ),
        instructions=os.path.join(current_dir, "instructions.md"),
        tools_folder=os.path.join(current_dir, "tools"),
        files_folder=os.path.join(current_dir, "files"),
        model=get_default_model(),
        tools=[
            PersistentShellTool,
            IPythonInterpreter,
            LoadFileAttachment,
            CopyFile,
            ExecuteTool,
            FindTools,
            ManageConnections,
            SearchTools,
        ],
        model_settings=ModelSettings(
            reasoning=Reasoning(effort="medium", summary="auto") if is_openai_provider() else None,
            truncation="auto",
        ),
        conversation_starters=[
            "Analyze my transaction CSV and show cash-flow KPIs.",
            "Generate a runway and allocation dashboard from my data.",
            "What's my revenue volatility over the last 6 months?",
            "Connect to QuickBooks and summarize last quarter.",
        ],
    )
