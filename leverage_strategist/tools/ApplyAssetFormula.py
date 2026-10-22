import json

from agency_swarm.tools import BaseTool
from pydantic import Field


class ApplyAssetFormula(BaseTool):
    """Full Asset Formula: PASS if Yield > CoC + Friction."""

    asset_name: str = Field(...)
    asset_yield_pct: float = Field(..., ge=0)
    cost_of_capital_pct: float = Field(..., ge=0)
    friction_expenses_pct: float = Field(default=2.0, ge=0)
    acquisition_cost: float = Field(..., gt=0)

    def run(self) -> str:
        min_yield = self.cost_of_capital_pct + self.friction_expenses_pct
        spread = self.asset_yield_pct - min_yield
        annual_profit = self.acquisition_cost * (spread / 100) if spread > 0 else 0

        return json.dumps(
            {
                "asset_name": self.asset_name,
                "acquisition_cost": self.acquisition_cost,
                "asset_yield_pct": self.asset_yield_pct,
                "minimum_required_yield_pct": round(min_yield, 3),
                "spread_pct": round(spread, 3),
                "verdict": "PASS" if spread > 0 else "REJECT",
                "estimated_annual_spread_profit": round(annual_profit, 2),
                "formula": "Asset Yield > Cost of Capital + Friction/Expenses",
            },
            indent=2,
        )


if __name__ == "__main__":
    print(
        ApplyAssetFormula(
            asset_name="Digital course IP",
            asset_yield_pct=35,
            cost_of_capital_pct=0,
            friction_expenses_pct=3,
            acquisition_cost=2000,
        ).run()
    )
