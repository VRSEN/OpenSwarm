import json

from agency_swarm.tools import BaseTool
from pydantic import Field


class ValidateAcquisitionDebt(BaseTool):
    """Approves acquisition debt only; denies ego and consumption debt."""

    debt_purpose: str = Field(...)
    purpose_category: str = Field(..., description="acquisition, ego, consumption, or cash_flow")
    amount: float = Field(..., gt=0)
    asset_yield_pct: float = Field(default=0, ge=0)
    cost_of_capital_pct: float = Field(default=0, ge=0)

    def run(self) -> str:
        cat = self.purpose_category.lower().strip()
        if cat not in ("acquisition", "ego", "consumption", "cash_flow"):
            return json.dumps({"error": "Invalid purpose_category"})

        if cat in ("ego", "consumption"):
            return json.dumps(
                {
                    "verdict": "denied",
                    "reason": f"Debt for {cat} violates acquisition-only rule.",
                    "mirror_message": "This purchase performs success—it does not build it.",
                    "route_to": "Behavioral Mirror",
                },
                indent=2,
            )

        if cat == "acquisition":
            spread = self.asset_yield_pct - self.cost_of_capital_pct - 2.0
            if spread <= 0:
                return json.dumps(
                    {
                        "verdict": "denied",
                        "reason": "Acquisition debt fails Asset Formula—spread not positive after friction.",
                        "spread_pct": round(spread, 3),
                    },
                    indent=2,
                )
            return json.dumps(
                {
                    "verdict": "approved",
                    "amount": self.amount,
                    "purpose": self.debt_purpose,
                    "spread_pct": round(spread, 3),
                    "rule": "Debt for acquisition only—never ego.",
                },
                indent=2,
            )

        return json.dumps(
            {"verdict": "review", "reason": "Cash-flow debt requires Cash Flow Engineer runway check."},
            indent=2,
        )


if __name__ == "__main__":
    print(
        ValidateAcquisitionDebt(
            debt_purpose="Luxury watch",
            purpose_category="ego",
            amount=8000,
        ).run()
    )
