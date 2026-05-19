"""YouTube ideation & scripting swarm — entry point.

Run:   python youtube_swarm.py

Requires:
  - claude CLI installed and logged in (`claude login`)
  - claude-agent-sdk in requirements.txt (already added)
  - DEFAULT_MODEL set to a Claude model id (e.g. claude-opus-4-7)
  - CLAUDE_USE_AGENT_SDK=1 in .env (or auto-detected when claude-agent-sdk
    is installed alongside a Claude DEFAULT_MODEL)
"""

import os

from dotenv import load_dotenv
from agents import set_tracing_disabled, set_tracing_export_api_key

load_dotenv()

# Disable OpenAI tracing in subscription mode — we're not calling OpenAI.
_tracing_key = os.getenv("OPENAI_API_KEY")
if _tracing_key and not (os.getenv("OPENAI_BASE_URL") or os.getenv("CLAUDE_USE_AGENT_SDK")):
    set_tracing_export_api_key(_tracing_key)
else:
    set_tracing_disabled(True)


def create_agency():
    from agency_swarm import Agency
    from agency_swarm.tools import SendMessage

    from youtube_swarm.agents import (
        create_orchestrator,
        create_researcher,
        create_ideator,
        create_scripter,
    )

    orchestrator = create_orchestrator()
    researcher = create_researcher()
    ideator = create_ideator()
    scripter = create_scripter()

    return Agency(
        orchestrator,
        researcher,
        ideator,
        scripter,
        communication_flows=[
            (orchestrator, researcher, SendMessage),
            (orchestrator, ideator, SendMessage),
            (orchestrator, scripter, SendMessage),
        ],
        name="YouTubeSwarm",
        shared_instructions=(
            "You are part of a focused team that turns a user's topic into "
            "research-backed YouTube video ideas and ready-to-record scripts. "
            "The Orchestrator is the only agent the user talks to directly. "
            "Specialists return their deliverable to the Orchestrator and stop."
        ),
    )


if __name__ == "__main__":
    agency = create_agency()
    agency.tui(show_reasoning=False, reload=False)
