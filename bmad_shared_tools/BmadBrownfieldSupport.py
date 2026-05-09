from __future__ import annotations

import json
from typing import Literal

from pydantic import Field

from bmad_shared_tools.bmad_utils import analyze_project_tree, resolve_repo_path, summarize_markdown_artifacts
from bmad_shared_tools.compat import BaseTool


class BmadBrownfieldSupport(BaseTool):
    """
    Produces reusable brownfield support outputs for BMAD workflows such as project documentation,
    project context generation, quick development context, and course correction analysis.
    """

    project_root: str = Field(..., description="Absolute or repo-relative root directory of the project to analyze")
    mode: Literal["document-project", "generate-project-context", "quick-dev", "correct-course"] = Field(
        ...,
        description="Brownfield workflow mode to execute",
    )
    artifact_directory: str | None = Field(
        None,
        description="Optional BMAD artifact directory to summarize alongside the project analysis",
    )
    max_depth: int = Field(4, description="Maximum directory depth to inspect when building the project tree")

    class ToolConfig:
        strict: bool = False

    def run(self) -> str:
        project_root = resolve_repo_path(self.project_root)
        if not project_root.exists() or not project_root.is_dir():
            return json.dumps(
                {
                    "ok": False,
                    "mode": self.mode,
                    "errors": [f"Project root not found: {project_root}"],
                },
                indent=2,
                ensure_ascii=False,
            )

        analysis = analyze_project_tree(project_root, max_depth=self.max_depth)
        artifact_summary = []
        if self.artifact_directory:
            artifact_dir = resolve_repo_path(self.artifact_directory)
            if artifact_dir.exists() and artifact_dir.is_dir():
                artifact_summary = summarize_markdown_artifacts(artifact_dir, recursive=True)

        payload = {
            "ok": True,
            "mode": self.mode,
            "project_root": str(project_root),
            "project_analysis": analysis,
            "artifact_summary": artifact_summary,
            "workflow_guidance": self._workflow_guidance(analysis, artifact_summary),
        }
        return json.dumps(payload, indent=2, ensure_ascii=False)

    def _workflow_guidance(self, analysis: dict, artifact_summary: list[dict]) -> dict:
        extensions = analysis.get("extensions", {})
        top_extensions = sorted(extensions.items(), key=lambda item: item[1], reverse=True)[:5]
        open_artifacts = [item for item in artifact_summary if item.get("status") not in {None, "ready", "superseded"}]

        if self.mode == "document-project":
            return {
                "goal": "Create baseline brownfield documentation for the current codebase.",
                "recommended_artifacts": ["project-scan", "product-brief", "project-context"],
                "notes": [
                    f"Top file types detected: {top_extensions}",
                    f"Open BMAD artifacts already present: {len(open_artifacts)}",
                ],
            }

        if self.mode == "generate-project-context":
            return {
                "goal": "Generate implementation-facing context from the existing repository state.",
                "recommended_artifacts": ["project-context", "architecture", "readiness-report"],
                "notes": [
                    "Use the tree summary to identify integration boundaries and module ownership.",
                    f"Relevant open artifacts: {[item.get('artifact_id') for item in open_artifacts]}",
                ],
            }

        if self.mode == "quick-dev":
            return {
                "goal": "Create a lightweight implementation starting point for an incremental change.",
                "recommended_artifacts": ["story"],
                "notes": [
                    "Prefer a narrow story with explicit affected paths.",
                    f"Most common file types in repo: {top_extensions}",
                ],
            }

        return {
            "goal": "Support correction of course when delivery artifacts drift from the codebase or priorities change.",
            "recommended_artifacts": ["readiness-report", "architecture", "story"],
            "notes": [
                "Compare current implementation constraints with latest planning artifacts.",
                f"Open artifacts requiring attention: {[item.get('artifact_id') for item in open_artifacts]}",
            ],
        }
