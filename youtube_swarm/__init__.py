"""YouTube ideation & scripting swarm.

Four-agent setup on agency-swarm, backed by ClaudeAgentSDKModel for
Claude subscription auth via the local `claude` CLI.
"""

from .agents import (
    create_orchestrator,
    create_researcher,
    create_ideator,
    create_scripter,
)

__all__ = [
    "create_orchestrator",
    "create_researcher",
    "create_ideator",
    "create_scripter",
]
