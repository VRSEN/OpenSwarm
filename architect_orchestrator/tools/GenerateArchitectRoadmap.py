import json

from agency_swarm.tools import BaseTool
from pydantic import Field

STAGES = ("Stability", "Skill Stacking", "Asset Acquisition", "Sovereignty")


class GenerateArchitectRoadmap(BaseTool):
    """Stage-by-stage mechanical roadmap aligned to Cash Flow Mastery."""

    current_stage: str = Field(...)
    monthly_essentials: float = Field(..., gt=0)
    monthly_gross_income: float = Field(..., gt=0)
    target_sovereignty_income: float = Field(..., gt=0)
    focus_season_months: int = Field(default=6, ge=1, le=12)

    def run(self) -> str:
        if self.current_stage not in STAGES:
            return json.dumps({"error": f"current_stage must be one of {STAGES}"})

        future_monthly = self.monthly_gross_income * 0.15
        essentials_monthly = self.monthly_gross_income * 0.65
        life_monthly = self.monthly_gross_income * 0.20

        milestones = []
        for stage in STAGES[STAGES.index(self.current_stage) :]:
            milestones.append(
                {
                    "stage": stage,
                    "exit_criteria": _exit(stage),
                    "primary_agent": _agent(stage),
                }
            )

        result = {
            "current_stage": self.current_stage,
            "monthly_156520_targets": {
                "future_15pct": round(future_monthly, 2),
                "essentials_65pct": round(essentials_monthly, 2),
                "life_20pct": round(life_monthly, 2),
            },
            "stability_fund_range_months": "3-6",
            "target_sovereignty_income": self.target_sovereignty_income,
            "solitude_mode": {
                "duration_months": self.focus_season_months,
                "purpose": "6-Month Focus Season—deep work over consumption",
            },
            "milestones": milestones,
        }
        return json.dumps(result, indent=2)


def _exit(stage: str) -> str:
    return {
        "Stability": "Stability Fund = 3-6 months essentials",
        "Skill Stacking": "Revenue/hour +20% vs baseline",
        "Asset Acquisition": "≥1 positive-spread asset",
        "Sovereignty": "Passive covers 100% essentials; Step-Up documented",
    }[stage]


def _agent(stage: str) -> str:
    return {
        "Stability": "Cash Flow Engineer",
        "Skill Stacking": "Leverage Strategist",
        "Asset Acquisition": "Opportunity Scanner",
        "Sovereignty": "Legacy Architect",
    }[stage]


if __name__ == "__main__":
    tool = GenerateArchitectRoadmap(
        current_stage="Stability",
        monthly_essentials=4500,
        monthly_gross_income=7200,
        target_sovereignty_income=5400,
    )
    print(tool.run())
