import json

from agency_swarm.tools import BaseTool
from pydantic import Field


class ScoreMoneyVelocity(BaseTool):
    """
    Money Velocity = (profit / capital) × (365 / days) × recycle_count.
    Tracks recycle speed, not volume.
    """

    capital_deployed: float = Field(..., gt=0)
    profit_returned: float = Field(...)
    days_to_recycle: int = Field(..., ge=1)
    recycle_count: int = Field(default=1, ge=1)

    def run(self) -> str:
        roi = self.profit_returned / self.capital_deployed
        velocity = roi * (365 / self.days_to_recycle) * self.recycle_count
        volume_roi = self.profit_returned / self.capital_deployed * 100

        tier = "A" if velocity >= 2 else "B" if velocity >= 0.5 else "C"

        return json.dumps(
            {
                "money_velocity_score": round(velocity, 3),
                "volume_roi_pct": round(volume_roi, 2),
                "recycle_count": self.recycle_count,
                "days_to_recycle": self.days_to_recycle,
                "tier": tier,
                "insight": "Velocity prioritizes how fast capital returns and redeploys—not headline profit.",
                "formula": "velocity = (profit/capital) × (365/days) × recycle_count",
            },
            indent=2,
        )


if __name__ == "__main__":
    print(ScoreMoneyVelocity(capital_deployed=25, profit_returned=45, days_to_recycle=3, recycle_count=2).run())
