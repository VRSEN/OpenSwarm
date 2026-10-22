import json

from agency_swarm.tools import BaseTool
from pydantic import Field


class ModelIncomeDensity(BaseTool):
    """Models Skill Stacking ROI—income per hour improvement."""

    current_revenue_per_hour: float = Field(..., gt=0)
    hours_invested_in_skill: float = Field(..., gt=0)
    skill_cost: float = Field(..., ge=0)
    projected_revenue_per_hour: float = Field(..., gt=0)
    months_to_realize: int = Field(default=3, ge=1)

    def run(self) -> str:
        density_delta_pct = (
            (self.projected_revenue_per_hour - self.current_revenue_per_hour)
            / self.current_revenue_per_hour
            * 100
        )
        skill_stacking_exit = density_delta_pct >= 20
        hourly_gain = self.projected_revenue_per_hour - self.current_revenue_per_hour
        roi = (
            (hourly_gain * self.hours_invested_in_skill * 12) / self.skill_cost * 100
            if self.skill_cost > 0
            else float("inf")
        )

        return json.dumps(
            {
                "current_revenue_per_hour": self.current_revenue_per_hour,
                "projected_revenue_per_hour": self.projected_revenue_per_hour,
                "density_improvement_pct": round(density_delta_pct, 2),
                "skill_stacking_stage_exit_met": skill_stacking_exit,
                "hours_invested": self.hours_invested_in_skill,
                "skill_cost": self.skill_cost,
                "months_to_realize": self.months_to_realize,
                "projected_skill_roi_pct": round(roi, 2) if roi != float("inf") else "infinite",
            },
            indent=2,
        )


if __name__ == "__main__":
    print(
        ModelIncomeDensity(
            current_revenue_per_hour=75,
            hours_invested_in_skill=40,
            skill_cost=500,
            projected_revenue_per_hour=95,
        ).run()
    )
