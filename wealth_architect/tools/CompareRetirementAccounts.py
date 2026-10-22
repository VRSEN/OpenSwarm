import json

from agency_swarm.tools import BaseTool
from pydantic import Field

# 2026 contribution limits (approximate; verify annually)
SEP_IRA_LIMIT = 70_000
SOLO_401K_EMPLOYEE = 24_500
SOLO_401K_TOTAL = 70_000
TRADITIONAL_IRA_LIMIT = 7_000


class CompareRetirementAccounts(BaseTool):
    """
    Compares SEP-IRA, Solo 401(k), and Traditional IRA options for a self-employed user.
    """

    net_self_employment_income: float = Field(..., gt=0, description="Net self-employment income.")
    age: int = Field(..., ge=18, le=75, description="User age.")
    desired_annual_contribution: float = Field(..., ge=0, description="Desired annual contribution amount.")
    has_employees: bool = Field(default=False, description="True if business has W-2 employees other than owner.")

    def run(self) -> str:
        sep_max = min(self.net_self_employment_income * 0.25, SEP_IRA_LIMIT)
        solo_employee = min(SOLO_401K_EMPLOYEE, self.desired_annual_contribution)
        solo_employer = min(self.net_self_employment_income * 0.25, SOLO_401K_TOTAL - solo_employee)
        solo_max = min(solo_employee + solo_employer, SOLO_401K_TOTAL)
        trad_max = TRADITIONAL_IRA_LIMIT + (1000 if self.age >= 50 else 0)

        accounts = [
            {
                "type": "SEP-IRA",
                "max_contribution": round(sep_max, 2),
                "pros": ["Simple setup", "High contribution limit", "Low admin cost"],
                "cons": ["No employee deferral", "No loan option", "Employer-only contributions"],
                "best_for": "Solo operators wanting simplicity",
            },
            {
                "type": "Solo 401(k)",
                "max_contribution": round(solo_max, 2),
                "pros": ["Employee + employer contributions", "Possible loan option", "Roth option available"],
                "cons": ["More paperwork", "Form 5500-EZ if assets > threshold"],
                "best_for": "High earners maximizing contributions",
            },
            {
                "type": "Traditional IRA",
                "max_contribution": trad_max,
                "pros": ["Simple", "Low minimum"],
                "cons": ["Lowest limit", "Income limits for deduction if covered elsewhere"],
                "best_for": "Side income or supplemental savings",
            },
        ]

        if self.has_employees:
            recommendation = "SEP-IRA or full 401(k) plan—Solo 401(k) not available with employees."
        elif self.desired_annual_contribution > sep_max * 0.8:
            recommendation = "Solo 401(k)—maximizes contribution room via employee deferral + employer match."
        elif self.net_self_employment_income < 50000:
            recommendation = "SEP-IRA—simple setup with sufficient room at lower income levels."
        else:
            recommendation = "Solo 401(k) if you can contribute > $10k/year; otherwise SEP-IRA for simplicity."

        result = {
            "net_self_employment_income": self.net_self_employment_income,
            "age": self.age,
            "desired_annual_contribution": self.desired_annual_contribution,
            "has_employees": self.has_employees,
            "accounts": accounts,
            "recommendation": recommendation,
            "note": "Confirm with tax advisor. Limits are estimates for 2026.",
        }
        return json.dumps(result, indent=2)


if __name__ == "__main__":
    tool = CompareRetirementAccounts(
        net_self_employment_income=120000,
        age=38,
        desired_annual_contribution=25000,
    )
    print(tool.run())
