"""Restore an HTML document source from a previous DOCX export snapshot."""

from pathlib import Path

from agency_swarm.tools import BaseTool
from pydantic import Field

from .utils.doc_file_utils import get_project_dir, normalize_docx_filename


class RestoreDocument(BaseTool):
    """
    Restore the working HTML source of a document to the state it was in at
    a previous DOCX export.

    Every time ConvertDocument produces a .docx it automatically saves a
    companion snapshot alongside it:

        report.docx
        report.docx.snapshot.html   ← HTML source at time of that export
        report_v2.docx
        report_v2.docx.snapshot.html

    This tool reads the snapshot for the requested DOCX version and writes
    it back as the canonical <document>.source.html, ready for further edits
    or re-conversion.

    To list available versions use ListDocuments — each .docx file in the
    project is one export.
    """

    project_name: str = Field(
        ...,
        description="Name of the project folder containing the document.",
    )
    docx_filename: str = Field(
        ...,
        description=(
            "Filename of the DOCX export to restore from, e.g. 'report.docx' "
            "or 'report_v2.docx'. The file must exist in the project folder."
        ),
    )

    def run(self) -> str:
        try:
            project_dir = get_project_dir(self.project_name)
            docx_name = normalize_docx_filename(self.docx_filename)
            snapshot_path = project_dir / f"{docx_name}.snapshot.html"

            if not snapshot_path.exists():
                available = sorted(
                    p.name for p in project_dir.glob("*.docx.snapshot.html")
                )
                hint = (
                    "\nAvailable snapshots:\n" + "\n".join(f"  {s}" for s in available)
                    if available
                    else "\nNo snapshots found in this project."
                )
                return f"Error: No snapshot found for '{docx_name}'.{hint}"

            doc_name = Path(docx_name).stem
            doc_name = _strip_version(doc_name)
            source_path = project_dir / f"{doc_name}.source.html"

            source_path.write_text(snapshot_path.read_text(encoding="utf-8"), encoding="utf-8")

            return (
                f"Restored '{doc_name}' to the version captured in '{docx_name}'.\n"
                f"Working source: {source_path}"
            )
        except Exception as e:
            return f"Error restoring document: {str(e)}"


def _strip_version(stem: str) -> str:
    """Remove trailing _vN suffix so report_v2 → report."""
    import re
    return re.sub(r"_v\d+$", "", stem)
