import json

from agency_swarm.tools import BaseTool
from pydantic import Field

from backend.services.omni_wealth import evaluate_move


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


class UnderwriteSmartMove(BaseTool):
    """Two-key underwrite for flips, trades, crypto, Kalshi, or other bets."""

    name: str = Field(...)
    move_type: str = Field(default="flip", description="flip, trade, crypto, kalshi, business_reinvest, equipment, acquisition, other")
    platform: str = Field(default="")
    capital_required: float = Field(..., ge=0)
    expected_profit: float = Field(default=0)
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
                "platform": self.platform,
                "capital_required": self.capital_required,
                "expected_profit": self.expected_profit,
                "max_loss": self.max_loss or self.capital_required,
                "recycle_days": self.recycle_days,
                "exit_plan": self.exit_plan,
            },
        )
        return json.dumps(packet, indent=2)


if __name__ == "__main__":
    print(
        UnderwriteSmartMove(
            name="30-day equipment flip",
            move_type="flip",
            capital_required=900,
            expected_profit=400,
            max_loss=200,
            exit_plan="Sell by day 21 or list at cost",
            monthly_gross_income=8000,
            monthly_essentials=4800,
            stability_fund_balance=12000,
        ).run()
    )
