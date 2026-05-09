from __future__ import annotations

import json

from pydantic import Field

from bmad_shared_tools.bmad_utils import collect_markdown_files, resolve_repo_path, validate_artifact_file
from bmad_shared_tools.compat import BaseTool


class BmadQaCheck(BaseTool):
    """
    Runs a BMAD QA pass over a directory and summarizes release readiness, blocking issues,
    and artifacts that still require review.
    """

    directory_path: str = Field(..., description="Absolute or repo-relative directory containing BMAD artifacts")
    recursive: bool = Field(True, description="If true, scans subdirectories recursively")

    class ToolConfig:
        strict: bool = False

    def run(self) -> str:
        directory = resolve_repo_path(self.directory_path)
        if not directory.exists() or not directory.is_dir():
            return json.dumps(
                {
                    "ok": False,
                    "errors": [f"Directory not found: {directory}"],
                },
                indent=2,
                ensure_ascii=False,
            )

        reports = []
        for file_path in collect_markdown_files(directory, recursive=self.recursive):
            result = validate_artifact_file(file_path)
            report = result.to_dict(file_path)
            reports.append(report)

        blocking = [r for r in reports if any(issue["severity"] == "error" for issue in r["errors"])]
        in_review = [r for r in reports if r["extracted_metadata"].get("status") in {"draft", "in_review", "blocked"}]
        ready = [r for r in reports if r["extracted_metadata"].get("status") == "ready" and r["valid"]]

        payload = {
            "ok": True,
            "directory_path": str(directory),
            "summary": {
                "artifacts_checked": len(reports),
                "blocking_artifacts": len(blocking),
                "artifacts_in_review": len(in_review),
                "release_ready_artifacts": len(ready),
            },
            "workflow": {
                "qa_gate": [
                    "1. Validate all planning and implementation artifacts.",
                    "2. Resolve every error-level issue before marking the stream release-ready.",
                    "3. Review warning-level issues for handoff and completeness drift.",
                    "4. Publish a readiness or QA report artifact for stakeholder visibility.",
                ]
            },
            "blocking_artifacts": [
                {
                    "file_path": report["file_path"],
                    "artifact_id": report["extracted_metadata"].get("artifact_id"),
                    "errors": report["errors"],
                }
                for report in blocking
            ],
            "artifacts_in_review": [
                {
                    "file_path": report["file_path"],
                    "artifact_id": report["extracted_metadata"].get("artifact_id"),
                    "status": report["extracted_metadata"].get("status"),
                }
                for report in in_review
            ],
        }
        return json.dumps(payload, indent=2, ensure_ascii=False)
