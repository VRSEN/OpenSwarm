import json

from agency_swarm.tools import BaseTool
from pydantic import Field

from backend.services.omni_wealth import allocate_capital


class _Profile:
    monthly_gross_income = 0
    monthly_essentials = 0
    stability_fund_balance = 0
    stability_fund_target_months = 4


class AllocateCapitalWaterfall(BaseTool):
    """Split monthly cash into survival, tax, reserve, opportunity, and speculative pools."""

    monthly_gross_income: float = Field(..., ge=0)
    monthly_essentials: float = Field(..., ge=0)
    stability_fund_balance: float = Field(default=0, ge=0)
    stability_fund_target_months: int = Field(default=4, ge=3, le=6)

    def run(self) -> str:
        profile = _Profile()
        profile.monthly_gross_income = self.monthly_gross_income
        profile.monthly_essentials = self.monthly_essentials
        profile.stability_fund_balance = self.stability_fund_balance
        profile.stability_fund_target_months = self.stability_fund_target_months
        return json.dumps(allocate_capital(profile), indent=2)


if __name__ == "__main__":
    print(
        AllocateCapitalWaterfall(
            monthly_gross_income=8000,
            monthly_essentials=5000,
            stability_fund_balance=4000,
        ).run()
    )
