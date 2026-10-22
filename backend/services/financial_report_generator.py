"""Generate financial report files under ./mnt from intake data."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.services.financial_intake import build_financial_summary
from backend.services.financial_report_templates import render_report_html, render_report_markdown
from backend.services.journey_engine import assess_stage
from backend.services.pdf_export import write_pdf_from_html


def _mnt_documents_dir(user_id: str) -> Path:
    slug = user_id.replace("-", "_").lower() or "default"
    return Path(__file__).resolve().parents[2] / "mnt" / f"architect_reports_{slug}" / "documents"


def _slug_template(template_id: str) -> str:
    return template_id.replace("-", "_")


def generate_financial_report(
    profile,
    *,
    template_id: str,
    formats: list[str] | None = None,
) -> dict[str, Any]:
    """Render template and write files. Returns paths relative to mnt/."""
    summary = build_financial_summary(profile)
    journey = assess_stage(
        monthly_essentials=profile.monthly_essentials or 0,
        stability_fund_balance=profile.stability_fund_balance or 0,
        stability_fund_target_months=profile.stability_fund_target_months or 4,
        revenue_per_hour=profile.revenue_per_hour or 0,
        baseline_revenue_per_hour=profile.baseline_revenue_per_hour or 0,
    )

    requested = formats or ["html", "markdown", "pdf"]
    allowed = {"html", "markdown", "pdf", "md"}
    out_formats = [f if f != "md" else "markdown" for f in requested if f in allowed]
    if not out_formats:
        out_formats = ["html", "markdown"]

    markdown = render_report_markdown(template_id, summary, journey)
    html = render_report_html(template_id, summary, journey)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    doc_base = f"{_slug_template(template_id)}_{stamp}"
    doc_dir = _mnt_documents_dir(profile.user_id)
    doc_dir.mkdir(parents=True, exist_ok=True)
    (doc_dir / "assets").mkdir(exist_ok=True)

    files: list[dict[str, str]] = []
    mnt_root = doc_dir.parent.parent

    if "markdown" in out_formats:
        md_path = doc_dir / f"{doc_base}.md"
        md_path.write_text(markdown, encoding="utf-8")
        rel = md_path.relative_to(mnt_root).as_posix()
        files.append(
            {
                "format": "markdown",
                "path": rel,
                "download_url": f"/studio/files/{rel}",
                "preview_type": "markdown",
            }
        )

    source_html = doc_dir / f"{doc_base}.source.html"
    html_path = doc_dir / f"{doc_base}.html"
    if "html" in out_formats:
        source_html.write_text(html, encoding="utf-8")
        html_path.write_text(html, encoding="utf-8")
        rel = html_path.relative_to(mnt_root).as_posix()
        files.append(
            {
                "format": "html",
                "path": rel,
                "download_url": f"/studio/files/{rel}",
                "preview_url": f"/studio/files/{rel}",
                "preview_type": "html",
            }
        )
    else:
        source_html.write_text(html, encoding="utf-8")

    if "pdf" in out_formats:
        pdf_path = doc_dir / f"{doc_base}.pdf"
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
            # HTML/Markdown still delivered when PDF libs unavailable (common on Windows).

    preview = _pick_preview(files)

    return {
        "template_id": template_id,
        "document_name": doc_base,
        "project": doc_dir.parent.name,
        "files": files,
        "preview": preview,
        "summary_preview": {
            "display_name": summary.get("display_name"),
            "stage": journey.get("stage"),
            "monthly_gross_income": summary.get("monthly_gross_income"),
        },
    }


def _pick_preview(files: list[dict]) -> dict | None:
    order = ("html", "pdf", "pitch_card", "markdown", "image")
    for kind in order:
        for f in files:
            if f.get("preview_type") == kind or (kind == "pitch_card" and f.get("preview_type") == "pitch_card"):
                return f
    for f in files:
        if f.get("preview_url"):
            return f
    return files[0] if files else None
