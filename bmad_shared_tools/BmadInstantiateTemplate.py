from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from bmad_shared_tools.bmad_utils import (
    TEMPLATE_STAGE_BY_NAME,
    load_template,
    normalize_artifact_type,
    render_template,
    resolve_output_dir,
    utc_today,
)
from bmad_shared_tools.compat import BaseTool


class BmadInstantiateTemplate(BaseTool):
    """
    Instantiates a BMAD template, populates metadata and body placeholders, and writes the artifact
    into _bmad-output/planning-artifacts/ or _bmad-output/implementation-artifacts/.
    """

    template_name: str = Field(..., description="Template name under _bmad/custom/templates, with or without .md suffix")
    artifact_kind: Literal["planning", "implementation"] = Field(
        ..., description="Target artifact family. planning writes to planning-artifacts, implementation writes to implementation-artifacts"
    )
    artifact_name: str = Field(..., description="Output artifact file name, with or without .md extension")
    title: str = Field(..., description="Document title to inject into the template")
    artifact_id: str = Field(..., description="Unique artifact identifier, e.g. PRD-001 or STORY-003")
    owner_agent: str = Field(..., description="Agent responsible for producing the artifact")
    recommended_next_agent: str = Field(..., description="Agent recommended to receive the next handoff")
    recommended_next_workflow: str | None = Field(
        None, description="Optional next workflow identifier, e.g. bmad-create-architecture"
    )
    status: Literal["draft", "in_review", "ready", "blocked", "superseded"] = Field(
        "draft", description="Artifact lifecycle status"
    )
    project: str = Field(..., description="Project name stored in artifact metadata")
    source_inputs: list[str] = Field(
        default_factory=list,
        description="Source artifact paths or other inputs used to produce this artifact",
    )
    open_questions: list[str] = Field(
        default_factory=list,
        description="Open questions to include in metadata list form",
    )
    blocking_issues: list[str] = Field(
        default_factory=list,
        description="Blocking issues to include in metadata list form",
    )
    variables: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional placeholder values for the template body",
        json_schema_extra={"type": "object", "additionalProperties": True, "properties": {}},
    )

    class ToolConfig:
        strict: bool = False

    def run(self) -> str:
        template = load_template(self.template_name)
        output_dir = resolve_output_dir(self.artifact_kind)
        output_dir.mkdir(parents=True, exist_ok=True)

        file_name = self.artifact_name if self.artifact_name.endswith(".md") else f"{self.artifact_name}.md"
        output_path = output_dir / file_name
        today = utc_today()
        artifact_type = normalize_artifact_type(self.template_name)
        template_stage = TEMPLATE_STAGE_BY_NAME.get(artifact_type)
        stage = template_stage or ("implementation" if self.artifact_kind == "implementation" else "planning")

        metadata_values = {
            "artifact_type": artifact_type,
            "artifact_id": self.artifact_id,
            "status": self.status,
            "owner_agent": self.owner_agent,
            "stage": stage,
            "project": self.project,
            "last_updated": today,
            "recommended_next_agent": self.recommended_next_agent,
            "recommended_next_workflow": self.recommended_next_workflow or "",
        }

        list_values = {
            "source_inputs_yaml": self._yaml_list(self.source_inputs),
            "open_questions_yaml": self._yaml_list(self.open_questions, default_empty="[]"),
            "blocking_issues_yaml": self._yaml_list(self.blocking_issues, default_empty="[]"),
            "open_questions_body": self._body_list(self.open_questions, empty_placeholder="- None at this stage."),
        }

        default_values = {
            "title": self.title,
            "decision_needed": self.variables.get("decision_needed", "None"),
            "ready_for_next_stage": self.variables.get("ready_for_next_stage", "No"),
            "readiness_verdict": self.variables.get("readiness_verdict", "Pending review"),
            "architecture_review": self.variables.get("architecture_review", "Pending review"),
            "ready_for_implementation_planning": self.variables.get("ready_for_implementation_planning", "No"),
            "story_validation": self.variables.get("story_validation", "Pending review"),
            "ready_for_development": self.variables.get("ready_for_development", "No"),
            "readiness_score": self.variables.get("readiness_score", "TBD"),
            "next_step": self._default_next_step(),
        }

        rendered = render_template(
            template,
            {
                **metadata_values,
                **list_values,
                **default_values,
                **self._default_body_values(),
                **self.variables,
            },
        )

        output_path.write_text(rendered, encoding="utf-8")

        return (
            f"BMAD artifact created successfully\n"
            f"template: {self.template_name}\n"
            f"output_path: {output_path}\n"
            f"artifact_kind: {self.artifact_kind}\n"
            f"artifact_type: {artifact_type}\n"
            f"artifact_id: {self.artifact_id}\n"
            f"status: {self.status}"
        )

    def _default_next_step(self) -> str:
        workflow = self.recommended_next_workflow or "<define-workflow>"
        return (
            f"- Recommended next agent: {self.recommended_next_agent}\n"
            f"- Recommended next workflow: {workflow}\n"
            f"- Required action: review artifact {self.artifact_id} and proceed with the BMAD handoff."
        )

    @staticmethod
    def _yaml_list(items: list[str], default_empty: str | None = None) -> str:
        if not items:
            return default_empty if default_empty is not None else "  - <add-item>"
        return "\n".join(f"  - {item}" for item in items)

    @staticmethod
    def _body_list(items: list[str], empty_placeholder: str = "- None.") -> str:
        if not items:
            return empty_placeholder
        return "\n".join(f"- {item}" for item in items)

    @staticmethod
    def _default_body_values() -> dict[str, str]:
        placeholder = "TBD"
        bullet_placeholder = "- TBD"
        return {
            "executive_summary": placeholder,
            "problem_statement": placeholder,
            "target_users_and_stakeholders": bullet_placeholder,
            "goals": bullet_placeholder,
            "non_goals": bullet_placeholder,
            "constraints": bullet_placeholder,
            "assumptions": bullet_placeholder,
            "risks": bullet_placeholder,
            "evidence_and_inputs_used": bullet_placeholder,
            "product_vision": placeholder,
            "problem_and_opportunity": placeholder,
            "target_users": bullet_placeholder,
            "user_journeys": bullet_placeholder,
            "functional_requirements": bullet_placeholder,
            "non_functional_requirements": bullet_placeholder,
            "success_metrics": bullet_placeholder,
            "constraints_and_dependencies": bullet_placeholder,
            "out_of_scope": bullet_placeholder,
            "readiness_notes": placeholder,
            "system_context": placeholder,
            "architectural_drivers": bullet_placeholder,
            "proposed_architecture": placeholder,
            "components_and_responsibilities": bullet_placeholder,
            "data_and_integration_flows": bullet_placeholder,
            "technology_choices": bullet_placeholder,
            "risks_and_tradeoffs": bullet_placeholder,
            "context": placeholder,
            "description": placeholder,
            "acceptance_criteria": bullet_placeholder,
            "dependencies": bullet_placeholder,
            "implementation_notes": bullet_placeholder,
            "test_notes": bullet_placeholder,
            "validation_notes": bullet_placeholder,
            "scope_reviewed": bullet_placeholder,
            "findings": bullet_placeholder,
            "gaps": bullet_placeholder,
            "recommendations": bullet_placeholder,
        }
