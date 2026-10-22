import json

from agency_swarm.tools import BaseTool
from pydantic import Field


STAGES = ("Survival", "Stability", "Growth", "Sovereignty")


class AssessFinancialStage(BaseTool):
    """
    Determines a self-employed user's financial stage (Survival → Sovereignty)
    from runway, cash flow, tax reserves, and debt inputs.
    """

    monthly_expenses: float = Field(..., description="Total monthly burn including minimum debt payments.")
    liquid_cash: float = Field(..., ge=0, description="Cash available across operating accounts.")
    monthly_net_income: float = Field(..., ge=0, description="Average net income over the last 3 months.")
    emergency_fund_target_months: int = Field(default=6, ge=1, description="Target runway months for emergency fund.")
    tax_reserve_balance: float = Field(default=0, ge=0, description="Current tax savings balance.")
    tax_reserve_target: float = Field(default=0, ge=0, description="Required tax reserve for the year.")
    high_interest_debt: float = Field(default=0, ge=0, description="Debt above 8% APR.")

    def run(self) -> str:
        if self.monthly_expenses <= 0:
            return json.dumps({"error": "monthly_expenses must be greater than 0."})

        runway_months = self.liquid_cash / self.monthly_expenses
        tax_reserve_pct = (
            (self.tax_reserve_balance / self.tax_reserve_target * 100)
            if self.tax_reserve_target > 0
            else 100.0
        )

        if runway_months < 3 or self.high_interest_debt > self.liquid_cash * 0.5:
            stage = "Survival"
        elif runway_months < 6:
            stage = "Stability"
        elif runway_months < 12 or tax_reserve_pct < 90:
            stage = "Growth"
        else:
            stage = "Sovereignty"

        gates = {
            "arbitrage": stage in ("Growth", "Sovereignty"),
            "investing": stage in ("Growth", "Sovereignty"),
            "arbitrage_cap_pct": 10 if stage == "Growth" else 25 if stage == "Sovereignty" else 0,
            "tax_reserve_pct": round(tax_reserve_pct, 1),
        }

        route_map = {
            "Survival": "Discipline Controller",
            "Stability": "Discipline Controller",
            "Growth": "Wealth Architect",
            "Sovereignty": "Arbitrage Scout",
        }

        actions = []
        if stage == "Survival":
            actions = [
                "Run Profit First split on every deposit immediately.",
                "Cut all non-essential recurring expenses.",
                f"Build runway from {runway_months:.1f} to 3+ months.",
                "Fund tax reserve before any discretionary spend.",
            ]
        elif stage == "Stability":
            actions = [
                "Maintain Profit First on all inflows.",
                f"Increase tax reserve from {tax_reserve_pct:.0f}% to 50%+ of target.",
                "Build emergency fund to 3 months expenses.",
            ]
        elif stage == "Growth":
            actions = [
                "Complete tax reserve to 90%+ of target.",
                "Open retirement account (SEP-IRA or Solo 401k).",
                "Deploy ≤ 10% liquid capital to A-tier arbitrage only.",
            ]
        else:
            actions = [
                "Maintain 12+ month runway.",
                "Execute investment policy per Wealth Architect.",
                "Deploy ≤ 25% liquid to high-velocity arbitrage pipeline.",
            ]

        result = {
            "stage": stage,
            "runway_months": round(runway_months, 2),
            "monthly_net_income": self.monthly_net_income,
            "tax_reserve_pct": round(tax_reserve_pct, 1),
            "gates": gates,
            "route_to_agent": route_map[stage],
            "recommended_actions": actions,
        }
        return json.dumps(result, indent=2)


if __name__ == "__main__":
    tool = AssessFinancialStage(
        monthly_expenses=4500,
        liquid_cash=9000,
        monthly_net_income=6000,
        tax_reserve_balance=1200,
        tax_reserve_target=8000,
        high_interest_debt=0,
    )
    print(tool.run())
