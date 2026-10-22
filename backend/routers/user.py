"""User onboarding, profile, and journey routes."""

import json

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.user_profile import UserProfile
from backend.schemas.interactions import ContractSign, FocusSeasonToggle, FootprintConnect, PatternAcknowledge
from backend.schemas.user import LiteracyProgress, OnboardingComplete, ProfileUpdate
from backend.services.clinical_audit import derive_profile_from_audit, generate_clinical_audit
from backend.services.journey_engine import STAGES, assess_stage
from backend.services.financial_intake import build_financial_summary
from backend.services.literacy_content import get_module, get_modules
from backend.services.wealth_playbook import PLAYBOOK_CATEGORIES, get_playbook

router = APIRouter(prefix="/user", tags=["user"])


def _get_or_create_profile(db: Session, user_id: str) -> UserProfile:
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    if not profile:
        profile = UserProfile(user_id=user_id)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


@router.get("/profile")
def get_profile(user_id: str = Query(default="default"), db: Session = Depends(get_db)):
    profile = _get_or_create_profile(db, user_id)
    completed = json.loads(profile.literacy_completed_json or "[]")
    return {
        "user_id": profile.user_id,
        "display_name": profile.display_name,
        "primary_trade": profile.primary_trade,
        "monthly_gross_income": profile.monthly_gross_income,
        "monthly_essentials": profile.monthly_essentials,
        "stability_fund_balance": profile.stability_fund_balance,
        "stability_fund_target_months": profile.stability_fund_target_months,
        "baseline_revenue_per_hour": profile.baseline_revenue_per_hour,
        "revenue_per_hour": profile.revenue_per_hour,
        "focus_season_active": profile.focus_season_active,
        "solitude_mode_active": profile.solitude_mode_active,
        "creation_hour": profile.creation_hour,
        "contract_signed": profile.contract_signed_at is not None,
        "onboarding_completed": profile.onboarding_completed,
        "intake_completed": profile.intake_completed_at is not None,
        "intake_step": profile.intake_step or 0,
        "data_source": profile.data_source or "none",
        "literacy_completed": completed,
    }


@router.post("/onboarding")
def complete_onboarding(
    body: OnboardingComplete,
    user_id: str = Query(default="default"),
    db: Session = Depends(get_db),
):
    profile = _get_or_create_profile(db, user_id)
    profile.display_name = body.display_name
    profile.primary_trade = body.primary_trade
    profile.monthly_gross_income = body.monthly_gross_income
    profile.monthly_essentials = body.monthly_essentials
    profile.stability_fund_balance = body.stability_fund_balance
    profile.stability_fund_target_months = body.stability_fund_target_months
    profile.baseline_revenue_per_hour = body.baseline_revenue_per_hour or body.revenue_per_hour
    profile.revenue_per_hour = body.revenue_per_hour
    profile.focus_season_active = body.focus_season_active
    profile.onboarding_completed = True
    db.commit()

    journey = assess_stage(
        monthly_essentials=profile.monthly_essentials,
        stability_fund_balance=profile.stability_fund_balance,
        stability_fund_target_months=profile.stability_fund_target_months,
        revenue_per_hour=profile.revenue_per_hour,
        baseline_revenue_per_hour=profile.baseline_revenue_per_hour,
    )

    return {
        "message": f"Welcome, {profile.display_name}. Your machine is initialized.",
        "identity_notification": "You are an architect who protects their future—not a worker who trades hours.",
        "onboarding_completed": True,
        "journey": journey,
    }


@router.patch("/profile")
def update_profile(
    body: ProfileUpdate,
    user_id: str = Query(default="default"),
    db: Session = Depends(get_db),
):
    profile = _get_or_create_profile(db, user_id)
    if not profile.onboarding_completed:
        raise HTTPException(status_code=400, detail="Complete onboarding first")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)
    db.commit()
    return get_profile(user_id=user_id, db=db)


@router.get("/journey")
def get_journey(user_id: str = Query(default="default"), db: Session = Depends(get_db)):
    profile = _get_or_create_profile(db, user_id)
    if not profile.onboarding_completed:
        return {
            "onboarding_required": True,
            "message": "Complete onboarding to see your Architect journey.",
            "stages_overview": list(STAGES),
        }

    journey = assess_stage(
        monthly_essentials=profile.monthly_essentials,
        stability_fund_balance=profile.stability_fund_balance,
        stability_fund_target_months=profile.stability_fund_target_months,
        revenue_per_hour=profile.revenue_per_hour,
        baseline_revenue_per_hour=profile.baseline_revenue_per_hour,
    )
    journey["display_name"] = profile.display_name
    journey["primary_trade"] = profile.primary_trade
    journey["focus_season_active"] = profile.focus_season_active
    journey["stages_overview"] = list(STAGES)
    journey["onboarding_required"] = False
    from backend.services.cashflow_quadrant import assess_from_profile

    journey["cashflow_quadrant"] = assess_from_profile(profile, journey["stage"])
    return journey


