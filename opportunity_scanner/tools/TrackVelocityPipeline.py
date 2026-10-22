import json
import uuid
from pathlib import Path

from agency_swarm.tools import BaseTool
from pydantic import Field

PIPELINE_FILE = "velocity_pipeline.json"


class TrackVelocityPipeline(BaseTool):
    """Local pipeline of velocity-ranked projects with recycle tracking."""

    action: str = Field(..., description="add, update, list, or recycle")
    project_name: str = Field(default="")
    capital_deployed: float = Field(default=0, ge=0)
    profit_returned: float = Field(default=0)
    velocity_score: float = Field(default=0)
    recycle_count: int = Field(default=1, ge=1)
    project_id: str = Field(default="")
    gap_type: str = Field(default="")

    def _path(self) -> Path:
        p = Path(__file__).resolve().parent.parent / "files"
        p.mkdir(parents=True, exist_ok=True)
        return p / PIPELINE_FILE

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
        pipeline = self._load()

        if action == "list":
            sorted_p = sorted(pipeline, key=lambda x: x.get("velocity_score", 0), reverse=True)
            return json.dumps({"count": len(sorted_p), "pipeline": sorted_p}, indent=2)

        if action == "add":
            entry = {
                "id": str(uuid.uuid4())[:8],
                "name": self.project_name,
                "gap_type": self.gap_type,
                "capital_deployed": self.capital_deployed,
                "profit_returned": self.profit_returned,
                "velocity_score": self.velocity_score,
                "recycle_count": self.recycle_count,
            }
            pipeline.append(entry)
            self._save(pipeline)
            return json.dumps({"added": entry}, indent=2)

        if action == "recycle" and self.project_id:
            for item in pipeline:
                if item.get("id") == self.project_id:
                    item["recycle_count"] = item.get("recycle_count", 1) + 1
                    if self.profit_returned:
                        item["profit_returned"] = item.get("profit_returned", 0) + self.profit_returned
                    if self.velocity_score:
                        item["velocity_score"] = self.velocity_score
                    self._save(pipeline)
                    return json.dumps({"recycled": item}, indent=2)
            return json.dumps({"error": "Project not found"})

        return json.dumps({"error": "Invalid action or missing project_id"})


if __name__ == "__main__":
    print(
        TrackVelocityPipeline(
            action="add",
            project_name="Template flip",
            capital_deployed=150,
            profit_returned=80,
            velocity_score=12.5,
            gap_type="skill",
        ).run()
    )
