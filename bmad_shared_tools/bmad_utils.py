from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
CUSTOM_ROOT = REPO_ROOT / "_bmad" / "custom"
TEMPLATES_ROOT = CUSTOM_ROOT / "templates"
OUTPUT_ROOT = REPO_ROOT / "_bmad-output"
PLANNING_OUTPUT = OUTPUT_ROOT / "planning-artifacts"
IMPLEMENTATION_OUTPUT = OUTPUT_ROOT / "implementation-artifacts"
METADATA_SCHEMA_PATH = CUSTOM_ROOT / "schemas" / "artifact-metadata.schema.json"
ARTIFACT_GUIDE_PATH = CUSTOM_ROOT / "guides" / "artifact-contracts.md"

VALID_STATUSES = {"draft", "in_review", "ready", "blocked", "superseded"}
VALID_OWNER_AGENTS = {
    "BMAD Business Analyst",
    "BMAD Product Manager",
    "BMAD Architect",
    "BMAD Developer",
    "BMAD Technical Writer",
}
FINAL_HANDOFF_TARGETS = {"Docs Agent", "stakeholder", "stakeholders", "final stakeholder", "final stakeholders"}
OWNER_HANDOFFS = {
    "BMAD Business Analyst": {"BMAD Product Manager"},
    "BMAD Product Manager": {"BMAD Architect"},
    "BMAD Architect": {"BMAD Developer", "BMAD Technical Writer"},
    "BMAD Developer": {"BMAD Developer", "BMAD Architect", "BMAD Technical Writer"},
    "BMAD Technical Writer": FINAL_HANDOFF_TARGETS,
}
ARTIFACT_RULES = {
    "product-brief": {
        "stage": "analysis",
        "owner_agent": "BMAD Business Analyst",
        "recommended_next_agents": ["BMAD Product Manager"],
        "required_headings": [
            "# Metadata",
            "# Status",
            "# Executive Summary",
            "# Problem Statement",
            "# Target Users and Stakeholders",
            "# Goals",
            "# Non-Goals",
            "# Constraints",
            "# Assumptions",
            "# Risks",
            "# Open Questions",
            "# Evidence and Inputs Used",
            "# Next Step",
        ],
    },
    "prd": {
        "stage": "planning",
        "owner_agent": "BMAD Product Manager",
        "recommended_next_agents": ["BMAD Architect"],
        "required_headings": [
            "# Metadata",
            "# Status",
            "# Executive Summary",
            "# Product Vision",
            "# Problem and Opportunity",
            "# Target Users",
            "# User Journeys",
            "# Functional Requirements",
            "# Non-Functional Requirements",
            "# Success Metrics",
            "# Constraints and Dependencies",
            "# Out of Scope",
            "# Risks",
            "# Open Questions",
            "# Readiness Verdict",
            "# Next Step",
        ],
    },
    "architecture": {
        "stage": "solutioning",
        "owner_agent": "BMAD Architect",
        "recommended_next_agents": ["BMAD Developer"],
        "required_headings": [
            "# Metadata",
            "# Status",
            "# Executive Summary",
            "# System Context",
            "# Architectural Drivers",
            "# Proposed Architecture",
            "# Components and Responsibilities",
            "# Data and Integration Flows",
            "# Technology Choices",
            "# Risks and Trade-Offs",
            "# Open Questions",
            "# Next Step",
        ],
    },
    "story": {
        "stage": "implementation",
        "owner_agent": "BMAD Developer",
        "recommended_next_agents": ["BMAD Developer", "BMAD Architect", "BMAD Technical Writer"],
        "required_headings": [
            "# Metadata",
            "# Status",
            "# Context",
            "# Description",
            "# Acceptance Criteria",
            "# Dependencies",
            "# Implementation Notes",
            "# Test Notes",
            "# Validation Notes",
            "# Next Step",
        ],
    },
    "readiness-report": {
        "stage": "planning",
        "owner_agent": "BMAD Architect",
        "recommended_next_agents": ["BMAD Developer", "BMAD Technical Writer"],
        "required_headings": [
            "# Metadata",
            "# Status",
            "# Scope Reviewed",
            "# Findings",
            "# Gaps",
            "# Risks",
            "# Recommendations",
            "# Next Step",
        ],
    },
    "project-scan": {
        "stage": "analysis",
        "owner_agent": "BMAD Business Analyst",
        "recommended_next_agents": ["BMAD Product Manager", "BMAD Architect"],
        "required_headings": ["# Metadata", "# Status", "# Next Step"],
    },
    "project-context": {
        "stage": "solutioning",
        "owner_agent": "BMAD Architect",
        "recommended_next_agents": ["BMAD Developer", "BMAD Technical Writer"],
        "required_headings": ["# Metadata", "# Status", "# Next Step"],
    },
    "quick-dev": {
        "stage": "implementation",
        "owner_agent": "BMAD Developer",
        "recommended_next_agents": ["BMAD Developer", "BMAD Architect"],
        "required_headings": ["# Metadata", "# Status", "# Next Step"],
    },
    "correct-course": {
        "stage": "implementation",
        "owner_agent": "BMAD Architect",
        "recommended_next_agents": ["BMAD Developer", "BMAD Product Manager"],
        "required_headings": ["# Metadata", "# Status", "# Next Step"],
    },
    "qa-report": {
        "stage": "documentation",
        "owner_agent": "BMAD Technical Writer",
        "recommended_next_agents": ["Docs Agent", "stakeholders", "final stakeholders"],
        "required_headings": ["# Metadata", "# Status", "# QA Summary", "# Findings", "# Next Step"],
    },
}
TEMPLATE_STAGE_BY_NAME = {
    "product-brief": "analysis",
    "prd": "planning",
    "architecture": "solutioning",
    "story": "implementation",
    "readiness-report": "planning",
}
STAGE_BY_KIND = {
    "planning": "planning",
    "implementation": "implementation",
}
STATUS_EXPECTATIONS = {
    "draft": {"requires_next_step": True, "requires_blocking_issues": False},
    "in_review": {"requires_next_step": True, "requires_blocking_issues": False},
    "ready": {"requires_next_step": True, "requires_blocking_issues": False},
    "blocked": {"requires_next_step": True, "requires_blocking_issues": True},
    "superseded": {"requires_next_step": True, "requires_blocking_issues": False},
}
NON_CONTENT_HEADINGS = {"# Metadata", "# Status", "# Next Step"}
BROWNFIELD_WORKFLOWS = {"document-project", "generate-project-context", "quick-dev", "correct-course"}


