import json

from agency_swarm.tools import BaseTool
from pydantic import Field

from backend.services.reputation_engine import (
    EngagementRecord,
    PressurePerformanceInput,
    QuietBuilderInput,
    RarityInput,
    SelfTrustEvent,
    StrategyPersistenceInput,
    compute_full_reputation,
)


class GenerateVettingReport(BaseTool):
    """Full five-pillar vetting report for UI and Fund Now gates."""

    subject_name: str = Field(default="provider")
    engagements: list[dict] = Field(default_factory=list)
    self_trust_events: list[dict] = Field(default_factory=list)
    crisis_events: int = Field(default=0, ge=0)
    crisis_passed: int = Field(default=0, ge=0)
    steady_months: int = Field(default=0, ge=0)
    consumer_tag_count: int = Field(default=0, ge=0)
    acquirer_tag_count: int = Field(default=0, ge=0)
    skill_depth_score: float = Field(default=50.0, ge=0, le=100)

    def run(self) -> str:
        rep = compute_full_reputation(
            engagements=[
                EngagementRecord(
                    delivered=e.get("delivered", False),
                    on_time=e.get("on_time", False),
                )
                for e in self.engagements
            ],
            self_trust_events=[
                SelfTrustEvent(kept_commitment=e.get("kept_commitment", False))
                for e in self.self_trust_events
            ],
            pressure=PressurePerformanceInput(
                crisis_events=self.crisis_events,
                crisis_passed=self.crisis_passed,
            ),
            quiet_builder=QuietBuilderInput(
                consumer_tag_count=self.consumer_tag_count,
                acquirer_tag_count=self.acquirer_tag_count,
            ),
            rarity=RarityInput(
                skill_depth_score=self.skill_depth_score,
                discipline_score=min(self.steady_months * 8, 100),
            ),
            persistence=StrategyPersistenceInput(steady_months=self.steady_months),
        )
        return json.dumps(
            {
                "subject_name": self.subject_name,
                "vetting_report": {
                    "composite_score": rep["reputation_credit_score"],
                    "tier": rep["tier"],
                    "five_pillars": rep["pillars"],
                    "rarity": rep["rarity"],
                    "fund_now_eligible": rep["fund_now_eligible"],
                    "block_reason": rep.get("fund_now_block_reason"),
                    "unlocks": rep["unlocks"],
                },
                "travels_ahead_summary": rep["travels_ahead_summary"],
            },
            indent=2,
        )


if __name__ == "__main__":
    print(
        GenerateVettingReport(
            subject_name="QuickDev LLC",
            engagements=[{"delivered": True, "on_time": True}],
            self_trust_events=[{"kept_commitment": True}] * 5,
            steady_months=10,
        ).run()
    )
