import json

from agency_swarm.tools import BaseTool
from pydantic import Field


class AutomateStabilityFund(BaseTool):
    """Tracks 3-6 month Stability Fund and recommends auto-transfers from Future bucket."""

    monthly_essentials: float = Field(..., gt=0)
    stability_fund_balance: float = Field(..., ge=0)
    target_months: int = Field(default=4, ge=3, le=6)
    future_bucket_monthly: float = Field(..., ge=0)

    def run(self) -> str:
        target = self.monthly_essentials * self.target_months
        progress = (self.stability_fund_balance / target * 100) if target > 0 else 0
        shortfall = max(target - self.stability_fund_balance, 0)
        months_to_funded = shortfall / self.future_bucket_monthly if self.future_bucket_monthly > 0 else None
        auto_transfer = min(self.future_bucket_monthly, shortfall) if shortfall > 0 else 0

        return json.dumps(
            {
                "target_months": self.target_months,
                "target_amount": round(target, 2),
                "current_balance": self.stability_fund_balance,
                "progress_pct": round(progress, 1),
                "shortfall": round(shortfall, 2),
                "recommended_monthly_auto_transfer": round(auto_transfer, 2),
                "months_to_funded": round(months_to_funded, 1) if months_to_funded else 0,
                "stage_exit": progress >= 100,
            },
            indent=2,
        )


if __name__ == "__main__":
    print(
        AutomateStabilityFund(
            monthly_essentials=4500,
            stability_fund_balance=9000,
            target_months=4,
            future_bucket_monthly=1080,
        ).run()
    )
