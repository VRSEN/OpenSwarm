"""Financial Reality Intake routes."""

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.user_profile import UserProfile
from backend.schemas.user import (
    IntakeComplete,
    IntakeStep1,
    IntakeStep2,
    IntakeStep3,
    IntakeStep4,
    IntakeStep5,
    IntakeStep6,
    IntakeStep7,
    IntakeStep8,
)
from backend.services.clinical_audit import generate_clinical_audit
from backend.services.financial_intake import apply_intake_to_profile, build_financial_summary
from backend.services.financial_profile import serialize_intake_data
from backend.services.journey_engine import assess_stage
from backend.services.quick_wins import build_quick_wins

router = APIRouter(prefix="/user/intake", tags=["intake"])

STEP_SCHEMAS = {
    1: IntakeStep1,
    2: IntakeStep2,
    3: IntakeStep3,
    4: IntakeStep4,
    5: IntakeStep5,
    6: IntakeStep6,
    7: IntakeStep7,
    8: IntakeStep8,
}


def _get_or_create(db: Session, user_id: str) -> UserProfile:
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    if not profile:
        profile = UserProfile(user_id=user_id)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


def _apply_legacy_step(profile: UserProfile, step: int, body: dict) -> None:
    """Map old 6-step intake payloads to expanded steps."""
    if step == 2 and "monthly_essentials" in body:
        apply_intake_to_profile(
            profile,
            2,
            {
                "income_streams": [
                    {
                        "name": "Primary income",
                        "source_type": "business",
                        "amount_monthly": float(body["monthly_gross_income"]),
                        "frequency": "monthly",
                        "notes": "",
                    }
                ],
                "monthly_gross_income": float(body["monthly_gross_income"]),
            },
        )
        apply_intake_to_profile(
            profile,
            3,
            {"monthly_essentials": float(body["monthly_essentials"])},
        )
        apply_intake_to_profile(
            profile,
            4,
            {
                "bills": [],
                "stability_fund_balance": float(body.get("stability_fund_balance", 0)),
                "stability_fund_target_months": int(body.get("stability_fund_target_months", 4)),
            },
        )
        profile.monthly_essentials = float(body["monthly_essentials"])
        profile.intake_step = max(profile.intake_step or 0, 4)
        return
    if step == 3:
        apply_intake_to_profile(profile, 5, body)
        return
    if step == 4:
        apply_intake_to_profile(profile, 6, body)
        return
    if step == 5:
        apply_intake_to_profile(profile, 7, body)
        return
    if step == 6:
        apply_intake_to_profile(profile, 8, body)
        return
    raise HTTPException(status_code=400, detail="Unknown legacy intake step")


def _is_legacy_payload(step: int, body: dict) -> bool:
    if step == 2 and "monthly_essentials" in body and "income_streams" not in body:
        return True
    if step in (3, 4, 5, 6) and step <= 6:
        # Old step 3 was debts — if only debts key and step is 3
        if step == 3 and "debts" in body and "housing" not in body:
            return True
        if step == 4 and "score_band" in body:
            return True
        if step == 5 and "profit_pct" in body:
            return True
        if step == 6 and "footprints" in body:
            return True
    return False


@router.get("/status")
def intake_status(user_id: str = Query(default="default"), db: Session = Depends(get_db)):
    profile = _get_or_create(db, user_id)
    return {
        "intake_step": profile.intake_step or 0,
        "intake_completed": profile.intake_completed_at is not None,
        "onboarding_completed": profile.onboarding_completed,
        "data_source": profile.data_source or "none",
    }


@router.get("/data")
def intake_data(user_id: str = Query(default="default"), db: Session = Depends(get_db)):
    profile = _get_or_create(db, user_id)
    return serialize_intake_data(profile)


@router.get("/summary")
def financial_summary(user_id: str = Query(default="default"), db: Session = Depends(get_db)):
    profile = _get_or_create(db, user_id)
    if not profile.intake_completed_at and not profile.onboarding_completed:
        raise HTTPException(status_code=400, detail="Complete Financial Reality Intake first")
    return build_financial_summary(profile)


@router.post("/step/{step}")
def save_intake_step(
    step: int,
    body: dict,
    user_id: str = Query(default="default"),
    db: Session = Depends(get_db),
):
    if step not in STEP_SCHEMAS and not (2 <= step <= 6 and _is_legacy_payload(step, body)):
        raise HTTPException(status_code=404, detail="Invalid intake step")

    profile = _get_or_create(db, user_id)

    if _is_legacy_payload(step, body):
        _apply_legacy_step(profile, step, body)
    else:
        schema = STEP_SCHEMAS[step]
        validated = schema.model_validate(body)
        apply_intake_to_profile(profile, step, validated.model_dump())

    db.commit()
    db.refresh(profile)

    preview = build_financial_summary(profile) if profile.monthly_gross_income else None
    return {
        "step": step,
        "intake_step": profile.intake_step,
        "saved": True,
        "preview": preview,
    }


@router.post("/complete")
def complete_intake(
    body: IntakeComplete,
    user_id: str = Query(default="default"),
    db: Session = Depends(get_db),
):
    profile = _get_or_create(db, user_id)
    if (profile.intake_step or 0) < 7:
        raise HTTPException(status_code=400, detail="Complete steps 1–7 before signing the contract")

    profile.intake_completed_at = datetime.now(timezone.utc)
    profile.contract_signed_at = datetime.now(timezone.utc)
    profile.onboarding_completed = True
    profile.focus_season_active = True
    profile.intake_step = 9
    if not profile.data_source or profile.data_source == "none":
        profile.data_source = "manual"

    footprints = json.loads(profile.footprints_json or "{}")
    if any(footprints.values()):
        audit = generate_clinical_audit(
            banking_connected=footprints.get("banking", False),
            calendar_connected=footprints.get("calendar", False),
            screen_connected=footprints.get("screen_time", False),
            profile=profile,
        )
        profile.audit_json = json.dumps(audit)

    db.commit()
    db.refresh(profile)

    journey = assess_stage(
        monthly_essentials=profile.monthly_essentials,
        stability_fund_balance=profile.stability_fund_balance,
        stability_fund_target_months=profile.stability_fund_target_months,
        revenue_per_hour=profile.revenue_per_hour,
        baseline_revenue_per_hour=profile.baseline_revenue_per_hour,
    )

    summary = build_financial_summary(profile)
    return {
        "intake_completed": True,
        "identity_notification": (
            f"Welcome, {profile.display_name}. Your machine runs on your numbers—not demo data."
        ),
        "journey": journey,
        "financial_summary": summary,
    }


@router.post("/reset")
def reset_intake(user_id: str = Query(default="default"), db: Session = Depends(get_db)):
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    if profile:
        db.delete(profile)
        db.commit()
    return {"reset": True, "message": "Profile cleared. Start intake again from Get Started."}


@router.get("/quick-wins")
def get_quick_wins(user_id: str = Query(default="default"), db: Session = Depends(get_db)):
    profile = _get_or_create(db, user_id)
    if not profile.intake_completed_at:
        raise HTTPException(status_code=400, detail="Complete intake first")
    return build_quick_wins(profile)


@router.get("/credit-plan")
def get_credit_plan(user_id: str = Query(default="default"), db: Session = Depends(get_db)):
    profile = _get_or_create(db, user_id)
    if not profile.intake_completed_at:
        raise HTTPException(status_code=400, detail="Complete intake first")
    summary = build_financial_summary(profile)
    return {
        "credit_plan": summary["credit_plan"],
        "disclaimer": summary["disclaimer"],
    }
