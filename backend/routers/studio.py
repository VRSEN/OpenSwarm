"""Studio — deliverables, templates, previews, file downloads."""

import mimetypes

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.user_profile import UserProfile
from backend.services.financial_report_generator import generate_financial_report
from backend.services.financial_report_templates import list_report_templates
from backend.services.pitch_card_generator import generate_pitch_card
from backend.services.pitch_card_templates import list_pitch_card_templates
from backend.services.studio_artifacts import list_artifacts, safe_mnt_path

router = APIRouter(prefix="/studio", tags=["studio"])

_INLINE_TYPES = {
    ".pdf": "application/pdf",
    ".html": "text/html",
    ".htm": "text/html",
    ".md": "text/plain; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".mp4": "video/mp4",
    ".webm": "video/webm",
}


class GenerateReportBody(BaseModel):
    template_id: str = Field(..., min_length=1)
    formats: list[str] = Field(default_factory=lambda: ["pdf", "html", "markdown"])


class GeneratePitchCardBody(BaseModel):
    template_id: str = Field(..., min_length=1)
    formats: list[str] = Field(default_factory=lambda: ["html", "pdf"])


def _get_profile(db: Session, user_id: str) -> UserProfile:
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Complete Financial Reality Intake first")
    if not profile.intake_completed_at and not profile.onboarding_completed:
        raise HTTPException(status_code=400, detail="Complete Financial Reality Intake first")
    if not (profile.monthly_gross_income or 0) > 0:
        raise HTTPException(status_code=400, detail="Add your income in intake before generating reports")
    return profile


@router.get("/report-templates")
def studio_report_templates():
    return {"templates": list_report_templates()}


@router.get("/pitch-card-templates")
def studio_pitch_card_templates():
    return {"templates": list_pitch_card_templates()}


@router.post("/reports/generate")
def studio_generate_report(
    body: GenerateReportBody,
    user_id: str = Query(default="default"),
    db: Session = Depends(get_db),
):
    profile = _get_profile(db, user_id)
    valid_ids = {t["id"] for t in list_report_templates()}
    if body.template_id not in valid_ids:
        raise HTTPException(status_code=400, detail=f"Unknown template. Choose from: {', '.join(sorted(valid_ids))}")

    try:
        return generate_financial_report(
            profile,
            template_id=body.template_id,
            formats=body.formats,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/pitch-cards/generate")
def studio_generate_pitch_card(
    body: GeneratePitchCardBody,
    user_id: str = Query(default="default"),
    db: Session = Depends(get_db),
):
    profile = _get_profile(db, user_id)
    valid_ids = {t["id"] for t in list_pitch_card_templates()}
    if body.template_id not in valid_ids:
        raise HTTPException(status_code=400, detail=f"Unknown template. Choose from: {', '.join(sorted(valid_ids))}")

    try:
        return generate_pitch_card(
            profile,
            template_id=body.template_id,
            formats=body.formats,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/artifacts")
def studio_artifacts(limit: int = 80):
    return {"artifacts": list_artifacts(limit=limit)}


@router.get("/files/{filepath:path}")
def studio_download(filepath: str, inline: bool = Query(default=False)):
    target = safe_mnt_path(filepath)
    if not target:
        raise HTTPException(status_code=404, detail="File not found")

    ext = target.suffix.lower()
    media_type = _INLINE_TYPES.get(ext) or mimetypes.guess_type(target.name)[0]
    headers = {}
    disposition = "inline" if inline else "attachment"
    headers["Content-Disposition"] = f'{disposition}; filename="{target.name}"'

    return FileResponse(
        path=str(target),
        filename=target.name,
        media_type=media_type,
        headers=headers,
    )
