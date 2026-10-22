"""Command Center / Character Mirror dashboard routes."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.repositories.reputation_repo import (
    compute_user_reputation,
    get_active_recalibration,
    maybe_create_recalibration,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/mirror")
def get_character_mirror(
    user_id: str = Query(default="default"),
    essentials_pct: float = Query(default=65.0, ge=0, le=100),
    life_bucket_pct: float = Query(default=20.0, ge=0, le=100),
    stability_fund_pct: float = Query(default=0.0, ge=0),
    money_velocity_tier: str = Query(default="B"),
    consumer_tag_count: int = Query(default=0, ge=0),
    acquirer_tag_count: int = Query(default=0, ge=0),
    pause_breaches_recent: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """
    Silent Dashboard — 3 KPIs + Character Mirror expand payload.
    Connects Consumer vs Acquirer tags to Quiet Builder (Pillar 4).
    """
    reputation = compute_user_reputation(
        db,
        user_id,
        quiet_builder_overrides={
            "consumer_tag_count": consumer_tag_count,
            "acquirer_tag_count": acquirer_tag_count,
            "life_ego_spend_pct": max(0, life_bucket_pct - 20),
        },
        essentials_pct=essentials_pct,
        life_bucket_pct=life_bucket_pct,
    )

    recalibration = maybe_create_recalibration(
        db,
        user_id,
        essentials_pct=essentials_pct,
        pause_breaches=pause_breaches_recent,
        life_bucket_pct=life_bucket_pct,
    )
    active_alert = get_active_recalibration(db, user_id)

    identity_line = (
        "You are an architect who protects their future."
        if reputation["fund_now_eligible"]
        else "You are rebuilding trust with your machine—consistency before velocity."
    )

    return {
        "silent_kpis": {
            "stability_fund_pct": round(stability_fund_pct, 1),
            "money_velocity_tier": money_velocity_tier,
            "reputation_credit_score": reputation["reputation_credit_score"],
            "reputation_tier": reputation["tier"],
        },
        "character_mirror": {
            "pillars": reputation["pillars"],
            "self_trust_index": reputation["self_trust_detail"]["self_trust_index"],
            "rarity_score": reputation["rarity"]["rarity_score"],
            "quiet_builder_inputs": {
                "consumer_tag_count": consumer_tag_count,
                "acquirer_tag_count": acquirer_tag_count,
            },
            "fund_now_eligible": reputation["fund_now_eligible"],
            "unlocks": reputation["unlocks"],
        },
        "recalibration_alert": recalibration or (
            {
                "message": active_alert.message,
                "severity": active_alert.severity,
                "id": active_alert.id,
            }
            if active_alert
            else None
        ),
        "identity_line": identity_line,
    }
