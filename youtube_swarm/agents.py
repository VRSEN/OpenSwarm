"""Agent factories for the YouTube swarm.

Each agent is an agency_swarm.Agent backed by ClaudeAgentSDKModel,
which spawns the local `claude` CLI for subscription auth. The
researcher gets Claude Code's built-in WebSearch; the others run
toolless (LLM only).
"""

from pathlib import Path

from agency_swarm import Agent, ModelSettings

from config import get_default_model

_INSTRUCTIONS = Path(__file__).parent / "instructions"


def _read(name: str) -> str:
    return (_INSTRUCTIONS / f"{name}.md").read_text(encoding="utf-8")


def create_orchestrator() -> Agent:
    return Agent(
        name="Orchestrator",
        description=(
            "Routes a YouTube content request to the right specialist "
            "(Researcher → Ideator → Scripter) and assembles the "
            "final deliverable. Never produces deliverables itself."
        ),
        instructions=_read("orchestrator"),
        model=get_default_model(),
        model_settings=ModelSettings(),
        conversation_starters=[
            "Research the budget cooking niche and propose 3 video scripts.",
            "I run a productivity channel. Find me trending angles and 5 ideas.",
            "Help me launch a new finance channel — niche brief + 3 scripts.",
            "What's working in YouTube Shorts for fitness right now?",
        ],
    )


def _researcher_model():
    """Build a model that enables Claude Code's built-in WebSearch.

    Falls back to the agency's default model if the SDK adapter isn't
    in use (e.g. user runs with OpenAI directly).
    """
    base = get_default_model()
    try:
        from claude_oauth_model import ClaudeAgentSDKModel  # noqa: PLC0415
        if isinstance(base, ClaudeAgentSDKModel):
            return ClaudeAgentSDKModel(model=base._model, use_builtin_tools=True)
    except ImportError:
        pass
    return base


def create_researcher() -> Agent:
    return Agent(
        name="Researcher",
        description=(
            "Investigates a YouTube niche with WebSearch and returns a "
            "structured research brief: top performers, trending angles, "
            "audience pain points, format conventions, sources."
        ),
        instructions=_read("researcher"),
        model=_researcher_model(),
        model_settings=ModelSettings(),
        tools=[],
    )


def create_ideator() -> Agent:
    return Agent(
        name="Ideator",
        description=(
            "Turns a research brief into 8 ranked video ideas, each "
            "with hook, target viewer, and a why-this-works citation."
        ),
        instructions=_read("ideator"),
        model=get_default_model(),
        model_settings=ModelSettings(),
        tools=[],
    )


def create_scripter() -> Agent:
    return Agent(
        name="Scripter",
        description=(
            "Writes one full ready-to-record YouTube script per call: "
            "hook, intro, body with B-roll cues, CTA, outro."
        ),
        instructions=_read("scripter"),
        model=get_default_model(),
        model_settings=ModelSettings(),
        tools=[],
    )
