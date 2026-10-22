import json
from datetime import datetime, timezone
from pathlib import Path

from agency_swarm.tools import BaseTool
from pydantic import Field

DASHBOARD_FILE = "reputation_dashboard.json"


class UpdateReputationDashboard(BaseTool):
    """Persists and returns Reputation Credit Dashboard state."""

    action: str = Field(..., description="update, get, or export")
    score_data: dict = Field(default_factory=dict)

    def _path(self) -> Path:
        p = Path(__file__).resolve().parent.parent / "files"
        p.mkdir(parents=True, exist_ok=True)
        return p / DASHBOARD_FILE

    def run(self) -> str:
        path = self._path()
        action = self.action.lower().strip()

        if action == "get":
            if not path.exists():
                return json.dumps({"score": None, "history": [], "message": "No dashboard data yet"})
            with open(path, encoding="utf-8") as f:
                return json.dumps(json.load(f), indent=2)

        if action in ("update", "export"):
            history = []
            if path.exists():
                with open(path, encoding="utf-8") as f:
                    history = json.load(f).get("history", [])
            entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                **self.score_data,
            }
            history.append(entry)
            dashboard = {
                "current_score": self.score_data.get("reputation_credit_score"),
                "tier": self.score_data.get("tier"),
                "travels_ahead_summary": self.score_data.get("travels_ahead_summary", ""),
                "history": history[-52:],
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(dashboard, f, indent=2)
            result = {"dashboard": dashboard, "path": str(path)}
            if action == "export":
                result["export_ready"] = True
            return json.dumps(result, indent=2)

        return json.dumps({"error": "action must be update, get, or export"})


if __name__ == "__main__":
    print(
        UpdateReputationDashboard(
            action="update",
            score_data={"reputation_credit_score": 82, "tier": "Gold", "travels_ahead_summary": "Reliable operator"},
        ).run()
    )
