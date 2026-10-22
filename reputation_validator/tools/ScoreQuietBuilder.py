import json

from agency_swarm.tools import BaseTool
from pydantic import Field

from backend.services.reputation_engine import QuietBuilderInput, compute_quiet_builder_score


class ScoreQuietBuilder(BaseTool):
    """Pillar 4 — reward reinvesting into systems; penalize ego/status spend."""

    future_bucket_pct: float = Field(default=15.0, ge=0, le=100)
    life_ego_spend_pct: float = Field(default=0.0, ge=0)
    reinvest_ratio: float = Field(default=0.5, ge=0, le=1)
    consumer_tag_count: int = Field(default=0, ge=0)
    acquirer_tag_count: int = Field(default=0, ge=0)
    verified_delivery_count: int = Field(default=0, ge=0)

    def run(self) -> str:
        score = compute_quiet_builder_score(
            QuietBuilderInput(
                future_bucket_pct=self.future_bucket_pct,
                life_ego_spend_pct=self.life_ego_spend_pct,
                reinvest_ratio=self.reinvest_ratio,
                consumer_tag_count=self.consumer_tag_count,
                acquirer_tag_count=self.acquirer_tag_count,
                verified_delivery_count=self.verified_delivery_count,
            )
        )
        performer_risk = self.consumer_tag_count > self.acquirer_tag_count * 2
        return json.dumps(
            {
                "quiet_builder_score": round(score, 1),
                "pillar": "authenticity",
                "performer_risk_flag": performer_risk,
                "principle": "Truth scales better than performance",
            },
            indent=2,
        )


if __name__ == "__main__":
    print(ScoreQuietBuilder(consumer_tag_count=5, acquirer_tag_count=2, reinvest_ratio=0.7).run())
