"""
Spread engine with reputation-based cost-of-capital adjustments and fund gates.
"""

from __future__ import annotations

from typing import Any

from backend.services.reputation_engine import check_fund_now_gate, get_tier_unlocks


def calculate_net_spread(
    asset_yield_pct: float,
    cost_of_capital_pct: float,
    friction_expenses_pct: float = 2.0,
    reputation_tier: str = "Bronze",
) -> dict[str, Any]:
    """Net spread with reputation CoC adjustment applied."""
    adjusted_coc = apply_reputation_coc_adjustment(cost_of_capital_pct, reputation_tier)
    spread = asset_yield_pct - adjusted_coc - friction_expenses_pct
    return {
        "asset_yield_pct": asset_yield_pct,
        "base_cost_of_capital_pct": cost_of_capital_pct,
        "adjusted_cost_of_capital_pct": round(adjusted_coc, 3),
        "friction_expenses_pct": friction_expenses_pct,
        "reputation_tier": reputation_tier,
        "coc_adjustment_bps": get_tier_unlocks(reputation_tier)["coc_adjustment_bps"],
        "net_spread_pct": round(spread, 3),
        "pass": spread > 0,
    }


def apply_reputation_coc_adjustment(base_coc_pct: float, tier: str) -> float:
    """Gold/Platinum: −50 bps effective cost of capital."""
    bps = get_tier_unlocks(tier)["coc_adjustment_bps"]
    return max(0.0, base_coc_pct + bps / 100)


def evaluate_fund_eligibility(
    composite_score: float,
    self_trust_pillar: float,
    tier: str,
    requested_amount: float,
) -> dict[str, Any]:
    """Fund Now gate: reputation tier + Self-Trust floor + amount cap."""
    gate = check_fund_now_gate(composite_score, self_trust_pillar)
    unlocks = get_tier_unlocks(tier)

    if not gate["eligible"]:
        return {
            "approved": False,
            "reason": gate["block_reason"],
            "max_allowed": 0,
            "tier": tier,
        }

    if not unlocks["arbitrage_funding"]:
        return {
            "approved": False,
            "reason": "Bronze tier: arbitrage funding blocked",
            "max_allowed": 0,
            "tier": tier,
        }

    max_allowed = unlocks["max_fund_amount"]
    if requested_amount > max_allowed:
        return {
            "approved": False,
            "reason": f"Requested ${requested_amount:.0f} exceeds {tier} max ${max_allowed:.0f}",
            "max_allowed": max_allowed,
            "tier": tier,
            "requires_pause": requested_amount > 500,
        }

    return {
        "approved": True,
        "reason": None,
        "max_allowed": max_allowed,
        "tier": tier,
        "requires_pause": requested_amount > 500,
        "pipeline_priority": unlocks["pipeline_priority"],
    }
