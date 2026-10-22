import json

from agency_swarm.tools import BaseTool
from pydantic import Field

from backend.services.reputation_engine import (
    EngagementRecord,
    QuietBuilderInput,
    RarityInput,
    SelfTrustEvent,
    StrategyPersistenceInput,
    PressurePerformanceInput,
    compute_full_reputation,
    build_portable_summary,
)


class ExportPortableReputation(BaseTool):
    """Export travels-ahead reputation summary for new partnerships."""

    self_trust_events: list[dict] = Field(default_factory=list)
    engagements: list[dict] = Field(default_factory=list)
    steady_months: int = Field(default=0, ge=0)
    consumer_tag_count: int = Field(default=0, ge=0)
    acquirer_tag_count: int = Field(default=0, ge=0)

    def run(self) -> str:
        rep = compute_full_reputation(
            self_trust_events=[
                SelfTrustEvent(
                    kept_commitment=e.get("kept_commitment", False),
                    event_type=e.get("event_type", "check_in"),
                )
                for e in self.self_trust_events
            ],
            engagements=[
                EngagementRecord(
                    delivered=e.get("delivered", False),
                    on_time=e.get("on_time", False),
                )
                for e in self.engagements
            ],
            persistence=StrategyPersistenceInput(steady_months=self.steady_months),
            quiet_builder=QuietBuilderInput(
                consumer_tag_count=self.consumer_tag_count,
                acquirer_tag_count=self.acquirer_tag_count,
            ),
            rarity=RarityInput(discipline_score=min(self.steady_months * 8, 100)),
            pressure=PressurePerformanceInput(),
        )
        return json.dumps(
            {
                "export_format": "travels_ahead",
                "summary": rep["travels_ahead_summary"],
                "reputation_credit_score": rep["reputation_credit_score"],
                "tier": rep["tier"],
                "pillars": rep["pillars"],
                "rarity_score": rep["rarity"]["rarity_score"],
                "unlocks": rep["unlocks"],
                "portable_paragraph": build_portable_summary(
                    rep["reputation_credit_score"],
                    rep["tier"],
                    rep["pillars"],
                    rep["rarity"],
                ),
            },
            indent=2,
        )


if __name__ == "__main__":
    print(
        ExportPortableReputation(
            self_trust_events=[{"kept_commitment": True}, {"kept_commitment": True}],
            steady_months=12,
        ).run()
    )
