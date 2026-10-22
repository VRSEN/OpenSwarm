import json

from agency_swarm.tools import BaseTool
from pydantic import Field

from backend.services.reputation_engine import EngagementRecord, score_behavioral_reliability


class AuditBehavioralReliability(BaseTool):
    """Pillar 1 — score follow-through on engagements and invoice timeliness."""

    engagements: list[dict] = Field(
        default_factory=list,
        description="{delivered, on_time, promised}",
    )
    invoice_on_time_rate_pct: float | None = Field(default=None, ge=0, le=100)
    subject_name: str = Field(default="user")

    def run(self) -> str:
        records = [
            EngagementRecord(
                delivered=e.get("delivered", False),
                on_time=e.get("on_time", False),
                promised=e.get("promised", ""),
            )
            for e in self.engagements
        ]
        score = score_behavioral_reliability(records, self.invoice_on_time_rate_pct)
        return json.dumps(
            {
                "subject_name": self.subject_name,
                "behavioral_trust_score": round(score, 1),
                "pillar": "behavioral_trust",
                "principle": "Predictability over excitement",
                "engagement_count": len(records),
            },
            indent=2,
        )


if __name__ == "__main__":
    print(
        AuditBehavioralReliability(
            engagements=[
                {"delivered": True, "on_time": True, "promised": "Invoice paid"},
                {"delivered": True, "on_time": False, "promised": "Project deadline"},
            ],
            invoice_on_time_rate_pct=90,
        ).run()
    )
