from __future__ import annotations

import json
from typing import Literal

from pydantic import Field

from bmad_shared_tools.bmad_utils import collect_markdown_files, resolve_repo_path, validate_artifact_file
from bmad_shared_tools.compat import BaseTool


class BmadValidateDirectory(BaseTool):
    """
    Validates all BMAD markdown artifacts in a directory and returns a per-file report.
    """

    directory_path: str = Field(..., description="Absolute or repo-relative directory path to scan for BMAD markdown artifacts")
    recursive: bool = Field(True, description="If true, scans subdirectories recursively")
    artifact_kind: Literal["planning", "implementation"] | None = Field(
        None,
        description="Optional expected artifact kind for all files in the directory",
    )

    class ToolConfig:
        strict: bool = False

    def run(self) -> str:
        directory = resolve_repo_path(self.directory_path)

        if not directory.exists() or not directory.is_dir():
            return json.dumps(
                {
                    "valid": False,
                    "directory_path": str(directory),
                    "errors": [
                        {
                            "code": "directory_not_found",
                            "message": f"Directory not found: {directory}",
                            "severity": "error",
                        }
                    ],
                    "warnings": [],
                },
                indent=2,
                ensure_ascii=False,
            )

        reports = []
        files_failed = 0
        total_errors = 0
        total_warnings = 0

        for file_path in collect_markdown_files(directory, recursive=self.recursive):
            result = validate_artifact_file(file_path, artifact_kind=self.artifact_kind)
            report = result.to_dict(file_path)
            reports.append(report)
            if not result.valid:
                files_failed += 1
            total_errors += len(report["errors"])
            total_warnings += len(report["warnings"])

        return json.dumps(
            {
                "valid": files_failed == 0,
                "directory_path": str(directory),
                "files_checked": len(reports),
                "files_failed": files_failed,
                "total_errors": total_errors,
                "total_warnings": total_warnings,
                "reports": reports,
            },
            indent=2,
            ensure_ascii=False,
        )
