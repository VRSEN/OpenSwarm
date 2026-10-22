"""Load user reputation inputs from database."""

import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.models.reputation import (
    RecalibrationAlert,
    ReputationScore,
    SelfTrustEvent,
    StrategyPersistence,
    UserSelfCommitment,
)
from backend.services.reputation_engine import (
    EngagementRecord,
    PressurePerformanceInput,
    QuietBuilderInput,
    RarityInput,
    SelfTrustEvent as SelfTrustEventDTO,
    StrategyPersistenceInput,
    compute_full_reputation,
    detect_drift_for_recalibration,
)


def _default_user_id(user_id: str | None) -> str:
    return user_id or "default"


def load_self_trust_events(db: Session, user_id: str) -> list[SelfTrustEventDTO]:
    rows = (
        db.query(SelfTrustEvent)
        .filter(SelfTrustEvent.user_id == user_id)
        .order_by(SelfTrustEvent.recorded_at.desc())
        .limit(100)
        .all()
    )
    return [
        SelfTrustEventDTO(
            kept_commitment=r.kept_commitment,
            event_type=r.event_type,
            weight=r.weight,
        )
        for r in rows
    ]


def load_persistence(db: Session, user_id: str) -> StrategyPersistenceInput:
    row = (
        db.query(StrategyPersistence)
        .filter(StrategyPersistence.user_id == user_id, StrategyPersistence.active.is_(True))
        .order_by(StrategyPersistence.strategy_start_date.asc())
        .first()
    )
    if not row:
        return StrategyPersistenceInput()

    days = (datetime.now(timezone.utc) - row.strategy_start_date.replace(tzinfo=timezone.utc)).days
    return StrategyPersistenceInput(
        strategy_start_days_ago=days,
        restart_count=row.restart_count,
        invisible_season_days=row.invisible_season_days,
        steady_months=row.steady_months,
    )


def compute_user_reputation(
    db: Session,
    user_id: str | None = None,
    *,
    engagements: list[dict] | None = None,
    quiet_builder_overrides: dict | None = None,
    essentials_pct: float | None = None,
    life_bucket_pct: float | None = None,
) -> dict:
    uid = _default_user_id(user_id)
    events = load_self_trust_events(db, uid)
    persistence = load_persistence(db, uid)

    engagement_records = []
    if engagements:
        for e in engagements:
            engagement_records.append(
                EngagementRecord(
                    delivered=e.get("delivered", False),
                    on_time=e.get("on_time", False),
                    promised=e.get("promised", ""),
                )
            )

    qb = QuietBuilderInput()
    if quiet_builder_overrides:
        for k, v in quiet_builder_overrides.items():
            if hasattr(qb, k):
                setattr(qb, k, v)

    result = compute_full_reputation(
        engagements=engagement_records,
        self_trust_events=events,
        persistence=persistence,
        quiet_builder=qb,
        rarity=RarityInput(
            skill_depth_score=quiet_builder_overrides.get("skill_depth_score", 50) if quiet_builder_overrides else 50,
            discipline_score=persistence.steady_months * 8 if persistence.steady_months else 50,
        ),
        pressure=PressurePerformanceInput(),
    )

    # Persist snapshot
    db.add(
        ReputationScore(
            user_id=uid,
            composite_score=result["reputation_credit_score"],
            tier=result["tier"],
            pillar_behavioral_trust=result["pillars"]["behavioral_trust"],
            pillar_self_trust=result["pillars"]["self_trust"],
            pillar_pressure=result["pillars"]["pressure_performance"],
            pillar_authenticity=result["pillars"]["authenticity"],
            pillar_consistency=result["pillars"]["consistency"],
            rarity_score=result["rarity"]["rarity_score"],
            snapshot_json=json.dumps(result),
        )
    )
    db.commit()

    return result


def get_active_recalibration(db: Session, user_id: str) -> RecalibrationAlert | None:
    return (
        db.query(RecalibrationAlert)
        .filter(
            RecalibrationAlert.user_id == user_id,
            RecalibrationAlert.dismissed.is_(False),
        )
        .order_by(RecalibrationAlert.created_at.desc())
        .first()
    )


def maybe_create_recalibration(
    db: Session,
    user_id: str,
    essentials_pct: float,
    pause_breaches: int,
    life_bucket_pct: float,
) -> dict | None:
    payload = detect_drift_for_recalibration(
        essentials_pct=essentials_pct,
        pause_breaches_recent=pause_breaches,
        life_bucket_over_pct=life_bucket_pct,
    )
    if not payload:
        return None

    existing = get_active_recalibration(db, user_id)
    if existing:
        return json.loads(existing.reasons_json) if existing.reasons_json.startswith("[") else {"message": existing.message}

    alert = RecalibrationAlert(
        user_id=user_id,
        severity=payload["severity"],
        message=payload["message"],
        reasons_json=json.dumps(payload["reasons"]),
    )
    db.add(alert)
    db.commit()
    return payload
