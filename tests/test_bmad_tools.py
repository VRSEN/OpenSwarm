from __future__ import annotations

import importlib
import json

from bmad_shared_tools.BmadInstantiateTemplate import BmadInstantiateTemplate
from bmad_shared_tools.BmadValidateArtifact import BmadValidateArtifact
from bmad_shared_tools.BmadValidateDirectory import BmadValidateDirectory

instantiate_module = importlib.import_module("bmad_shared_tools.BmadInstantiateTemplate")


def test_instantiate_template_creates_expected_markdown(tmp_path, monkeypatch):
    artifact_dir = tmp_path / "planning-artifacts"
    monkeypatch.setattr(instantiate_module, "resolve_output_dir", lambda _: artifact_dir)

    tool = BmadInstantiateTemplate(
        template_name="prd",
        artifact_kind="planning",
        artifact_name="sample-prd",
        title="Sample PRD",
        artifact_id="PRD-001",
        owner_agent="BMAD Product Manager",
        recommended_next_agent="BMAD Architect",
        status="draft",
        project="OpenSwarm",
        source_inputs=["brief.md"],
        open_questions=["What is the MVP boundary?"],
        variables={"executive_summary": "Summary text"},
    )

    result = tool.run()
    created = artifact_dir / "sample-prd.md"

    assert created.exists()
    text = created.read_text(encoding="utf-8")
    assert "artifact_id: PRD-001" in text
    assert "stage: planning" in text
    assert "Summary text" in text
    assert "What is the MVP boundary?" in text
    assert "output_path:" in result


def test_validate_artifact_accepts_valid_prd(tmp_path):
    file_path = tmp_path / "prd.md"
    file_path.write_text(
        """# Metadata

```yaml
artifact_type: prd
artifact_id: PRD-001
status: ready
owner_agent: BMAD Product Manager
stage: planning
project: OpenSwarm
last_updated: 2026-01-01
source_inputs:
  - brief.md
recommended_next_agent: BMAD Architect
recommended_next_workflow: bmad-create-architecture
open_questions:
  - None
blocking_issues: []
```

# Status

- Current status: ready

# Product Requirements Document

# Executive Summary

Summary

# Product Vision

Vision

# Problem and Opportunity

Problem

# Target Users

- User

# User Journeys

- Journey

# Functional Requirements

- Requirement

# Non-Functional Requirements

- Requirement

# Success Metrics

- Metric

# Constraints and Dependencies

- Constraint

# Out of Scope

- Out

# Risks

- Risk

# Open Questions

- None

# Readiness Verdict

Ready

# Next Step

- Hand off to BMAD Architect
""",
        encoding="utf-8",
    )

    result = json.loads(BmadValidateArtifact(file_path=str(file_path)).run())
    assert result["valid"] is True
    assert result["errors"] == []


def test_validate_artifact_flags_missing_heading_and_blocked_rules(tmp_path):
    file_path = tmp_path / "story.md"
    file_path.write_text(
        """# Metadata

```yaml
artifact_type: story
artifact_id: STORY-001
status: blocked
owner_agent: BMAD Developer
stage: implementation
project: OpenSwarm
last_updated: 2026-01-01
source_inputs:
  - architecture.md
recommended_next_agent: BMAD Developer
open_questions: []
blocking_issues: []
```

# Status

- Current status: blocked

# Story Title

# Context

Context

# Description

Description

# Acceptance Criteria

- One

# Dependencies

- None

# Implementation Notes

- Note

# Test Notes

- Note

# Next Step

Escalate issue.
""",
        encoding="utf-8",
    )

    result = json.loads(BmadValidateArtifact(file_path=str(file_path)).run())
    error_codes = {issue["code"] for issue in result["errors"]}
    assert "blocked_requires_blocking_issues" in error_codes
    assert "missing_required_heading" in error_codes


def test_validate_directory_reports_mixed_results(tmp_path):
    valid_file = tmp_path / "valid-prd.md"
    invalid_file = tmp_path / "invalid-story.md"

    valid_file.write_text(
        """# Metadata

```yaml
artifact_type: prd
artifact_id: PRD-002
status: ready
owner_agent: BMAD Product Manager
stage: planning
project: OpenSwarm
last_updated: 2026-01-01
source_inputs:
  - brief.md
recommended_next_agent: BMAD Architect
open_questions: []
blocking_issues: []
```

# Status

- Current status: ready

# PRD

# Executive Summary

Summary

# Product Vision

Vision

# Problem and Opportunity

Problem

# Target Users

- User

# User Journeys

- Journey

# Functional Requirements

- Requirement

# Non-Functional Requirements

- Requirement

# Success Metrics

- Metric

# Constraints and Dependencies

- Constraint

# Out of Scope

- Out

# Risks

- Risk

# Open Questions

- None

# Readiness Verdict

Ready

# Next Step

- Hand off
""",
        encoding="utf-8",
    )

    invalid_file.write_text(
        """# Metadata

```yaml
artifact_type: architecture
artifact_id: ARCH-001
status: ready
owner_agent: BMAD Product Manager
stage: planning
project: OpenSwarm
last_updated: 2026-01-01
source_inputs:
  - prd.md
recommended_next_agent: BMAD Developer
open_questions: []
blocking_issues: []
```

# Status

- Current status: ready

# Architecture

# Next Step

- Hand off
""",
        encoding="utf-8",
    )

    result = json.loads(BmadValidateDirectory(directory_path=str(tmp_path)).run())
    assert result["files_checked"] == 2
    assert result["files_failed"] == 1
    assert result["valid"] is False
    assert any(report["valid"] is False for report in result["reports"])
