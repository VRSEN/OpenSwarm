import json

from agency_swarm.tools import BaseTool
from pydantic import Field

RISK_MULTIPLIERS = {"low": 1.0, "medium": 0.75, "high": 0.5}


class ScoreOpportunityVelocity(BaseTool):
    """
    Rates an arbitrage opportunity by expected gain, capital required, time to realize,
    and execution risk using a velocity score (ROI per day of capital deployment).
    """

    opportunity_name: str = Field(..., description="Short name for the opportunity.")
    expected_gain: float = Field(..., description="Net profit after all costs.")
    capital_required: float = Field(..., ge=0, description="Capital that must be deployed.")
    days_to_realize: int = Field(..., ge=1, description="Days until gain is realized.")
    execution_risk: str = Field(default="medium", description="low, medium, or high.")
    recurring: bool = Field(default=False, description="True if gain repeats (annualizes velocity).")

    def run(self) -> str:
        risk = self.execution_risk.lower().strip()
        if risk not in RISK_MULTIPLIERS:
            return json.dumps({"error": "execution_risk must be low, medium, or high."})

        if self.expected_gain <= 0:
            return json.dumps({"error": "expected_gain must be positive for scoring."})

        capital = max(self.capital_required, 1.0)
        roi = self.expected_gain / capital
        annualization = 365 / self.days_to_realize
        if self.recurring:
            annualization *= 12

        velocity = roi * annualization * RISK_MULTIPLIERS[risk]

        if velocity >= 2.0:
            tier = "A"
            recommendation = "go"
        elif velocity >= 0.5:
            tier = "B"
            recommendation = "research"
        else:
            tier = "C"
            recommendation = "no-go"

        result = {
            "opportunity_name": self.opportunity_name,
            "expected_gain": self.expected_gain,
            "capital_required": self.capital_required,
            "days_to_realize": self.days_to_realize,
            "execution_risk": risk,
            "recurring": self.recurring,
            "roi_pct": round(roi * 100, 2),
            "velocity_score": round(velocity, 3),
            "tier": tier,
            "recommendation": recommendation,
            "formula": "velocity = (gain/capital) × (365/days) × risk_multiplier",
        }
        return json.dumps(result, indent=2)


if __name__ == "__main__":
    tool = ScoreOpportunityVelocity(
        opportunity_name="Switch payment processor",
        expected_gain=800,
        capital_required=500,
        days_to_realize=14,
        execution_risk="low",
    )
    print(tool.run())
