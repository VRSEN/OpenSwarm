import json

from agency_swarm.tools import BaseTool
from pydantic import Field


class ProjectSovereigntyNumber(BaseTool):
    """
    Calculates the investable net worth target for financial sovereignty
    and estimates years to reach it at a given savings rate.
    """

    annual_lifestyle_expenses: float = Field(..., gt=0, description="Annual personal lifestyle expenses.")
    safe_withdrawal_rate_pct: float = Field(default=4.0, ge=3.0, le=5.0, description="Safe withdrawal rate.")
    passive_income_monthly: float = Field(default=0, ge=0, description="Existing passive income per month.")
    business_sale_value: float = Field(default=0, ge=0, description="Optional expected business exit value.")
    current_net_worth: float = Field(default=0, ge=0, description="Current investable net worth.")
    monthly_savings_rate: float = Field(default=0, ge=0, description="Monthly amount saved toward sovereignty.")

    def run(self) -> str:
        annual_passive = self.passive_income_monthly * 12
        net_annual_need = max(self.annual_lifestyle_expenses - annual_passive, 0)
        swr = self.safe_withdrawal_rate_pct / 100
        sovereignty_number = net_annual_need / swr

        total_target = sovereignty_number + self.business_sale_value
        gap = max(total_target - self.current_net_worth, 0)

        years_to_target = None
        if self.monthly_savings_rate > 0:
            months = gap / self.monthly_savings_rate
            years_to_target = round(months / 12, 1)

        result = {
            "annual_lifestyle_expenses": self.annual_lifestyle_expenses,
            "passive_income_annual": round(annual_passive, 2),
            "net_annual_need": round(net_annual_need, 2),
            "safe_withdrawal_rate_pct": self.safe_withdrawal_rate_pct,
            "sovereignty_number": round(sovereignty_number, 2),
            "business_sale_value": self.business_sale_value,
            "total_target": round(total_target, 2),
            "current_net_worth": self.current_net_worth,
            "gap_to_sovereignty": round(gap, 2),
            "monthly_savings_rate": self.monthly_savings_rate,
            "estimated_years_to_sovereignty": years_to_target or "provide monthly_savings_rate",
            "formula": "sovereignty_number = (expenses - passive_income) / SWR",
        }
        return json.dumps(result, indent=2)


if __name__ == "__main__":
    tool = ProjectSovereigntyNumber(
        annual_lifestyle_expenses=72000,
        current_net_worth=85000,
        monthly_savings_rate=2500,
        passive_income_monthly=400,
    )
    print(tool.run())
