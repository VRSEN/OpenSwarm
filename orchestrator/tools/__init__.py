"""Tools registered exclusively on the orchestrator.

Lives separate from `shared_tools/` so it cannot be imported via wildcard
or accidentally given to a specialist agent. Anything here breaks the
orchestrator's strict "router only" contract by design — see
orchestrator/instructions.md for the documented carve-out.
"""

from orchestrator.tools.SwitchProvider import SwitchProvider

__all__ = ["SwitchProvider"]
