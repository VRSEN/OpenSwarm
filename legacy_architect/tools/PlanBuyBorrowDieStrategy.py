import json

from agency_swarm.tools import BaseTool
from pydantic import Field


class PlanBuyBorrowDieStrategy(BaseTool):
    """Outlines Buy-Borrow-Die sequence for appreciating assets."""

    assets: list[dict] = Field(..., description="List of {name, fmv, basis, annual_appreciation_pct}")
    borrowing_capacity_pct: float = Field(default=50, ge=0, le=80)
    estate_planning_goal: str = Field(default="step_up_for_heirs")

    def run(self) -> str:
        if not self.assets:
            return json.dumps({"error": "At least one asset required"})

        phases = []
        total_fmv = sum(float(a.get("fmv", 0)) for a in self.assets)
        total_basis = sum(float(a.get("basis", 0)) for a in self.assets)

        for asset in self.assets:
            fmv = float(asset.get("fmv", 0))
            borrow_capacity = fmv * (self.borrowing_capacity_pct / 100)
            phases.append(
                {
                    "asset": asset.get("name"),
                    "phase_buy": f"Acquire/hold {asset.get('name')}—basis ${asset.get('basis', 0):,.0f}",
                    "phase_borrow": f"Borrow up to ${borrow_capacity:,.0f} against FMV ({self.borrowing_capacity_pct}% LTV)",
                    "phase_die": "Heirs receive step-up in basis at death—capital gains minimized",
                }
            )

        return json.dumps(
            {
                "estate_planning_goal": self.estate_planning_goal,
                "total_fmv": round(total_fmv, 2),
                "total_basis": round(total_basis, 2),
                "total_step_up_potential": round(total_fmv - total_basis, 2),
                "phases_by_asset": phases,
                "disclaimer": "Requires estate attorney and tax professional review.",
            },
            indent=2,
        )


if __name__ == "__main__":
    print(
        PlanBuyBorrowDieStrategy(
            assets=[
                {"name": "Rental A", "fmv": 320000, "basis": 185000, "annual_appreciation_pct": 4},
            ],
        ).run()
    )
