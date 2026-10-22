import json

from agency_swarm.tools import BaseTool
from pydantic import Field

from backend.services.spread_engine import calculate_net_spread, evaluate_fund_eligibility


class ApplyReputationSpreadGate(BaseTool):
    """Apply tier-based CoC adjustment and Fund Now eligibility (Self-Trust floor 60)."""

    asset_yield_pct: float = Field(..., ge=0)
    cost_of_capital_pct: float = Field(..., ge=0)
    friction_expenses_pct: float = Field(default=2.0, ge=0)
    reputation_tier: str = Field(default="Bronze")
    composite_score: float = Field(default=50.0, ge=0, le=100)
    self_trust_pillar: float = Field(default=50.0, ge=0, le=100)
    requested_fund_amount: float = Field(default=25.0, gt=0)

    def run(self) -> str:
        spread = calculate_net_spread(
            self.asset_yield_pct,
            self.cost_of_capital_pct,
            self.friction_expenses_pct,
            self.reputation_tier,
        )
        fund = evaluate_fund_eligibility(
            self.composite_score,
            self.self_trust_pillar,
            self.reputation_tier,
            self.requested_fund_amount,
        )
        return json.dumps({"spread": spread, "fund_eligibility": fund}, indent=2)


if __name__ == "__main__":
    print(
        ApplyReputationSpreadGate(
            asset_yield_pct=12,
            cost_of_capital_pct=6,
            reputation_tier="Gold",
            composite_score=78,
            self_trust_pillar=72,
            requested_fund_amount=100,
        ).run()
    )
