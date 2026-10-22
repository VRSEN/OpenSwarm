import json

from agency_swarm.tools import BaseTool
from pydantic import Field

STAGES = ("Stability", "Skill Stacking", "Asset Acquisition", "Sovereignty")

MODULE_GATES = {
    "Stability": ["156520", "stability_fund", "72_hour_pause", "behavior_mirror"],
    "Skill Stacking": ["invisible_gaps", "micro_investment", "income_density"],
    "Asset Acquisition": ["spread_calculator", "asset_formula", "acquisition_debt"],
    "Sovereignty": ["buy_borrow_die", "step_up_vault", "generational_transfer"],
}


class AssessArchitectStage(BaseTool):
    """Assesses Cash Flow Mastery stage and returns gate matrix plus routing."""

    monthly_essentials: float = Field(..., gt=0)
    stability_fund_balance: float = Field(..., ge=0)
    stability_fund_target_months: int = Field(default=4, ge=3, le=6)
    revenue_per_hour: float = Field(default=0, ge=0)
    baseline_revenue_per_hour: float = Field(default=0, ge=0)
    positive_spread_assets: int = Field(default=0, ge=0)
    passive_covers_essentials_pct: float = Field(default=0, ge=0, le=100)
    solitude_mode_active: bool = Field(default=False)

    def run(self) -> str:
        target = self.monthly_essentials * self.stability_fund_target_months
        fund_pct = (self.stability_fund_balance / target * 100) if target > 0 else 0

        density_improvement = 0.0
        if self.baseline_revenue_per_hour > 0 and self.revenue_per_hour > 0:
            density_improvement = (
                (self.revenue_per_hour - self.baseline_revenue_per_hour)
                / self.baseline_revenue_per_hour
                * 100
            )

        if fund_pct < 100:
            stage = "Stability"
        elif density_improvement < 20:
            stage = "Skill Stacking"
        elif self.positive_spread_assets < 1:
            stage = "Asset Acquisition"
        elif self.passive_covers_essentials_pct < 100:
            stage = "Asset Acquisition"
        else:
            stage = "Sovereignty"

        unlocked = []
        invisible = []
        for s, modules in MODULE_GATES.items():
            idx = STAGES.index(s)
            if STAGES.index(stage) >= idx:
                unlocked.extend(modules)
            else:
                invisible.extend(modules)

        route_map = {
            "Stability": "Cash Flow Engineer",
            "Skill Stacking": "Leverage Strategist",
            "Asset Acquisition": "Opportunity Scanner",
            "Sovereignty": "Legacy Architect",
        }

        result = {
            "stage": stage,
            "stability_fund_target": round(target, 2),
            "stability_fund_balance": self.stability_fund_balance,
            "stability_fund_pct": round(fund_pct, 1),
            "income_density_improvement_pct": round(density_improvement, 1),
            "positive_spread_assets": self.positive_spread_assets,
            "passive_covers_essentials_pct": self.passive_covers_essentials_pct,
            "unlocked_modules": list(dict.fromkeys(unlocked)),
            "intentionally_invisible_modules": list(dict.fromkeys(invisible)),
            "route_to_agent": route_map[stage],
            "solitude_mode_active": self.solitude_mode_active,
            "next_mechanical_action": _next_action(stage, fund_pct),
        }
        return json.dumps(result, indent=2)


def _next_action(stage: str, fund_pct: float) -> str:
    actions = {
        "Stability": f"Fund Stability Fund ({fund_pct:.0f}% complete)—run 15/65/20 on next inflow.",
        "Skill Stacking": "Invest skill hours to raise revenue-per-hour by 20% vs baseline.",
        "Asset Acquisition": "Acquire one asset where Asset Yield > Cost of Capital + Friction.",
        "Sovereignty": "Document Step-Up in Basis in Sovereign Vault; maintain spread-positive portfolio.",
    }
    return actions[stage]


if __name__ == "__main__":
    tool = AssessArchitectStage(
        monthly_essentials=4500,
        stability_fund_balance=9000,
        revenue_per_hour=85,
        baseline_revenue_per_hour=70,
    )
    print(tool.run())