@router.get("/financial-summary")
def get_financial_summary(user_id: str = Query(default="default"), db: Session = Depends(get_db)):
    profile = _get_or_create_profile(db, user_id)
    if not profile.intake_completed_at and not profile.onboarding_completed:
        raise HTTPException(status_code=400, detail="Complete Financial Reality Intake first")
    return build_financial_summary(profile)


@router.get("/literacy/playbook")
def list_wealth_playbook(
    category: str | None = Query(default=None),
    tag: str | None = Query(default=None),
):
    if category and category not in PLAYBOOK_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"category must be one of: {PLAYBOOK_CATEGORIES}")
    return {"categories": list(PLAYBOOK_CATEGORIES), "entries": get_playbook(category=category, tag=tag)}


@router.get("/literacy/modules")
def list_literacy_modules():
    return {"modules": get_modules()}


@router.get("/literacy/modules/{module_id}")
def get_literacy_module(module_id: str):
    module = get_module(module_id)
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")
    return module


@router.post("/literacy/progress")
def save_literacy_progress(
    body: LiteracyProgress,
    user_id: str = Query(default="default"),
    db: Session = Depends(get_db),
):
    profile = _get_or_create_profile(db, user_id)
    completed = set(json.loads(profile.literacy_completed_json or "[]"))
    if body.completed:
        completed.add(body.module_id)
    else:
        completed.discard(body.module_id)
    profile.literacy_completed_json = json.dumps(sorted(completed))
    db.commit()
    return {"literacy_completed": sorted(completed)}


@router.post("/footprints/connect")
def connect_footprints(
    body: FootprintConnect,
    user_id: str = Query(default="default"),
    db: Session = Depends(get_db),
):
    profile = _get_or_create_profile(db, user_id)
    profile.footprints_json = json.dumps(body.model_dump())
    db.commit()
    audit = generate_clinical_audit(
        banking_connected=body.banking,
        calendar_connected=body.calendar,
        screen_connected=body.screen_time,
        profile=profile,
    )
    return {"connected": body.model_dump(), "audit_preview": audit}


@router.get("/clinical-audit")
def get_clinical_audit(user_id: str = Query(default="default"), db: Session = Depends(get_db)):
    profile = _get_or_create_profile(db, user_id)
    footprints = json.loads(profile.footprints_json or "{}")
    audit = generate_clinical_audit(
        banking_connected=footprints.get("banking", False),
        calendar_connected=footprints.get("calendar", False),
        screen_connected=footprints.get("screen_time", False),
        profile=profile,
    )
    return audit


@router.post("/clinical-audit/acknowledge")
def acknowledge_patterns(
    body: list[PatternAcknowledge],
    user_id: str = Query(default="default"),
    db: Session = Depends(get_db),
):
    profile = _get_or_create_profile(db, user_id)
    accepted = [p.pattern_id for p in body if p.accepted]
    return {"patterns_acknowledged": accepted, "count": len(accepted)}


@router.post("/contract/sign")
def sign_architect_contract(
    body: ContractSign,
    user_id: str = Query(default="default"),
    db: Session = Depends(get_db),
):
    profile = _get_or_create_profile(db, user_id)
    footprints = json.loads(profile.footprints_json or "{}")
    audit = generate_clinical_audit(
        banking_connected=footprints.get("banking", False),
        calendar_connected=footprints.get("calendar", False),
        screen_connected=footprints.get("screen_time", False),
        profile=profile,
    )
    if not audit.get("ready"):
        raise HTTPException(status_code=400, detail="Connect footprints and review audit first")

    derived = derive_profile_from_audit(audit, body.display_name)
    for key, val in derived.items():
        setattr(profile, key, val)

    profile.audit_json = json.dumps(audit)
    profile.contract_signed_at = datetime.now(timezone.utc)
    profile.onboarding_completed = True
    profile.focus_season_active = True
    db.commit()

    journey = assess_stage(
        monthly_essentials=profile.monthly_essentials,
        stability_fund_balance=profile.stability_fund_balance,
        stability_fund_target_months=profile.stability_fund_target_months,
        revenue_per_hour=profile.revenue_per_hour,
        baseline_revenue_per_hour=profile.baseline_revenue_per_hour,
    )

    return {
        "contract_signed": True,
        "focus_season_months": body.focus_season_months,
        "identity_notification": (
            "You signed with your future self. For six months, you act as an architect—not a reactor."
        ),
        "journey": journey,
    }


@router.post("/focus-season")
def toggle_focus_season(
    body: FocusSeasonToggle,
    user_id: str = Query(default="default"),
    db: Session = Depends(get_db),
):
    profile = _get_or_create_profile(db, user_id)
    if not profile.onboarding_completed:
        raise HTTPException(status_code=400, detail="Complete Clinical Life Audit first")
    profile.focus_season_active = body.active
    profile.solitude_mode_active = body.active
    profile.creation_hour = body.creation_hour
    db.commit()
    return {
        "focus_season_active": profile.focus_season_active,
        "solitude_mode_active": profile.solitude_mode_active,
        "creation_hour": profile.creation_hour,
        "ux_mode": "minimalist" if body.active else "standard",
        "identity_notification": (
            "Creation Hour protected. Noise suppressed—you are building, not consuming."
            if body.active
            else "Standard mode restored."
        ),
    }
