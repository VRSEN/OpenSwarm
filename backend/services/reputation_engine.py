"""
Deterministic Integrity Engine — five-pillar reputation scoring.

All math is pure functions; LLM agents narrate reports but never score.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

# Pillar weights (must sum to 1.0)
PILLAR_WEIGHTS = {
    "behavioral_trust": 0.25,
    "self_trust": 0.20,
    "pressure_performance": 0.20,
    "authenticity": 0.20,
    "consistency": 0.15,
}

SELF_TRUST_FLOOR = 60
TIER_THRESHOLDS = [
    ("Platinum", 90),
    ("Gold", 75),
    ("Silver", 60),
    ("Bronze", 0),
]


@dataclass
class EngagementRecord:
    delivered: bool = False
    on_time: bool = False
    promised: str = ""


@dataclass
class SelfTrustEvent:
    kept_commitment: bool = False
    event_type: str = "check_in"
    weight: float = 1.0


@dataclass
class StrategyPersistenceInput:
    strategy_start_days_ago: int = 0
    restart_count: int = 0
    invisible_season_days: int = 0
    steady_months: int = 0
    burst_gap_months: int = 0


@dataclass
class QuietBuilderInput:
    future_bucket_pct: float = 15.0
    life_ego_spend_pct: float = 0.0
    reinvest_ratio: float = 0.5
    consumer_tag_count: int = 0
    acquirer_tag_count: int = 0
    visibility_score: float = 50.0
    verified_delivery_count: int = 0


@dataclass
class RarityInput:
    skill_depth_score: float = 50.0
    discipline_score: float = 50.0
    visibility_inflation_factor: float = 1.0


@dataclass
class PressurePerformanceInput:
    crisis_events: int = 0
    crisis_passed: int = 0
    repeat_failure_modes: int = 0
    private_job_count: int = 0
    private_on_time_rate: float = 100.0


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def score_behavioral_reliability(
    engagements: list[EngagementRecord],
    invoice_on_time_rate: float | None = None,
) -> float:
    """Pillar 1 — predictability over excitement."""
    if not engagements and invoice_on_time_rate is None:
        return 50.0

    scores: list[float] = []
    if engagements:
        delivered = sum(1 for e in engagements if e.delivered)
        on_time = sum(1 for e in engagements if e.on_time)
        total = len(engagements)
        delivery_rate = delivered / total * 100
        on_time_rate = on_time / total * 100
        scores.append(delivery_rate * 0.55 + on_time_rate * 0.45)

    if invoice_on_time_rate is not None:
        scores.append(invoice_on_time_rate)

    return _clamp(sum(scores) / len(scores))


def compute_self_trust_index(events: list[SelfTrustEvent]) -> dict[str, Any]:
    """Pillar 2 — Self-Trust Index from private commitments."""
    if not events:
        return {
            "self_trust_index": 50.0,
            "commitments_kept": 0,
            "commitments_set": 0,
            "keep_rate_pct": 0.0,
        }

    weighted_total = sum(e.weight for e in events)
    weighted_kept = sum(e.weight for e in events if e.kept_commitment)
    keep_rate = (weighted_kept / weighted_total * 100) if weighted_total else 0.0

    # Recency: last 5 events weighted slightly higher
    recent = events[-5:] if len(events) >= 5 else events
    recent_kept = sum(1 for e in recent if e.kept_commitment)
    recent_rate = recent_kept / len(recent) * 100 if recent else keep_rate

    index = keep_rate * 0.7 + recent_rate * 0.3
    silent_slips = sum(1 for e in events if not e.kept_commitment and e.event_type == "pause_broken")
    breach_penalty = min(silent_slips * 5, 25)
    index = _clamp(index - breach_penalty)

    return {
        "self_trust_index": round(index, 1),
        "commitments_kept": int(weighted_kept),
        "commitments_set": int(weighted_total),
        "keep_rate_pct": round(keep_rate, 1),
        "pause_breaches": silent_slips,
    }


def score_pressure_performance(data: PressurePerformanceInput) -> float:
    """Pillar 3 — composure under uncertainty."""
    if data.crisis_events == 0:
        base = 70.0
    else:
        pass_rate = data.crisis_passed / data.crisis_events
        base = pass_rate * 100

    repeat_penalty = min(data.repeat_failure_modes * 10, 30)
    private_bonus = 0.0
    if data.private_job_count >= 3:
        private_bonus = min(data.private_on_time_rate * 0.1, 10)

    return _clamp(base - repeat_penalty + private_bonus)


def compute_rarity_score(data: RarityInput) -> dict[str, Any]:
    """Pillar 4 component — RARITY from skill depth × discipline / visibility inflation."""
    factor = max(data.visibility_inflation_factor, 0.5)
    raw = (data.skill_depth_score * data.discipline_score) / factor
    rarity = _clamp(raw / 100 * 100)
    return {
        "rarity_score": round(rarity, 1),
        "skill_depth_score": data.skill_depth_score,
        "discipline_score": data.discipline_score,
        "visibility_inflation_factor": factor,
    }


def compute_quiet_builder_score(data: QuietBuilderInput) -> float:
    """Pillar 4 — authenticity over performance; quiet builders reinvest."""
    reinvest_score = _clamp(data.reinvest_ratio * 100)
    ego_penalty = min(data.life_ego_spend_pct * 2, 30)
    tag_total = data.consumer_tag_count + data.acquirer_tag_count
    if tag_total > 0:
        acquirer_ratio = data.acquirer_tag_count / tag_total
        tag_score = acquirer_ratio * 100
    else:
        tag_score = 50.0

    future_bonus = min(max(data.future_bucket_pct - 10, 0) * 2, 15)
    delivery_bonus = min(data.verified_delivery_count * 3, 15)

    score = reinvest_score * 0.35 + tag_score * 0.35 + 50 * 0.15
    score += future_bonus + delivery_bonus - ego_penalty
    return _clamp(score)


def compute_strategy_persistence_score(data: StrategyPersistenceInput) -> float:
    """Pillar 5 — consistency over intensity; invisible years bonus."""
    base = 50.0
    if data.steady_months >= 12:
        base = 85.0
    elif data.steady_months >= 6:
        base = 70.0
    elif data.burst_gap_months >= 6:
        base = 45.0

    restart_penalty = min(data.restart_count * 12, 36)
    invisible_bonus = min(data.invisible_season_days / 30 * 2, 15)

    return _clamp(base - restart_penalty + invisible_bonus)


def composite_tier(score: float) -> str:
    for name, threshold in TIER_THRESHOLDS:
        if score >= threshold:
            return name
    return "Bronze"


def compute_full_reputation(
    *,
    engagements: list[EngagementRecord] | None = None,
    self_trust_events: list[SelfTrustEvent] | None = None,
    pressure: PressurePerformanceInput | None = None,
    quiet_builder: QuietBuilderInput | None = None,
    rarity: RarityInput | None = None,
    persistence: StrategyPersistenceInput | None = None,
    invoice_on_time_rate: float | None = None,
) -> dict[str, Any]:
    """Compute five-pillar composite Reputation Credit score."""
    engagements = engagements or []
    self_trust_events = self_trust_events or []
    pressure = pressure or PressurePerformanceInput()
    quiet_builder = quiet_builder or QuietBuilderInput()
    rarity = rarity or RarityInput()
    persistence = persistence or StrategyPersistenceInput()

    p1 = score_behavioral_reliability(engagements, invoice_on_time_rate)
    self_trust_result = compute_self_trust_index(self_trust_events)
    p2 = self_trust_result["self_trust_index"]
    p3 = score_pressure_performance(pressure)
    quiet = compute_quiet_builder_score(quiet_builder)
    rarity_result = compute_rarity_score(rarity)
    p4 = _clamp(quiet * 0.6 + rarity_result["rarity_score"] * 0.4)
    p5 = compute_strategy_persistence_score(persistence)

    pillars = {
        "behavioral_trust": round(p1, 1),
        "self_trust": round(p2, 1),
        "pressure_performance": round(p3, 1),
        "authenticity": round(p4, 1),
        "consistency": round(p5, 1),
    }

    composite = sum(pillars[k] * PILLAR_WEIGHTS[k] for k in PILLAR_WEIGHTS)
    composite = round(composite, 1)
    tier = composite_tier(composite)

    fund_gate = check_fund_now_gate(composite, p2)

    return {
        "reputation_credit_score": composite,
        "tier": tier,
        "pillars": pillars,
        "pillar_weights": PILLAR_WEIGHTS,
        "self_trust_detail": self_trust_result,
        "rarity": rarity_result,
        "fund_now_eligible": fund_gate["eligible"],
        "fund_now_block_reason": fund_gate.get("block_reason"),
        "unlocks": get_tier_unlocks(tier),
        "travels_ahead_summary": build_portable_summary(composite, tier, pillars, rarity_result),
    }


def get_tier_unlocks(tier: str) -> dict[str, Any]:
    """Liquid capital unlocks by reputation tier."""
    unlocks = {
        "Bronze": {
            "arbitrage_funding": False,
            "max_fund_amount": 0,
            "coc_adjustment_bps": 0,
            "pipeline_priority": False,
        },
        "Silver": {
            "arbitrage_funding": True,
            "max_fund_amount": 50,
            "coc_adjustment_bps": 0,
            "pipeline_priority": False,
        },
        "Gold": {
            "arbitrage_funding": True,
            "max_fund_amount": 500,
            "coc_adjustment_bps": -50,
            "pipeline_priority": False,
        },
        "Platinum": {
            "arbitrage_funding": True,
            "max_fund_amount": 5000,
            "coc_adjustment_bps": -50,
            "pipeline_priority": True,
        },
    }
    return unlocks.get(tier, unlocks["Bronze"])


def check_fund_now_gate(composite_score: float, self_trust_pillar: float) -> dict[str, Any]:
    """Hard gate: Self-Trust < 60 blocks even if composite >= 70."""
    if self_trust_pillar < SELF_TRUST_FLOOR:
        return {
            "eligible": False,
            "block_reason": f"Self-Trust pillar {self_trust_pillar:.0f} below floor {SELF_TRUST_FLOOR}",
        }
    if composite_score < 60:
        return {
            "eligible": False,
            "block_reason": f"Composite score {composite_score:.0f} below Silver threshold (60)",
        }
    return {"eligible": True, "block_reason": None}


def build_portable_summary(
    composite: float,
    tier: str,
    pillars: dict[str, float],
    rarity: dict[str, Any],
) -> str:
    return (
        f"Reputation Credit {composite:.0f}/100 ({tier})—"
        f"predictability {pillars['behavioral_trust']:.0f}, "
        f"self-trust {pillars['self_trust']:.0f}, "
        f"consistency {pillars['consistency']:.0f}, "
        f"RARITY {rarity['rarity_score']:.0f}. "
        f"Character travels ahead as relationship leverage."
    )


def detect_drift_for_recalibration(
    essentials_pct: float,
    target_essentials_pct: float = 65.0,
    pause_breaches_recent: int = 0,
    life_bucket_over_pct: float = 0.0,
) -> dict[str, Any] | None:
    """Return recalibration alert payload if behavior drifted from financial machine."""
    reasons: list[str] = []
    if essentials_pct > target_essentials_pct:
        reasons.append(f"Essentials {essentials_pct:.0f}% exceeds {target_essentials_pct:.0f}% target")
    if pause_breaches_recent > 0:
        reasons.append(f"{pause_breaches_recent} pause rule breach(es) in lookback window")
    if life_bucket_over_pct > 25:
        reasons.append(f"Life bucket at {life_bucket_over_pct:.0f}%—above 20% allocation")

    if not reasons:
        return None

    return {
        "alert_type": "recalibration",
        "severity": "amber" if essentials_pct <= target_essentials_pct + 10 else "red",
        "reasons": reasons,
        "message": (
            "Your machine drifted from architect standards. "
            + "; ".join(reasons)
            + ". Return to principles before reputation tier slips."
        ),
        "corrective_actions": [
            "Log one concrete corrective action in Operator Journal",
            "Review invisible transactions from the last 7 days",
            "Re-affirm active self-commitments",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
