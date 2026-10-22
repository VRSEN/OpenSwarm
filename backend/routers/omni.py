"""OmniWealth Command Center — net worth, risk budget, smart moves."""

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.user_profile import UserProfile
from backend.services.omni_wealth import (
    INFLOW_KINDS,
    MOVE_TYPES,
    command_center_payload,
    compare_reinvestment,
    evaluate_move,
    mark_route_done,
    route_inflow,
    save_inflow,
    today_payload,
    upsert_move,
    weekly_review,
)

router = APIRouter(prefix="/wealth", tags=["omni-wealth"])


def _profile(db: Session, user_id: str) -> UserProfile:
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Complete Financial Reality Intake first")
    return profile


class WealthStateBody(BaseModel):
    cash: float | None = None
    business_accounts: float | None = None
    productive_assets: float | None = None
    productive_assets_known: bool | None = None
    investments: float | None = None
    receivables: float | None = None
    business_equity: float | None = None
    business_equity_known: bool | None = None
    other_assets: float | None = None
    loans: float | None = None
    tax_liabilities: float | None = None
    other_liabilities: float | None = None
    as_of: str | None = None


class NorthStarBody(BaseModel):
    target_net_worth: float = Field(default=1_000_000, gt=0)
    target_date: str = Field(default="2027-12-31")
    label: str = Field(default="North Star — financial freedom")


class UnderwriteBody(BaseModel):
    name: str = Field(..., min_length=1)
    move_type: str = Field(default="other")
    platform: str = Field(default="")
    capital_required: float = Field(..., ge=0)
    expected_profit: float = Field(default=0)
    best_profit: float | None = None
    likely_profit: float | None = None
    max_loss: float | None = None
    recycle_days: int = Field(default=14, ge=1, le=365)
    exit_plan: str = Field(default="")
    independent_evidence: bool = Field(default=False)
    seller_claim: bool = Field(default=False)
    bull_why: str = Field(default="")
    override: bool = Field(default=False)
    override_reason: str = Field(default="")


class CommitBody(BaseModel):
    move_id: str
    confirm_max_loss: bool = Field(default=False)


class CloseBody(BaseModel):
    move_id: str
    result: str = Field(default="closed")
    profit: float = Field(default=0)


class ReinvestBody(BaseModel):
    capital: float = Field(..., gt=0)
    internal_return_pct: float = Field(..., ge=0)
    external_return_pct: float = Field(..., ge=0)
    days: int = Field(default=30, ge=1)
    track_record: str = Field(default="thin")


class InflowBody(BaseModel):
    amount: float = Field(..., gt=0)
    source: str = Field(default="")
    kind: str = Field(default="business")
    date: str | None = None
    tax_pct: float | None = Field(default=None, ge=0, le=60)
    preview: bool = Field(default=False)


class RouteDoneBody(BaseModel):
    inflow_id: str
    key: str


@router.get("/today")
def wealth_today(user_id: str = Query(default="default"), db: Session = Depends(get_db)):
    return today_payload(_profile(db, user_id))


@router.post("/inflow")
def wealth_inflow(body: InflowBody, user_id: str = Query(default="default"), db: Session = Depends(get_db)):
    if body.kind not in INFLOW_KINDS:
        raise HTTPException(status_code=400, detail=f"kind must be one of: {', '.join(INFLOW_KINDS)}")
    profile = _profile(db, user_id)
    flow = route_inflow(profile, body.amount, source=body.source, kind=body.kind, date=body.date, tax_pct=body.tax_pct)
    if body.preview:
        return {"inflow": flow, "saved": False}
    save_inflow(profile, flow)
    db.commit()
    return {"inflow": flow, "saved": True, "today": today_payload(profile)}


@router.post("/inflow/done")
def wealth_inflow_done(body: RouteDoneBody, user_id: str = Query(default="default"), db: Session = Depends(get_db)):
    profile = _profile(db, user_id)
    flow = mark_route_done(profile, body.inflow_id, body.key)
    if not flow:
        raise HTTPException(status_code=404, detail="Route not found or already done")
    db.commit()
    return {"inflow": flow, "today": today_payload(profile)}


