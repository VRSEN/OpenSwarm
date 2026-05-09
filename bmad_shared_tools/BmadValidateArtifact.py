from __future__ import annotations

import json
from typing import Literal

from pydantic import Field

from bmad_shared_tools.bmad_utils import resolve_repo_path, validate_artifact_file
from bmad_shared_tools.compat import BaseTool


class BmadValidateArtifact(BaseTool):
    """
    Validates a BMAD artifact for required metadata, required sections, and status/handoff coherence.
    """

    file_path: str = Field(..., description="Absolute or repo-relative path to the BMAD markdown artifact to validate")
    artifact_kind: Literal["planning", "implementation"] | None = Field(
        None,
        description="Optional expected artifact kind. If provided, validation will fail when the path/stage suggests a different kind.",
    )

    class ToolConfig:
        strict: bool = False

    def run(self) -> str:
        path = resolve_repo_path(self.file_path)
        if not path.exists():
            return json.dumps(
                {
                    "valid": False,
                    "file_path": str(path),
                    "errors": [
                        {
                            "code": "file_not_found",
                            "message": f"File not found: {path}",
                            "severity": "error",
                        }
                    ],
                    "warnings": [],
                },
                indent=2,
                ensure_ascii=False,
            )

        result = validate_artifact_file(path, artifact_kind=self.artifact_kind)
        return json.dumps(result.to_dict(path), indent=2, ensure_ascii=False)
