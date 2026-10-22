import json

from agency_swarm.tools import BaseTool
from pydantic import Field

STAGES = ("Survival", "Stability", "Growth", "Sovereignty")

STAGE_EXIT = {
    "Survival": {"runway_months": 3, "next": "Stability"},
    "Stability": {"runway_months": 6, "next": "Growth"},
    "Growth": {"runway_months": 12, "next": "Sovereignty"},
    "Sovereignty": {"runway_months": 12, "next": None},
}


class GenerateSovereigntyRoadmap(BaseTool):
    """
    Creates a stage-by-stage mechanical plan from current state to the sovereignty number.
    """

    current_stage: str = Field(..., description="Survival, Stability, Growth, or Sovereignty.")
    monthly_expenses: float = Field(..., gt=0, description="Monthly lifestyle and business burn.")
    monthly_net_income: float = Field(..., gt=0, description="Average monthly net income.")
    sovereignty_number: float = Field(..., gt=0, description="Target investable net worth.")
    months_to_target: int = Field(default=60, ge=12, description="Planning horizon in months.")
    current_net_worth: float = Field(default=0, ge=0, description="Current investable net worth.")

    def run(self) -> str:
        if self.current_stage not in STAGES:
            return json.dumps({"error": f"current_stage must be one of {STAGES}."})

        min_sovereignty = self.monthly_expenses * 12 * 10
        if self.sovereignty_number < min_sovereignty:
            return json.dumps(
                {"error": f"sovereignty_number should exceed {min_sovereignty:.0f} (10x annual expenses)."}
            )

        monthly_surplus = max(self.monthly_net_income - self.monthly_expenses, 0)
        gap = max(self.sovereignty_number - self.current_net_worth, 0)
        months_at_surplus = gap / monthly_surplus if monthly_surplus > 0 else None

        milestones = []
        stage_order = list(STAGES)
        start_idx = stage_order.index(self.current_stage)

        for idx in range(start_idx, len(stage_order)):
            stage = stage_order[idx]
            exit_criteria = STAGE_EXIT[stage]
            milestones.append(
                {
                    "stage": stage,
                    "exit_criteria": f"Runway ≥ {exit_criteria['runway_months']} months",
                    "next_stage": exit_criteria["next"],
                    "mechanical_focus": _stage_focus(stage),
                }
            )

        monthly_mechanical = {
            "profit_first_split": {"profit": 5, "tax": 15, "owner_pay": 50, "opex": 30},
            "minimum_monthly_savings": round(monthly_surplus * 0.05, 2) if monthly_surplus > 0 else 0,
            "tax_reserve_monthly": round(self.monthly_net_income * 0.15, 2),
        }

        result = {
            "current_stage": self.current_stage,
            "sovereignty_number": self.sovereignty_number,
            "current_net_worth": self.current_net_worth,
            "gap_to_sovereignty": round(gap, 2),
            "monthly_surplus": round(monthly_surplus, 2),
            "estimated_months_to_sovereignty": round(months_at_surplus, 1) if months_at_surplus else "increase surplus",
            "milestones": milestones,
            "monthly_mechanical_targets": monthly_mechanical,
            "planning_horizon_months": self.months_to_target,
        }
        return json.dumps(result, indent=2)


def _stage_focus(stage: str) -> str:
    return {
        "Survival": "Profit First + cut burn + fund tax reserve",
        "Stability": "Emergency fund + tax reserve to 50%",
        "Growth": "Retirement accounts + tax reserve to 90%",
        "Sovereignty": "IPS execution + arbitrage pipeline",
    }[stage]


if __name__ == "__main__":
    tool = GenerateSovereigntyRoadmap(
        current_stage="Stability",
        monthly_expenses=4500,
        monthly_net_income=7500,
        sovereignty_number=900000,
        current_net_worth=45000,
    )
    print(tool.run())
