import json

from agency_swarm.tools import BaseTool
from pydantic import Field

from backend.services.reputation_engine import StrategyPersistenceInput, compute_strategy_persistence_score


class ScoreConsistencyOverIntensity(BaseTool):
    """Pillar 5 — ordinary actions repeated; timeline variance analysis."""

    steady_months: int = Field(default=0, ge=0)
    burst_gap_months: int = Field(default=0, ge=0)
    invisible_season_days: int = Field(default=0, ge=0)
    engagement_count: int = Field(default=0, ge=0)

    def run(self) -> str:
        score = compute_strategy_persistence_score(
            StrategyPersistenceInput(
                steady_months=self.steady_months,
                burst_gap_months=self.burst_gap_months,
                invisible_season_days=self.invisible_season_days,
            )
        )
        intensity_low_consistency = self.burst_gap_months >= 4 and self.steady_months < 6
        return json.dumps(
            {
                "consistency_score": round(score, 1),
                "pillar": "consistency",
                "intensity_with_low_consistency_flag": intensity_low_consistency,
                "recommendation": "monitor" if intensity_low_consistency else "stable",
            },
            indent=2,
        )


if __name__ == "__main__":
    print(ScoreConsistencyOverIntensity(steady_months=13, invisible_season_days=200).run())
