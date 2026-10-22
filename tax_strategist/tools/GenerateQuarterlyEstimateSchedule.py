import json

from agency_swarm.tools import BaseTool
from pydantic import Field

QUARTERLY_DUE_DATES = [
    ("Q1", "April 15"),
    ("Q2", "June 15"),
    ("Q3", "September 15"),
    ("Q4", "January 15 (following year)"),
]


class GenerateQuarterlyEstimateSchedule(BaseTool):
    """
    Builds a quarterly estimated tax payment schedule with monthly reserve targets
    for self-employed US taxpayers.
    """

    projected_annual_net: float = Field(..., gt=0, description="Projected annual net self-employment income.")
    federal_withholding_ytd: float = Field(default=0, ge=0, description="Federal tax already paid/withheld YTD.")
    state_rate_pct: float = Field(default=5.0, ge=0, le=15, description="Estimated state effective tax rate.")
    prior_year_tax: float = Field(default=0, ge=0, description="Prior year total tax for safe harbor check.")
    estimated_federal_rate_pct: float = Field(default=22.0, ge=0, le=37, description="Estimated federal income tax bracket rate.")

    def run(self) -> str:
        taxable_se = self.projected_annual_net * 0.9235
        ss_tax = min(taxable_se, 176_100) * 0.124
        medicare_tax = taxable_se * 0.029
        se_tax = ss_tax + medicare_tax

        federal_income_tax = self.projected_annual_net * (self.estimated_federal_rate_pct / 100)
        state_tax = self.projected_annual_net * (self.state_rate_pct / 100)
        total_estimated_tax = se_tax + federal_income_tax + state_tax

        remaining = max(total_estimated_tax - self.federal_withholding_ytd, 0)
        quarterly_payment = remaining / 4
        monthly_set_aside = total_estimated_tax / 12

        safe_harbor_met = False
        if self.prior_year_tax > 0:
            safe_harbor_met = self.federal_withholding_ytd >= self.prior_year_tax * 0.9

        schedule = [
            {"quarter": q, "due_date": d, "estimated_payment": round(quarterly_payment, 2)}
            for q, d in QUARTERLY_DUE_DATES
        ]

        result = {
            "projected_annual_net": self.projected_annual_net,
            "estimated_se_tax": round(se_tax, 2),
            "estimated_federal_income_tax": round(federal_income_tax, 2),
            "estimated_state_tax": round(state_tax, 2),
            "total_estimated_annual_tax": round(total_estimated_tax, 2),
            "monthly_set_aside": round(monthly_set_aside, 2),
            "quarterly_payment": round(quarterly_payment, 2),
            "quarterly_schedule": schedule,
            "safe_harbor_met": safe_harbor_met,
            "profit_first_tax_pct_suggestion": round(monthly_set_aside / (self.projected_annual_net / 12) * 100, 1)
            if self.projected_annual_net > 0
            else 15,
            "note": "Educational estimate. Confirm amounts with CPA before paying.",
        }
        return json.dumps(result, indent=2)


if __name__ == "__main__":
    tool = GenerateQuarterlyEstimateSchedule(projected_annual_net=95000, state_rate_pct=5.0)
    print(tool.run())
