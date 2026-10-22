"""Assess user's Cash Flow Mastery stage from profile numbers."""

from __future__ import annotations

STAGES = (
    "Stability",
    "Skill Stacking",
    "Asset Acquisition",
    "System Scaling",
    "Sovereignty",
)

STAGE_DESCRIPTIONS = {
    "Stability": "Build your 3–6 month Stability Fund and run the 15/65/20 machine.",
    "Skill Stacking": "Raise income density—earn more per hour of effort.",
    "Asset Acquisition": "Turn active income into systems and spread-positive assets.",
    "System Scaling": "Recycle capital through vetted opportunities (advanced—unlocks later).",
    "Sovereignty": "Passive yield covers essentials; protect freedom long-term.",
}


def assess_stage(
    *,
    monthly_essentials: float,
    stability_fund_balance: float,
    stability_fund_target_months: int = 4,
    revenue_per_hour: float = 0,
    baseline_revenue_per_hour: float = 0,
    positive_spread_assets: int = 0,
    passive_covers_essentials_pct: float = 0,
) -> dict:
    target = monthly_essentials * stability_fund_target_months
    fund_pct = (stability_fund_balance / target * 100) if target > 0 else 0

    density_improvement = 0.0
    if baseline_revenue_per_hour > 0 and revenue_per_hour > 0:
        density_improvement = (
            (revenue_per_hour - baseline_revenue_per_hour) / baseline_revenue_per_hour * 100
        )

    if fund_pct < 100:
        stage = "Stability"
    elif density_improvement < 20:
        stage = "Skill Stacking"
    elif positive_spread_assets < 1:
        stage = "Asset Acquisition"
    elif passive_covers_essentials_pct < 100:
        stage = "Asset Acquisition"
    else:
        stage = "Sovereignty"

    return {
        "stage": stage,
        "stage_index": STAGES.index(stage) + 1,
        "total_stages": len(STAGES),
        "stage_description": STAGE_DESCRIPTIONS[stage],
        "stability_fund_target": round(target, 2),
        "stability_fund_balance": stability_fund_balance,
        "stability_fund_pct": round(fund_pct, 1),
        "income_density_improvement_pct": round(density_improvement, 1),
        "next_mechanical_action": _next_action(stage, fund_pct),
        "allocation_preview": _allocation_preview(monthly_essentials * 1.15 if monthly_essentials else 0),
    }


def _next_action(stage: str, fund_pct: float) -> str:
    actions = {
        "Stability": f"Keep funding your Stability Fund ({fund_pct:.0f}% of target). Every inflow gets split 15/65/20 before you spend.",
        "Skill Stacking": "Pick one skill that raises what you earn per hour. Track baseline vs now—you need +20% to graduate this stage.",
        "Asset Acquisition": "Build or buy one asset where yield beats cost of capital plus friction—a system, not more hours.",
        "System Scaling": "Advanced capital recycling unlocks here later. Focus on one spread-positive asset first.",
        "Sovereignty": "Maintain systems that cover essentials without your daily presence. Document legacy plans when ready.",
    }
    return actions.get(stage, actions["Stability"])


def _allocation_preview(gross_monthly: float) -> dict:
    if gross_monthly <= 0:
        return {"future": 0, "essentials": 0, "life": 0}
    return {
        "future": round(gross_monthly * 0.15, 2),
        "essentials": round(gross_monthly * 0.65, 2),
        "life": round(gross_monthly * 0.20, 2),
        "labels": {
            "future": "Future (15%) — Stability Fund, debt snowball, investments",
            "essentials": "Essentials (65%) — rent, food, insurance, business costs",
            "life": "Life (20%) — discretionary; pause before spending",
        },
    }
