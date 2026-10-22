import json

from agency_swarm.tools import BaseTool
from pydantic import Field


class CalculateCashRunway(BaseTool):
    """
    Computes how many months a self-employed operator can survive at current burn
    without new income, including optional near-term expected income.
    """

    liquid_cash: float = Field(..., ge=0, description="Total liquid cash available.")
    monthly_burn: float = Field(..., gt=0, description="Monthly expenses including minimum debt payments.")
    expected_income_30d: float = Field(default=0, ge=0, description="Contracted or pipeline income in next 30 days.")

    def run(self) -> str:
        adjusted_cash = self.liquid_cash + self.expected_income_30d
        runway_months = adjusted_cash / self.monthly_burn
        days_until_zero = int(runway_months * 30)

        if runway_months < 3:
            status = "danger"
            action = "Survival mode: freeze non-essential spending, enforce Profit First on all inflows."
        elif runway_months < 6:
            status = "warning"
            action = "Stability mode: build runway to 6 months, fund tax reserve to 50%+."
        else:
            status = "safe"
            action = "Maintain discipline protocols; proceed with stage-appropriate wealth building."

        result = {
            "liquid_cash": self.liquid_cash,
            "expected_income_30d": self.expected_income_30d,
            "adjusted_cash": round(adjusted_cash, 2),
            "monthly_burn": self.monthly_burn,
            "runway_months": round(runway_months, 2),
            "days_until_zero": days_until_zero,
            "status": status,
            "recommended_action": action,
        }
        return json.dumps(result, indent=2)


if __name__ == "__main__":
    tool = CalculateCashRunway(liquid_cash=12000, monthly_burn=4500, expected_income_30d=3000)
    print(tool.run())
