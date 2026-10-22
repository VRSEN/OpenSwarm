import json

from agency_swarm.tools import BaseTool
from pydantic import Field

from backend.services.reputation_engine import StrategyPersistenceInput, compute_strategy_persistence_score


class MeasureStrategyPersistence(BaseTool):
    """Pillar 5 — invisible years bonus; penalize identity restarts every ~6 months."""

    steady_months: int = Field(default=0, ge=0)
    restart_count: int = Field(default=0, ge=0)
    invisible_season_days: int = Field(default=0, ge=0)
    burst_gap_months: int = Field(default=0, ge=0)
    strategy_name: str = Field(default="primary strategy")

    def run(self) -> str:
        score = compute_strategy_persistence_score(
            StrategyPersistenceInput(
                steady_months=self.steady_months,
                restart_count=self.restart_count,
                invisible_season_days=self.invisible_season_days,
                burst_gap_months=self.burst_gap_months,
            )
        )
        collapse_risk = self.restart_count >= 2 and self.steady_months < 6
        return json.dumps(
            {
                "strategy_name": self.strategy_name,
                "consistency_score": round(score, 1),
                "pillar": "consistency",
                "invisible_years_bonus_days": self.invisible_season_days,
                "restart_penalty_count": self.restart_count,
                "performer_collapse_risk": collapse_risk,
            },
            indent=2,
        )


if __name__ == "__main__":
    print(MeasureStrategyPersistence(steady_months=14, invisible_season_days=180, restart_count=0).run())
