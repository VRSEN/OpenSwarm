import json
import math

from agency_swarm.tools import BaseTool
from pydantic import Field


class FundMicroInvestmentProject(BaseTool):
    """Structures $25/day micro-investment funding for 1-7 day payout projects."""

    project_name: str = Field(...)
    total_capital_needed: float = Field(..., gt=0)
    daily_micro_amount: float = Field(default=25, gt=0)
    expected_payout_days: int = Field(..., ge=1, le=7)
    expected_profit: float = Field(..., gt=0)
    gap_type: str = Field(default="skill")

    def run(self) -> str:
        days_to_fund = math.ceil(self.total_capital_needed / self.daily_micro_amount)
        total_days = days_to_fund + self.expected_payout_days
        velocity = (self.expected_profit / self.total_capital_needed) * (365 / total_days)

        go = self.expected_payout_days <= 7 and velocity >= 0.5

        schedule = [
            {"day": d, "invest": self.daily_micro_amount, "cumulative": min(d * self.daily_micro_amount, self.total_capital_needed)}
            for d in range(1, days_to_fund + 1)
        ]

        return json.dumps(
            {
                "project_name": self.project_name,
                "gap_type": self.gap_type,
                "total_capital_needed": self.total_capital_needed,
                "daily_micro_amount": self.daily_micro_amount,
                "days_to_fully_fund": days_to_fund,
                "expected_payout_days": self.expected_payout_days,
                "expected_profit": self.expected_profit,
                "funding_schedule": schedule,
                "projected_velocity": round(velocity, 3),
                "recommendation": "go" if go else "hold",
            },
            indent=2,
        )


if __name__ == "__main__":
    print(
        FundMicroInvestmentProject(
            project_name="Resell automation template",
            total_capital_needed=1500,
            daily_micro_amount=25,
            expected_payout_days=5,
            expected_profit=600,
            gap_type="skill",
        ).run()
    )
