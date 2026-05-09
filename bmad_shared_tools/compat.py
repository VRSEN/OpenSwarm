from __future__ import annotations

try:
    from agency_swarm.tools import BaseTool
except ModuleNotFoundError:  # pragma: no cover - fallback for local tests without agency_swarm installed
    from pydantic import BaseModel

    class BaseTool(BaseModel):
        class ToolConfig:
            strict: bool = False
