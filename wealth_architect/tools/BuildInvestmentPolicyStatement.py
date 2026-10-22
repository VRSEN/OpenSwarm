import json

from agency_swarm.tools import BaseTool
from pydantic import Field

ALLOCATIONS = {
    "Survival": {"conservative": {"cash": 100}, "moderate": {"cash": 100}, "aggressive": {"cash": 100}},
    "Stability": {
        "conservative": {"cash": 80, "bonds": 20},
        "moderate": {"cash": 70, "bonds": 20, "stocks": 10},
        "aggressive": {"cash": 60, "bonds": 20, "stocks": 20},
    },
    "Growth": {
        "conservative": {"cash": 20, "bonds": 40, "stocks": 35, "alternatives": 5},
        "moderate": {"cash": 10, "bonds": 30, "stocks": 50, "alternatives": 10},
        "aggressive": {"cash": 5, "bonds": 15, "stocks": 65, "alternatives": 15},
    },
    "Sovereignty": {
        "conservative": {"cash": 10, "bonds": 40, "stocks": 45, "alternatives": 5},
        "moderate": {"cash": 5, "bonds": 25, "stocks": 60, "alternatives": 10},
        "aggressive": {"cash": 5, "bonds": 10, "stocks": 75, "alternatives": 10},
    },
}


class BuildInvestmentPolicyStatement(BaseTool):
    """
    Drafts a stage-appropriate investment policy statement with asset allocation and rebalancing rules.
    """

    financial_stage: str = Field(..., description="Survival, Stability, Growth, or Sovereignty.")
    risk_tolerance: str = Field(default="moderate", description="conservative, moderate, or aggressive.")
    investment_horizon_years: int = Field(..., ge=1, description="Years until funds are needed.")
    liquid_investable_assets: float = Field(default=0, ge=0, description="Current liquid investable assets.")

    def run(self) -> str:
        stage = self.financial_stage.strip()
        risk = self.risk_tolerance.lower().strip()

        if stage not in ALLOCATIONS:
            return json.dumps({"error": "financial_stage must be Survival, Stability, Growth, or Sovereignty."})
        if risk not in ("conservative", "moderate", "aggressive"):
            return json.dumps({"error": "risk_tolerance must be conservative, moderate, or aggressive."})

        allocation = ALLOCATIONS[stage][risk]
        total = sum(allocation.values())
        if total != 100:
            return json.dumps({"error": "Internal allocation error—percentages do not sum to 100."})

        rebalancing = "annual" if stage in ("Survival", "Stability") else "semi-annual"
        max_drawdown = {"conservative": 10, "moderate": 20, "aggressive": 30}[risk]

        dollar_allocation = {
            asset: round(self.liquid_investable_assets * pct / 100, 2) for asset, pct in allocation.items()
        }

        result = {
            "financial_stage": stage,
            "risk_tolerance": risk,
            "investment_horizon_years": self.investment_horizon_years,
            "liquid_investable_assets": self.liquid_investable_assets,
            "allocation_pct": allocation,
            "allocation_dollars": dollar_allocation,
            "rebalancing_frequency": rebalancing,
            "max_drawdown_tolerance_pct": max_drawdown,
            "rules": [
                "No market investing in Survival stage.",
                "Rebalance when any asset class drifts > 5% from target.",
                "Tax-advantaged accounts funded before taxable brokerage.",
                "Arbitrage capital is separate from IPS allocation.",
            ],
            "note": "Educational IPS draft. Implement with fee-only advisor.",
        }
        return json.dumps(result, indent=2)


if __name__ == "__main__":
    tool = BuildInvestmentPolicyStatement(
        financial_stage="Growth",
        risk_tolerance="moderate",
        investment_horizon_years=15,
        liquid_investable_assets=45000,
    )
    print(tool.run())
