import json

from agency_swarm.tools import BaseTool
from pydantic import Field


class CalculateSpread(BaseTool):
    """Spread = Asset Yield - Cost of Capital - Friction. Pass if spread > 0."""

    asset_yield_pct: float = Field(..., ge=0)
    cost_of_capital_pct: float = Field(..., ge=0)
    friction_expenses_pct: float = Field(default=2.0, ge=0)
    asset_name: str = Field(default="asset")

    def run(self) -> str:
        spread = self.asset_yield_pct - self.cost_of_capital_pct - self.friction_expenses_pct
        return json.dumps(
            {
                "asset_name": self.asset_name,
                "asset_yield_pct": self.asset_yield_pct,
                "cost_of_capital_pct": self.cost_of_capital_pct,
                "friction_expenses_pct": self.friction_expenses_pct,
                "spread_pct": round(spread, 3),
                "pass": spread > 0,
                "recommendation": "proceed" if spread > 0 else "reject",
                "formula": "Spread = Yield - CoC - Friction",
            },
            indent=2,
        )


if __name__ == "__main__":
    print(CalculateSpread(asset_yield_pct=12, cost_of_capital_pct=6, asset_name="Rental unit").run())
