import json

from agency_swarm.tools import BaseTool
from pydantic import Field

from backend.services.omni_wealth import allocate_capital, evaluate_move


class _Profile:
    monthly_gross_income = 0
    monthly_essentials = 0
    stability_fund_balance = 0
    stability_fund_target_months = 4
    debts_json = "[]"
    credit_snapshot_json = "{}"
    wealth_state_json = "{}"
    north_star_json = "{}"
    opportunities_json = "[]"


class BuildKillCase(BaseTool):
    """Adversarial kill-case for a proposed smart move."""

    name: str = Field(..., description="Name of the bet or deal")
    move_type: str = Field(default="other", description="flip, trade, crypto, kalshi, business_reinvest, equipment, acquisition, other")
    capital_required: float = Field(..., ge=0)
    max_loss: float = Field(default=0, ge=0)
    recycle_days: int = Field(default=14, ge=1)
    exit_plan: str = Field(default="")
    monthly_gross_income: float = Field(default=0, ge=0)
    monthly_essentials: float = Field(default=0, ge=0)
    stability_fund_balance: float = Field(default=0, ge=0)

    def run(self) -> str:
        profile = _Profile()
        profile.monthly_gross_income = self.monthly_gross_income
        profile.monthly_essentials = self.monthly_essentials
        profile.stability_fund_balance = self.stability_fund_balance
        packet = evaluate_move(
            profile,
            {
                "name": self.name,
                "move_type": self.move_type,
                "capital_required": self.capital_required,
                "max_loss": self.max_loss or self.capital_required,
                "recycle_days": self.recycle_days,
                "exit_plan": self.exit_plan,
            },
        )
        alloc = allocate_capital(profile)
        return json.dumps(
            {
                "kill_case": packet["kill_case"],
                "verdict": packet["verdict"],
                "risk_budget": alloc["risk_budget"],
                "assurance": packet["assurance"],
            },
            indent=2,
        )


if __name__ == "__main__":
    print(
        BuildKillCase(
            name="Demo Kalshi",
            move_type="kalshi",
            capital_required=400,
            max_loss=400,
            monthly_gross_income=8000,
            monthly_essentials=5000,
            stability_fund_balance=2000,
        ).run()
    )
