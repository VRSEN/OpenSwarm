"""PDF export from HTML (WeasyPrint when available)."""

from __future__ import annotations

from pathlib import Path


def write_pdf_from_html(html_source: Path, pdf_path: Path) -> None:
    try:
        from weasyprint import HTML
    except (ImportError, OSError) as exc:
        raise RuntimeError(
            "PDF generation unavailable — install weasyprint and system libraries (GTK on Windows). "
            "HTML downloads still work."
        ) from exc

    try:
        HTML(filename=str(html_source)).write_pdf(str(pdf_path))
    except OSError as exc:
        raise RuntimeError(
            "PDF generation failed — WeasyPrint system libraries may be missing. "
            "Use HTML download or Print to PDF from the preview."
        ) from exc
