"""Integrity Engine REST routes."""

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.reputation import (
    RecalibrationAlert,
    ReputationUnlock,
    SelfTrustEvent,
    UserSelfCommitment,
)
from backend.repositories.reputation_repo import (
    compute_user_reputation,
    load_self_trust_events,
    maybe_create_recalibration,
)
from backend.schemas.reputation import (
    FundEligibilityRequest,
    SelfCommitmentCreate,
    SelfTrustCheckIn,
    VetProviderRequest,
)
from backend.services.reputation_engine import (
    EngagementRecord,
    compute_full_reputation,
    compute_self_trust_index,
    get_tier_unlocks,
    score_behavioral_reliability,
)
from backend.services.spread_engine import evaluate_fund_eligibility

router = APIRouter(prefix="/reputation", tags=["reputation"])


def _user_id(user_id: str | None = Query(default="default")) -> str:
    return user_id or "default"


@router.get("/score")
def get_reputation_score(
    user_id: str = Depends(_user_id),
    db: Session = Depends(get_db),
    consumer_tag_count: int = Query(default=0, ge=0),
    acquirer_tag_count: int = Query(default=0, ge=0),
):
    return compute_user_reputation(
        db,
        user_id,
        quiet_builder_overrides={
            "consumer_tag_count": consumer_tag_count,
            "acquirer_tag_count": acquirer_tag_count,
        },
    )


@router.get("/self-trust")
def get_self_trust(user_id: str = Depends(_user_id), db: Session = Depends(get_db)):
    events = load_self_trust_events(db, user_id)
    index = compute_self_trust_index(events)
    commitments = (
        db.query(UserSelfCommitment)
        .filter(UserSelfCommitment.user_id == user_id, UserSelfCommitment.active.is_(True))
        .all()
    )
    return {
        **index,
        "active_commitments": [
            {
                "id": c.id,
                "benchmark_type": c.benchmark_type,
                "description": c.description,
                "target_value": c.target_value,
                "streak_days": c.streak_days,
            }
            for c in commitments
        ],
    }


@router.post("/self-commitments")
def create_self_commitment(
    body: SelfCommitmentCreate,
    user_id: str = Depends(_user_id),
    db: Session = Depends(get_db),
):
    row = UserSelfCommitment(
        user_id=user_id,
        benchmark_type=body.benchmark_type,
        description=body.description,
        target_value=body.target_value,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        "id": row.id,
        "benchmark_type": row.benchmark_type,
        "description": row.description,
        "target_value": row.target_value,
        "active": row.active,
    }


@router.post("/self-trust/check-in")
def self_trust_check_in(
    body: SelfTrustCheckIn,
    user_id: str = Depends(_user_id),
    db: Session = Depends(get_db),
):
    event = SelfTrustEvent(
        user_id=user_id,
        event_type=body.event_type,
        kept_commitment=body.kept_commitment,
        commitment_id=body.commitment_id,
        notes=body.notes,
    )
    db.add(event)
    if body.commitment_id and body.kept_commitment:
        commitment = db.get(UserSelfCommitment, body.commitment_id)
        if commitment and commitment.user_id == user_id:
            commitment.streak_days += 1
    db.commit()
    events = load_self_trust_events(db, user_id)
    return compute_self_trust_index(events)


@router.get("/unlocks")
def get_unlocks(tier: str = Query(default="Bronze")):
    return {"tier": tier, "unlocks": get_tier_unlocks(tier)}


@router.get("/unlocks/all")
def get_all_unlocks(db: Session = Depends(get_db)):
    rows = db.query(ReputationUnlock).all()
    if rows:
        return {
            r.tier: {
                "arbitrage_funding": r.arbitrage_funding,
                "max_fund_amount": r.max_fund_amount,
                "coc_adjustment_bps": r.coc_adjustment_bps,
                "pipeline_priority": r.pipeline_priority,
            }
            for r in rows
        }
    return {t: get_tier_unlocks(t) for t in ("Bronze", "Silver", "Gold", "Platinum")}


@router.get("/portable")
def get_portable_reputation(
    user_id: str = Depends(_user_id),
    db: Session = Depends(get_db),
):
    rep = compute_user_reputation(db, user_id)
    return {
        "export_format": "travels_ahead",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": rep["travels_ahead_summary"],
        "reputation_credit_score": rep["reputation_credit_score"],
        "tier": rep["tier"],
        "pillars": rep["pillars"],
        "rarity_score": rep["rarity"]["rarity_score"],
        "fund_now_eligible": rep["fund_now_eligible"],
    }


@router.post("/vet-provider")
def vet_provider(body: VetProviderRequest):
    engagements = [
        EngagementRecord(
            delivered=e.delivered,
            on_time=e.on_time,
            promised=e.promised,
        )
        for e in body.engagements
    ]
    trust = score_behavioral_reliability(engagements)
    ref_bonus = min(body.references_verified * 5, 15)
    provider_trust = min(trust + ref_bonus * 0.3, 100)

    rep = compute_full_reputation(
        engagements=engagements,
        self_trust_events=[],
    )
    rep["provider_name"] = body.provider_name
    rep["provider_behavioral_trust"] = round(provider_trust, 1)
    rep["references_verified"] = body.references_verified
    rep["verdict"] = (
        "hire"
        if provider_trust >= 75 and rep["fund_now_eligible"]
        else "monitor"
        if provider_trust >= 60
        else "avoid"
    )
    rep["project_value"] = body.project_value
    rep["vetting_report"] = {
        "five_pillars": rep["pillars"],
        "rarity": rep["rarity"],
        "composite": rep["reputation_credit_score"],
        "tier": rep["tier"],
    }
    return rep


@router.post("/fund-eligibility")
def check_fund_eligibility(
    body: FundEligibilityRequest,
    user_id: str = Depends(_user_id),
    db: Session = Depends(get_db),
):
    if body.composite_score is None or body.self_trust_pillar is None or body.tier is None:
        rep = compute_user_reputation(db, user_id)
        composite = rep["reputation_credit_score"]
        self_trust = rep["pillars"]["self_trust"]
        tier = rep["tier"]
    else:
        composite = body.composite_score
        self_trust = body.self_trust_pillar
        tier = body.tier

    return evaluate_fund_eligibility(composite, self_trust, tier, body.requested_amount)


@router.post("/recalibration/{alert_id}/dismiss")
def dismiss_recalibration(
    alert_id: int,
    corrective_action: str = Query(..., min_length=3),
    user_id: str = Depends(_user_id),
    db: Session = Depends(get_db),
):
    alert = db.get(RecalibrationAlert, alert_id)
    if not alert or alert.user_id != user_id:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.dismissed = True
    alert.corrective_action = corrective_action
    alert.dismissed_at = datetime.now(timezone.utc)
    db.commit()
    return {"dismissed": True, "id": alert_id}