@router.get("/command")
def wealth_command(user_id: str = Query(default="default"), db: Session = Depends(get_db)):
    return command_center_payload(_profile(db, user_id))


@router.get("/weekly-review")
def wealth_weekly(user_id: str = Query(default="default"), db: Session = Depends(get_db)):
    return weekly_review(_profile(db, user_id))


@router.post("/state")
def wealth_state(body: WealthStateBody, user_id: str = Query(default="default"), db: Session = Depends(get_db)):
    profile = _profile(db, user_id)
    current = json.loads(profile.wealth_state_json or "{}")
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    current.update(updates)
    current["as_of"] = body.as_of or datetime.now(timezone.utc).date().isoformat()
    profile.wealth_state_json = json.dumps(current)
    db.commit()
    return command_center_payload(profile)


@router.post("/north-star")
def wealth_north_star(body: NorthStarBody, user_id: str = Query(default="default"), db: Session = Depends(get_db)):
    profile = _profile(db, user_id)
    profile.north_star_json = json.dumps(body.model_dump())
    db.commit()
    return command_center_payload(profile)


@router.post("/moves/underwrite")
def wealth_underwrite(body: UnderwriteBody, user_id: str = Query(default="default"), db: Session = Depends(get_db)):
    if body.move_type not in MOVE_TYPES:
        raise HTTPException(status_code=400, detail=f"move_type must be one of: {', '.join(MOVE_TYPES)}")
    profile = _profile(db, user_id)
    payload = body.model_dump()
    payload["capital"] = payload["capital_required"]
    if payload.get("max_loss") is None:
        payload["max_loss"] = payload["capital_required"]
    packet = evaluate_move(profile, payload)
    upsert_move(profile, packet, status="underwritten")
    db.commit()
    return packet


@router.post("/moves/commit")
def wealth_commit(body: CommitBody, user_id: str = Query(default="default"), db: Session = Depends(get_db)):
    profile = _profile(db, user_id)
    packet = None
    for move in json.loads(profile.opportunities_json or "[]"):
        if move.get("move_id") == body.move_id:
            packet = move
            break
    if not packet:
        raise HTTPException(status_code=404, detail="Underwrite the move first")
    if packet.get("verdict") not in ("BUY", "TEST", "ESCALATE"):
        raise HTTPException(status_code=400, detail=f"Cannot commit a {packet.get('verdict')} verdict")
    if not body.confirm_max_loss:
        raise HTTPException(status_code=400, detail="Confirm you accept the max loss before committing")
    reconstructed = evaluate_move(
        profile,
        {
            "move_id": packet["move_id"],
            "name": packet["name"],
            "move_type": packet["move_type"],
            "capital_required": packet.get("capital_required", 0),
            "max_loss": packet.get("max_loss"),
            "recycle_days": 14,
            "exit_plan": "Committed with max-loss confirmation",
        },
    )
    reconstructed["committed_at"] = datetime.now(timezone.utc).isoformat()
    upsert_move(profile, reconstructed, status="open")
    db.commit()
    return {
        "status": "open",
        "message": "Logged. Execute the playbook yourself — the system will watch the review date.",
        "move": reconstructed,
    }


@router.post("/moves/close")
def wealth_close(body: CloseBody, user_id: str = Query(default="default"), db: Session = Depends(get_db)):
    profile = _profile(db, user_id)
    moves = json.loads(profile.opportunities_json or "[]")
    found = False
    for move in moves:
        if move.get("move_id") == body.move_id:
            move["status"] = "closed"
            move["result"] = body.result
            move["profit"] = body.profit
            move["updated_at"] = datetime.now(timezone.utc).isoformat()
            found = True
    if not found:
        raise HTTPException(status_code=404, detail="Move not found")
    profile.opportunities_json = json.dumps(moves)
    db.commit()
    return {"status": "closed", "moves": moves}


@router.post("/reinvest/compare")
def wealth_reinvest(body: ReinvestBody, user_id: str = Query(default="default"), db: Session = Depends(get_db)):
    _profile(db, user_id)
    return compare_reinvestment(
        body.capital,
        body.internal_return_pct,
        body.external_return_pct,
        days=body.days,
        track_record=body.track_record,
    )
