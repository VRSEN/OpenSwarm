import json
from datetime import datetime, timezone
from pathlib import Path

from agency_swarm.tools import BaseTool
from pydantic import Field

JOURNAL_FILE = "behavior_journal.json"


class LogBehaviorPattern(BaseTool):
    """Persists behavior events to local journal for pattern analysis."""

    action: str = Field(..., description="add, list, or summary")
    event_type: str = Field(default="")
    metadata: dict = Field(default_factory=dict)

    def _path(self) -> Path:
        p = Path(__file__).resolve().parent.parent / "files"
        p.mkdir(parents=True, exist_ok=True)
        return p / JOURNAL_FILE

    def _load(self) -> list:
        path = self._path()
        if not path.exists():
            return []
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def _save(self, data: list) -> None:
        with open(self._path(), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def run(self) -> str:
        action = self.action.lower().strip()
        journal = self._load()

        if action == "add":
            entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event_type": self.event_type,
                "metadata": self.metadata,
            }
            journal.append(entry)
            self._save(journal)
            return json.dumps({"added": entry, "total_events": len(journal)}, indent=2)

        if action == "list":
            return json.dumps({"events": journal[-20:], "total": len(journal)}, indent=2)

        if action == "summary":
            counts = {}
            for e in journal:
                t = e.get("event_type", "unknown")
                counts[t] = counts.get(t, 0) + 1
            return json.dumps({"event_counts": counts, "total_events": len(journal)}, indent=2)

        return json.dumps({"error": "action must be add, list, or summary"})


if __name__ == "__main__":
    print(LogBehaviorPattern(action="add", event_type="pause", metadata={"amount": 189}).run())
    print(LogBehaviorPattern(action="summary").run())
