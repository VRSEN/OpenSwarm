import json
import os
import uuid
from pathlib import Path

from agency_swarm.tools import BaseTool
from pydantic import Field

PIPELINE_FILENAME = "arbitrage_pipeline.json"


def _pipeline_path() -> Path:
    base = Path(__file__).resolve().parent.parent / "files"
    base.mkdir(parents=True, exist_ok=True)
    return base / PIPELINE_FILENAME


def _load_pipeline() -> list:
    path = _pipeline_path()
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _save_pipeline(data: list) -> None:
    path = _pipeline_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


class TrackArbitragePipeline(BaseTool):
    """
    Maintains a local pipeline of arbitrage opportunities with add, update, list, and close actions.
    Opportunities are sorted by velocity score when listed.
    """

    action: str = Field(..., description="add, update, list, or close.")
    opportunity_id: str = Field(default="", description="ID for update or close actions.")
    opportunity_name: str = Field(default="", description="Name when adding.")
    expected_gain: float = Field(default=0, description="Net expected gain.")
    capital_required: float = Field(default=0, ge=0, description="Capital required.")
    days_to_realize: int = Field(default=30, ge=1, description="Days to realize gain.")
    velocity_score: float = Field(default=0, description="Pre-computed velocity score.")
    status: str = Field(default="researching", description="researching, executing, closed.")
    notes: str = Field(default="", description="Optional notes.")

    def run(self) -> str:
        action = self.action.lower().strip()
        pipeline = _load_pipeline()

        if action == "list":
            sorted_pipe = sorted(pipeline, key=lambda x: x.get("velocity_score", 0), reverse=True)
            return json.dumps({"count": len(sorted_pipe), "pipeline": sorted_pipe}, indent=2)

        if action == "add":
            if not self.opportunity_name:
                return json.dumps({"error": "opportunity_name required for add."})
            entry = {
                "id": str(uuid.uuid4())[:8],
                "name": self.opportunity_name,
                "expected_gain": self.expected_gain,
                "capital_required": self.capital_required,
                "days_to_realize": self.days_to_realize,
                "velocity_score": self.velocity_score,
                "status": self.status,
                "notes": self.notes,
            }
            pipeline.append(entry)
            _save_pipeline(pipeline)
            return json.dumps({"added": entry, "pipeline_path": str(_pipeline_path())}, indent=2)

        if action in ("update", "close"):
            if not self.opportunity_id:
                return json.dumps({"error": "opportunity_id required for update/close."})
            for item in pipeline:
                if item.get("id") == self.opportunity_id:
                    if action == "close":
                        item["status"] = "closed"
                    else:
                        if self.opportunity_name:
                            item["name"] = self.opportunity_name
                        if self.expected_gain:
                            item["expected_gain"] = self.expected_gain
                        if self.capital_required:
                            item["capital_required"] = self.capital_required
                        if self.velocity_score:
                            item["velocity_score"] = self.velocity_score
                        if self.status:
                            item["status"] = self.status
                        if self.notes:
                            item["notes"] = self.notes
                    _save_pipeline(pipeline)
                    return json.dumps({"updated": item}, indent=2)
            return json.dumps({"error": f"Opportunity {self.opportunity_id} not found."})

        return json.dumps({"error": "action must be add, update, list, or close."})


if __name__ == "__main__":
    tool = TrackArbitragePipeline(
        action="add",
        opportunity_name="Cancel unused SaaS stack",
        expected_gain=2400,
        capital_required=0,
        days_to_realize=7,
        velocity_score=125.7,
    )
    print(tool.run())
    print(TrackArbitragePipeline(action="list").run())