@dataclass
class ParsedArtifact:
    file_path: Path
    raw_text: str
    metadata: dict[str, Any]
    headings: list[str]
    section_map: dict[str, str]
    next_step_content: str


@dataclass
class ValidationIssue:
    code: str
    message: str
    severity: str
    field: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = {"code": self.code, "message": self.message, "severity": self.severity}
        if self.field:
            data["field"] = self.field
        return data


@dataclass
class ValidationResult:
    valid: bool
    artifact_kind: str | None
    errors: list[ValidationIssue]
    warnings: list[ValidationIssue]
    metadata: dict[str, Any]
    headings: list[str]
    template_rule: dict[str, Any] | None

    def to_dict(self, file_path: Path) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "file_path": str(file_path),
            "artifact_kind": self.artifact_kind,
            "errors": [issue.to_dict() for issue in self.errors],
            "warnings": [issue.to_dict() for issue in self.warnings],
            "extracted_metadata": self.metadata,
            "headings": self.headings,
            "template_rule": self.template_rule,
        }


def utc_today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "artifact"


def load_metadata_schema() -> dict[str, Any]:
    return json.loads(METADATA_SCHEMA_PATH.read_text(encoding="utf-8"))


def extract_required_metadata_fields() -> list[str]:
    schema = load_metadata_schema()
    return list(schema.get("required", []))


