"""Weekly quick wins and stage-gated opportunity cards."""

from __future__ import annotations

import json
from typing import Any

from backend.services.financial_intake import build_financial_summary
from backend.services.journey_engine import assess_stage


def _scan_opportunities(capital: float, skills: list[str], stability_pct: float) -> list[dict]:
    if stability_pct < 50:
        return [
            {
                "title": "High-yield savings move",
                "type": "stability",
                "capital_required": 0,
                "days_to_payout": 0,
                "action": "Open or move Future bucket to a high-yield savings (4%+ APY) — zero risk cushion boost.",
                "gated": False,
            },
            {
                "title": "Skill micro-offer",
                "type": "skill",
                "capital_required": 0,
                "days_to_payout": 7,
                "action": f"Package one {skills[0] if skills else 'core'} skill as a fixed-price offer this week.",
                "gated": False,
            },
        ]

    gaps = [
        {
            "title": "Vendor pricing arbitrage",
            "type": "convenience",
            "capital_required": min(capital, 200),
            "days_to_payout": 7,
            "action": "Buy wholesale / resell retail in a niche you know — validate spread before scaling.",
            "gated": False,
        },
        {
            "title": "Government small-business grants",
            "type": "information",
            "capital_required": 0,
            "days_to_payout": 30,
            "action": "Search SBA + state grant portals for your trade; many are under-applied.",
            "gated": False,
        },
    ]
    if stability_pct >= 100:
        gaps.append(
            {
                "title": "Invisible gap scan (full)",
                "type": "arbitrage",
                "capital_required": min(capital, 500),
                "days_to_payout": 7,
                "action": "Run Opportunity Scanner on convenience + skill gaps with verified spread.",
                "gated": False,
            }
        )
    else:
        gaps.append(
            {
                "title": "Capital flip (locked)",
                "type": "arbitrage",
                "capital_required": capital,
                "days_to_payout": 7,
                "action": "Unlocks when Stability Fund ≥ 50% — protect cushion first.",
                "gated": True,
            }
        )
    return gaps


def build_quick_wins(profile) -> dict[str, Any]:
    summary = build_financial_summary(profile)
    journey = assess_stage(
        monthly_essentials=profile.monthly_essentials,
        stability_fund_balance=profile.stability_fund_balance,
        stability_fund_target_months=profile.stability_fund_target_months,
        revenue_per_hour=profile.revenue_per_hour,
        baseline_revenue_per_hour=profile.baseline_revenue_per_hour,
    )
    stability_pct = summary["stability_fund"]["pct_of_target"]
    future_bucket = summary["allocation_156520"]["future"]
    skills = [profile.primary_trade] if profile.primary_trade else []

    wins: list[dict] = []

    if summary["debt_snowball"].get("primary_target"):
        wins.append(
            {
                "title": f"Debt snowball: {summary['debt_snowball']['primary_target']}",
                "priority": "high",
                "action": f"Send ${future_bucket:,.0f} extra to highest-APR debt — guaranteed return.",
                "category": "debt",
            }
        )

    for action in summary["credit_plan"].get("weekly_actions", [])[:2]:
        wins.append({"title": "Credit win", "priority": "medium", "action": action, "category": "credit"})

    wins.append(
        {
            "title": "Route next inflow",
            "priority": "high",
            "action": f"Split incoming dollars 15/65/20 — ${summary['allocation_156520']['future']:,.0f} to Future.",
            "category": "cashflow",
        }
    )

    opportunities = _scan_opportunities(future_bucket, skills, stability_pct)

    return {
        "stage": journey["stage"],
        "stability_fund_pct": stability_pct,
        "quick_wins": wins[:5],
        "opportunities": opportunities,
        "disclaimer": "Educational ideas — verify spreads and legal eligibility before deploying capital.",
    }
