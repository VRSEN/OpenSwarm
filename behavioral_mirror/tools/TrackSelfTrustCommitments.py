import json

from agency_swarm.tools import BaseTool
from pydantic import Field

from backend.services.reputation_engine import SelfTrustEvent, compute_self_trust_index


class TrackSelfTrustCommitments(BaseTool):
    """Log and score private self-commitments for the Self-Trust Index (Pillar 2)."""

    action: str = Field(default="score", description="score|log")
    events: list[dict] = Field(
        default_factory=list,
        description="List of {kept_commitment, event_type, weight}",
    )
    benchmark_type: str = Field(default="rhythm", description="rhythm|financial_machine|focus_season|operator_standard")
    description: str = Field(default="", description="Commitment description when action=log")

    def run(self) -> str:
        dto_events = [
            SelfTrustEvent(
                kept_commitment=e.get("kept_commitment", False),
                event_type=e.get("event_type", "check_in"),
                weight=float(e.get("weight", 1.0)),
            )
            for e in self.events
        ]
        result = compute_self_trust_index(dto_events)
        result["action"] = self.action
        if self.action == "log" and self.description:
            result["logged_commitment"] = {
                "benchmark_type": self.benchmark_type,
                "description": self.description,
            }
            result["note"] = "Persist via POST /reputation/self-commitments for full tracking."
        result["self_trust_floor"] = 60
        result["blocks_fund_now_if_below"] = result["self_trust_index"] < 60
        return json.dumps(result, indent=2)


if __name__ == "__main__":
    print(
        TrackSelfTrustCommitments(
            events=[
                {"kept_commitment": True, "event_type": "pause_honored"},
                {"kept_commitment": True, "event_type": "check_in"},
                {"kept_commitment": False, "event_type": "pause_broken"},
            ]
        ).run()
    )
