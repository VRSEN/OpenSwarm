import json

from agency_swarm.tools import BaseTool
from pydantic import Field


class TrackMoneyVelocityDashboard(BaseTool):
    """Aggregates Money Velocity metrics for the Velocity Tracker."""

    velocity_records: list[dict] = Field(default_factory=list)
    period_days: int = Field(default=30, ge=1)

    def run(self) -> str:
        if not self.velocity_records:
            return json.dumps({"error": "Provide velocity_records from Opportunity Scanner pipeline"})

        scores = [float(r.get("velocity_score", r.get("money_velocity_score", 0))) for r in self.velocity_records]
        recycles = [int(r.get("recycle_count", 1)) for r in self.velocity_records]
        avg_velocity = sum(scores) / len(scores) if scores else 0
        avg_recycle = sum(recycles) / len(recycles) if recycles else 0

        top = sorted(self.velocity_records, key=lambda x: x.get("velocity_score", 0), reverse=True)[:3]

        return json.dumps(
            {
                "period_days": self.period_days,
                "avg_money_velocity": round(avg_velocity, 3),
                "avg_recycle_count": round(avg_recycle, 2),
                "projects_tracked": len(self.velocity_records),
                "top_velocity_projects": top,
                "insight": "Track recycle speed—not transaction volume.",
            },
            indent=2,
        )


if __name__ == "__main__":
    print(
        TrackMoneyVelocityDashboard(
            velocity_records=[
                {"name": "Template flip", "velocity_score": 12.5, "recycle_count": 2},
                {"name": "Vendor switch", "velocity_score": 8.1, "recycle_count": 1},
            ],
        ).run()
    )
