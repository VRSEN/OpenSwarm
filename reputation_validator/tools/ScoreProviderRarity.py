import json

from agency_swarm.tools import BaseTool
from pydantic import Field

from backend.services.reputation_engine import RarityInput, compute_rarity_score


class ScoreProviderRarity(BaseTool):
    """Pillar 4 — RARITY = skill depth × discipline / visibility inflation."""

    skill_depth_score: float = Field(default=50.0, ge=0, le=100)
    discipline_score: float = Field(default=50.0, ge=0, le=100)
    visibility_inflation_factor: float = Field(default=1.0, ge=0.5)
    social_visibility_score: float = Field(default=50.0, ge=0, le=100)
    verified_delivery_count: int = Field(default=0, ge=0)

    def run(self) -> str:
        inflation = self.visibility_inflation_factor
        if self.social_visibility_score > 70 and self.verified_delivery_count < 3:
            inflation = max(inflation, 1.5 + (self.social_visibility_score - 70) / 30)

        result = compute_rarity_score(
            RarityInput(
                skill_depth_score=self.skill_depth_score,
                discipline_score=self.discipline_score,
                visibility_inflation_factor=inflation,
            )
        )
        result["performer_risk"] = inflation > 1.5
        return json.dumps(result, indent=2)


if __name__ == "__main__":
    print(ScoreProviderRarity(skill_depth_score=80, discipline_score=75, social_visibility_score=90, verified_delivery_count=1).run())