def load_template(template_name: str) -> str:
    normalized = template_name if template_name.endswith(".md") else f"{template_name}.md"
    candidates = [
        TEMPLATES_ROOT / normalized,
        TEMPLATES_ROOT / normalized.replace(".md", "-template.md"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate.read_text(encoding="utf-8")
    searched = ", ".join(str(c) for c in candidates)
    raise FileNotFoundError(f"Template not found for '{template_name}'. Searched: {searched}")


def resolve_output_dir(artifact_kind: str) -> Path:
    if artifact_kind == "planning":
        return PLANNING_OUTPUT
    if artifact_kind == "implementation":
        return IMPLEMENTATION_OUTPUT
    raise ValueError(f"Unsupported artifact kind: {artifact_kind}")


def render_template(template: str, values: dict[str, Any]) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1).strip()
        value = values.get(key, "")
        if isinstance(value, list):
            return "\n".join(str(item) for item in value)
        if value is None:
            return ""
        return str(value)

    rendered = re.sub(r"\{\{\s*([^}]+?)\s*\}\}", replace, template)
    rendered = re.sub(r"\n{3,}", "\n\n", rendered).strip() + "\n"
    return rendered


def normalize_scalar(value: str) -> Any:
    stripped = value.strip()
    if stripped in {"[]", "[ ]"}:
        return []
    if stripped.lower() in {"null", "none"}:
        return None
    if stripped.lower() == "true":
        return True
    if stripped.lower() == "false":
        return False
    return stripped.strip('"').strip("'")


def parse_metadata_block(text: str) -> dict[str, Any]:
    match = re.search(r"^# Metadata\s*```yaml\s*(.*?)\s*```", text, re.DOTALL | re.MULTILINE)
    if not match:
        return {}

    block = match.group(1)
    metadata: dict[str, Any] = {}
    current_list_key: str | None = None

    for raw_line in block.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped:
            continue

        if stripped.startswith("- "):
            if current_list_key is None:
                continue
            metadata.setdefault(current_list_key, []).append(normalize_scalar(stripped[2:]))
            continue

        current_list_key = None
        if ":" not in line:
            continue

        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()

        if value == "":
            metadata[key] = []
            current_list_key = key
        else:
            metadata[key] = normalize_scalar(value)

    return metadata


def extract_headings(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if re.match(r"^#\s+", line.strip())]


def extract_section_map(text: str) -> dict[str, str]:
    pattern = re.compile(r"^(#\s+.+?)\s*$", flags=re.MULTILINE)
    matches = list(pattern.finditer(text))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        heading = match.group(1).strip()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[heading] = text[start:end].strip()
    return sections


def extract_section_content(text: str, heading: str) -> str:
    return extract_section_map(text).get(heading, "")


def parse_artifact(file_path: str | Path) -> ParsedArtifact:
    path = Path(file_path)
    raw_text = path.read_text(encoding="utf-8")
    metadata = parse_metadata_block(raw_text)
    headings = extract_headings(raw_text)
    section_map = extract_section_map(raw_text)
    next_step_content = section_map.get("# Next Step", "")
    return ParsedArtifact(
        file_path=path,
        raw_text=raw_text,
        metadata=metadata,
        headings=headings,
        section_map=section_map,
        next_step_content=next_step_content,
    )


def validate_metadata_shape(metadata: dict[str, Any]) -> tuple[list[ValidationIssue], list[ValidationIssue]]:
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []
    required_fields = extract_required_metadata_fields()

    for field in required_fields:
        value = metadata.get(field)
        if value in (None, "", []):
            errors.append(ValidationIssue("missing_metadata_field", f"Missing required metadata field: {field}", "error", field))

    status = metadata.get("status")
    if status and status not in VALID_STATUSES:
        errors.append(
            ValidationIssue(
                "invalid_status",
                f"Invalid status '{status}'. Allowed: {', '.join(sorted(VALID_STATUSES))}",
                "error",
                "status",
            )
        )

    stage = metadata.get("stage")
    allowed_stages = set(load_metadata_schema().get("properties", {}).get("stage", {}).get("enum", []))
    if stage and allowed_stages and stage not in allowed_stages:
        errors.append(
            ValidationIssue(
                "invalid_stage",
                f"Invalid stage '{stage}'. Allowed: {', '.join(sorted(allowed_stages))}",
                "error",
                "stage",
            )
        )

    for list_field in ("source_inputs", "open_questions", "blocking_issues"):
        if list_field in metadata and metadata[list_field] is not None and not isinstance(metadata[list_field], list):
            errors.append(
                ValidationIssue(
                    "invalid_list_field",
                    f"Metadata field '{list_field}' must be a list",
                    "error",
                    list_field,
                )
            )

    last_updated = metadata.get("last_updated")
    if last_updated:
        try:
            datetime.strptime(str(last_updated), "%Y-%m-%d")
        except ValueError:
            warnings.append(
                ValidationIssue(
                    "last_updated_format",
                    "Metadata field 'last_updated' should use YYYY-MM-DD format",
                    "warning",
                    "last_updated",
                )
            )

    artifact_id = metadata.get("artifact_id")
    if artifact_id and not re.match(r"^[A-Z]+(?:-[A-Z]+)?-\d{3,}$", str(artifact_id)):
        warnings.append(
            ValidationIssue(
                "artifact_id_format",
                "Artifact ID should normally follow a pattern like PRD-001 or STORY-003",
                "warning",
                "artifact_id",
            )
        )

    if metadata.get("owner_agent") and metadata["owner_agent"] not in VALID_OWNER_AGENTS:
        warnings.append(
            ValidationIssue(
                "unknown_owner_agent",
                f"Owner agent '{metadata['owner_agent']}' is not in the known BMAD owner list",
                "warning",
                "owner_agent",
            )
        )

    return errors, warnings


def validate_required_headings(parsed: ParsedArtifact, metadata: dict[str, Any]) -> tuple[list[ValidationIssue], list[ValidationIssue], dict[str, Any] | None]:
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []
    artifact_type = normalize_artifact_type(metadata.get("artifact_type"))
    rule = ARTIFACT_RULES.get(artifact_type)

    if not rule:
        warnings.append(
            ValidationIssue(
                "unknown_artifact_type",
                f"No template rule registered for artifact_type '{metadata.get('artifact_type')}'",
                "warning",
                "artifact_type",
            )
        )
        return errors, warnings, None

    for heading in rule.get("required_headings", []):
        if heading not in parsed.headings:
            errors.append(
                ValidationIssue(
                    "missing_required_heading",
                    f"Missing required heading for template '{artifact_type}': {heading}",
                    "error",
                    heading,
                )
            )

    for heading in rule.get("required_headings", []):
        if heading in NON_CONTENT_HEADINGS:
            continue
        if heading in parsed.section_map and not parsed.section_map[heading]:
            warnings.append(
                ValidationIssue(
                    "empty_required_section",
                    f"Required section is present but empty: {heading}",
                    "warning",
                    heading,
                )
            )

    return errors, warnings, rule


def validate_handoff(metadata: dict[str, Any], next_step_content: str) -> tuple[list[ValidationIssue], list[ValidationIssue]]:
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []

    owner = metadata.get("owner_agent")
    next_agent = metadata.get("recommended_next_agent")
    status = metadata.get("status")
    blocking_issues = metadata.get("blocking_issues") or []

    if not next_agent:
        errors.append(
            ValidationIssue(
                "missing_recommended_next_agent",
                "Missing recommended_next_agent in metadata",
                "error",
                "recommended_next_agent",
            )
        )
        return errors, warnings

    allowed_targets = OWNER_HANDOFFS.get(owner)
    if allowed_targets and next_agent not in allowed_targets:
        errors.append(
            ValidationIssue(
                "invalid_handoff",
                f"Inconsistent handoff: owner_agent '{owner}' should hand off to one of {sorted(allowed_targets)}, got '{next_agent}'",
                "error",
                "recommended_next_agent",
            )
        )

    if status in STATUS_EXPECTATIONS and STATUS_EXPECTATIONS[status]["requires_next_step"] and not next_step_content:
        errors.append(ValidationIssue("missing_next_step_content", "# Next Step section is present but empty", "error", "# Next Step"))

    if status == "blocked" and not blocking_issues:
        errors.append(
            ValidationIssue(
                "blocked_requires_blocking_issues",
                "Blocked artifacts must include at least one blocking issue in metadata",
                "error",
                "blocking_issues",
            )
        )

    if status == "blocked" and next_agent in FINAL_HANDOFF_TARGETS:
        warnings.append(
            ValidationIssue(
                "blocked_final_handoff",
                "Blocked artifact is being handed to a final stakeholder target; verify escalation is intended",
                "warning",
                "recommended_next_agent",
            )
        )

    if status == "ready" and next_agent == owner:
        warnings.append(
            ValidationIssue(
                "ready_same_owner",
                "Artifact is marked ready but recommended_next_agent is the same as owner_agent",
                "warning",
                "recommended_next_agent",
            )
        )

    if status == "superseded" and "supersed" not in next_step_content.lower():
        warnings.append(
            ValidationIssue(
                "superseded_without_reference",
                "Superseded artifacts should mention the replacement artifact or rationale in # Next Step",
                "warning",
                "# Next Step",
            )
        )

    return errors, warnings


def validate_artifact_consistency(metadata: dict[str, Any], rule: dict[str, Any] | None) -> tuple[list[ValidationIssue], list[ValidationIssue]]:
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []
    if not rule:
        return errors, warnings

    artifact_type = normalize_artifact_type(metadata.get("artifact_type"))
    stage = metadata.get("stage")
    owner_agent = metadata.get("owner_agent")
    next_agent = metadata.get("recommended_next_agent")

    expected_stage = rule.get("stage")
    if expected_stage and stage and stage != expected_stage:
        errors.append(
            ValidationIssue(
                "artifact_stage_mismatch",
                f"artifact_type '{artifact_type}' expects stage '{expected_stage}', got '{stage}'",
                "error",
                "stage",
            )
        )

    expected_owner = rule.get("owner_agent")
    if expected_owner and owner_agent and owner_agent != expected_owner:
        errors.append(
            ValidationIssue(
                "artifact_owner_mismatch",
                f"artifact_type '{artifact_type}' expects owner_agent '{expected_owner}', got '{owner_agent}'",
                "error",
                "owner_agent",
            )
        )

    allowed_next = set(rule.get("recommended_next_agents", []))
    if allowed_next and next_agent and next_agent not in allowed_next:
        warnings.append(
            ValidationIssue(
                "artifact_next_agent_mismatch",
                f"artifact_type '{artifact_type}' usually hands off to one of {sorted(allowed_next)}, got '{next_agent}'",
                "warning",
                "recommended_next_agent",
            )
        )

    return errors, warnings


def infer_artifact_kind(metadata: dict[str, Any], file_path: Path) -> str | None:
    if "implementation-artifacts" in file_path.parts:
        return "implementation"
    if "planning-artifacts" in file_path.parts:
        return "planning"
    stage = metadata.get("stage")
    if stage in {"planning", "solutioning", "analysis", "documentation"}:
        return "planning"
    if stage == "implementation":
        return "implementation"
    return None


def normalize_artifact_type(value: Any) -> str:
    return slugify(str(value or "")).replace("-template", "")


def resolve_repo_path(path_value: str | Path) -> Path:
    path = Path(path_value)
    if not path.is_absolute():
        path = (REPO_ROOT / path).resolve()
    return path


def validate_artifact_file(file_path: str | Path, artifact_kind: str | None = None) -> ValidationResult:
    path = resolve_repo_path(file_path)
    parsed = parse_artifact(path)
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []

    if not parsed.metadata:
        errors.append(ValidationIssue("missing_metadata_block", "Missing # Metadata YAML block", "error", "# Metadata"))

    metadata_errors, metadata_warnings = validate_metadata_shape(parsed.metadata)
    errors.extend(metadata_errors)
    warnings.extend(metadata_warnings)

    for heading in ["# Metadata", "# Status", "# Next Step"]:
        if heading not in parsed.headings:
            errors.append(ValidationIssue("missing_required_heading", f"Missing required heading: {heading}", "error", heading))

    rule_errors, rule_warnings, rule = validate_required_headings(parsed, parsed.metadata)
    errors.extend(rule_errors)
    warnings.extend(rule_warnings)

    handoff_errors, handoff_warnings = validate_handoff(parsed.metadata, parsed.next_step_content)
    errors.extend(handoff_errors)
    warnings.extend(handoff_warnings)

    consistency_errors, consistency_warnings = validate_artifact_consistency(parsed.metadata, rule)
    errors.extend(consistency_errors)
    warnings.extend(consistency_warnings)

    inferred_kind = infer_artifact_kind(parsed.metadata, path)
    if artifact_kind and inferred_kind and artifact_kind != inferred_kind:
        errors.append(
            ValidationIssue(
                "artifact_kind_mismatch",
                f"Artifact kind mismatch: expected '{artifact_kind}' but inferred '{inferred_kind}' from path/stage",
                "error",
                "artifact_kind",
            )
        )

    return ValidationResult(
        valid=len(errors) == 0,
        artifact_kind=inferred_kind,
        errors=errors,
        warnings=warnings,
        metadata=parsed.metadata,
        headings=parsed.headings,
        template_rule=rule,
    )


def collect_markdown_files(directory: str | Path, recursive: bool = True) -> list[Path]:
    root = resolve_repo_path(directory)
    pattern = "**/*.md" if recursive else "*.md"
    return sorted(path for path in root.glob(pattern) if path.is_file())


def analyze_project_tree(project_root: str | Path, max_depth: int = 4) -> dict[str, Any]:
    root = resolve_repo_path(project_root)
    file_count = 0
    ext_counts: dict[str, int] = {}
    tree_lines: list[str] = []

    def walk(current: Path, depth: int) -> None:
        nonlocal file_count
        if depth > max_depth:
            return
        entries = sorted(current.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        for entry in entries:
            rel = entry.relative_to(root)
            indent = "  " * depth
            if entry.is_dir():
                tree_lines.append(f"{indent}- {rel.as_posix()}/")
                walk(entry, depth + 1)
            else:
                tree_lines.append(f"{indent}- {rel.as_posix()}")
                file_count += 1
                ext = entry.suffix.lower() or "<no-ext>"
                ext_counts[ext] = ext_counts.get(ext, 0) + 1

    walk(root, 0)
    return {
        "project_root": str(root),
        "file_count": file_count,
        "extensions": dict(sorted(ext_counts.items())),
        "tree": tree_lines,
    }


def summarize_markdown_artifacts(directory: str | Path, recursive: bool = True) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for file_path in collect_markdown_files(directory, recursive=recursive):
        parsed = parse_artifact(file_path)
        summaries.append(
            {
                "file_path": str(file_path),
                "artifact_type": parsed.metadata.get("artifact_type"),
                "artifact_id": parsed.metadata.get("artifact_id"),
                "status": parsed.metadata.get("status"),
                "owner_agent": parsed.metadata.get("owner_agent"),
                "stage": parsed.metadata.get("stage"),
                "recommended_next_agent": parsed.metadata.get("recommended_next_agent"),
                "headings": parsed.headings,
            }
        )
    return summaries
