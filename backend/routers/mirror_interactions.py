"""Fork Moments and dollar mission interaction routes."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.fork_moment import ForkMomentPause
from backend.models.user_profile import UserProfile
from backend.schemas.interactions import ForkEmotionAck, ForkPauseStart, ForkRelease
from backend.services.fork_moments import acknowledge_emotion, create_fork_pause, dollar_missions

router = APIRouter(prefix="/mirror", tags=["mirror"])


def _profile(db: Session, user_id: str) -> UserProfile:
    p = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    if not p or not p.onboarding_completed:
        raise HTTPException(status_code=400, detail="Complete Financial Reality Intake first")
    return p


@router.get("/dollar-missions")
def get_dollar_missions(user_id: str = Query(default="default"), db: Session = Depends(get_db)):
    profile = _profile(db, user_id)
    return dollar_missions(profile.monthly_gross_income)


@router.get("/fork-moments")
def list_fork_moments(user_id: str = Query(default="default"), db: Session = Depends(get_db)):
    rows = (
        db.query(ForkMomentPause)
        .filter(ForkMomentPause.user_id == user_id, ForkMomentPause.released.is_(False))
        .order_by(ForkMomentPause.created_at.desc())
        .all()
    )
    now = datetime.now(timezone.utc)
    pauses = []
    for r in rows:
        unlock = r.unlock_at
        if unlock.tzinfo is None:
            unlock = unlock.replace(tzinfo=timezone.utc)
        hours = max(0, (unlock - now).total_seconds() / 3600)
        pauses.append(
            {
                "id": r.id,
                "item": r.item_description,
                "amount": r.amount,
                "emotion_acknowledged": r.emotion_acknowledged,
                "unlock_at": unlock.isoformat(),
                "hours_remaining": hours,
                "unlocked": hours <= 0,
                "identity_notification": r.identity_notification,
            }
        )
    return {"active_pauses": pauses}


@router.post("/fork-moments/pause")
def start_fork_pause(
    body: ForkPauseStart,
    user_id: str = Query(default="default"),
    db: Session = Depends(get_db),
):
    _profile(db, user_id)
    payload = create_fork_pause(body.item_description, body.amount, body.bucket)
    if payload.get("status") == "exempt":
        return payload

    unlock = datetime.fromisoformat(payload["unlock_at"])
    row = ForkMomentPause(
        user_id=user_id,
        item_description=body.item_description,
        amount=body.amount,
        bucket=body.bucket,
        unlock_at=unlock,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    payload["pause_id"] = row.id
    return payload


@router.post("/fork-moments/acknowledge")
def ack_fork_emotion(
    body: ForkEmotionAck,
    user_id: str = Query(default="default"),
    db: Session = Depends(get_db),
):
    row = db.get(ForkMomentPause, body.pause_id)
    if not row or row.user_id != user_id:
        raise HTTPException(status_code=404, detail="Fork Moment not found")

    result = acknowledge_emotion(body.emotion, body.choose_architect_path)
    row.emotion = body.emotion
    row.emotion_acknowledged = True
    row.identity_notification = result["identity_notification"]
    db.commit()
    return result


@router.post("/fork-moments/release")
def release_fork_moment(
    body: ForkRelease,
    user_id: str = Query(default="default"),
    db: Session = Depends(get_db),
):
    """Close a pause (or all unlocked ones) so they leave Command Center."""
    now = datetime.now(timezone.utc)
    q = db.query(ForkMomentPause).filter(
        ForkMomentPause.user_id == user_id,
        ForkMomentPause.released.is_(False),
    )
    if body.release_all_unlocked:
        rows = q.all()
        closed = 0
        for row in rows:
            unlock = row.unlock_at
            if unlock.tzinfo is None:
                unlock = unlock.replace(tzinfo=timezone.utc)
            if unlock <= now:
                row.released = True
                closed += 1
        db.commit()
        return {"released": closed, "message": f"Cleared {closed} finished pause(s)."}

    if not body.pause_id:
        raise HTTPException(status_code=400, detail="pause_id required")
    row = db.get(ForkMomentPause, body.pause_id)
    if not row or row.user_id != user_id:
        raise HTTPException(status_code=404, detail="Fork Moment not found")
    row.released = True
    db.commit()
    return {"released": 1, "message": "Pause closed."}
