"""Generate pitch card slides under ./mnt from intake data."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.services.financial_intake import build_financial_summary
from backend.services.journey_engine import assess_stage
from backend.services.pdf_export import write_pdf_from_html
from backend.services.pitch_card_templates import render_pitch_card_html


def _mnt_presentations_dir(user_id: str) -> Path:
    slug = user_id.replace("-", "_").lower() or "default"
    return Path(__file__).resolve().parents[2] / "mnt" / f"architect_pitchcards_{slug}" / "presentations"


def generate_pitch_card(
    profile,
    *,
    template_id: str,
    formats: list[str] | None = None,
) -> dict[str, Any]:
    summary = build_financial_summary(profile)
    journey = assess_stage(
        monthly_essentials=profile.monthly_essentials or 0,
        stability_fund_balance=profile.stability_fund_balance or 0,
        stability_fund_target_months=profile.stability_fund_target_months or 4,
        revenue_per_hour=profile.revenue_per_hour or 0,
        baseline_revenue_per_hour=profile.baseline_revenue_per_hour or 0,
    )

    requested = formats or ["html", "pdf"]
    allowed = {"html", "pdf"}
    out_formats = [f for f in requested if f in allowed] or ["html"]

    html = render_pitch_card_html(template_id, summary, journey)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    doc_base = f"pitch_{template_id}_{stamp}"
    pres_dir = _mnt_presentations_dir(profile.user_id)
    pres_dir.mkdir(parents=True, exist_ok=True)
    mnt_root = pres_dir.parent.parent

    files: list[dict[str, str]] = []
    html_path = pres_dir / f"{doc_base}.html"
    source_html = pres_dir / f"{doc_base}.source.html"

    if "html" in out_formats:
        html_path.write_text(html, encoding="utf-8")
        source_html.write_text(html, encoding="utf-8")
        rel = html_path.relative_to(mnt_root).as_posix()
        files.append(
            {
                "format": "html",
                "path": rel,
                "download_url": f"/studio/files/{rel}",
                "preview_url": f"/studio/files/{rel}",
                "preview_type": "pitch_card",
            }
        )
    else:
        source_html.write_text(html, encoding="utf-8")

    if "pdf" in out_formats:
        pdf_path = pres_dir / f"{doc_base}.pdf"
        try:
            write_pdf_from_html(source_html, pdf_path)
            rel = pdf_path.relative_to(mnt_root).as_posix()
            files.append(
                {
                    "format": "pdf",
                    "path": rel,
                    "download_url": f"/studio/files/{rel}",
                    "preview_url": f"/studio/files/{rel}",
                    "preview_type": "pdf",
                }
            )
        except RuntimeError:
            if not files:
                raise

    preview = next((f for f in files if f.get("preview_type") == "pitch_card"), files[0] if files else None)

    return {
        "template_id": template_id,
        "document_name": doc_base,
        "project": pres_dir.parent.name,
        "files": files,
        "preview": preview,
        "summary_preview": {
            "display_name": summary.get("display_name"),
            "primary_trade": summary.get("primary_trade"),
            "badge": (summary.get("cashflow_quadrant") or {}).get("badge"),
        },
    }
