"""
Insert blank slide placeholders before a position.

Uses task_brief to plan outline and execution order. Slide content is generated later via ModifySlide.
Do not use in parallel with other tools.
"""

import asyncio
import json
import re
import threading
from pathlib import Path
from typing import Literal

import os
from agency_swarm import Agent, ModelSettings, Reasoning
from agency_swarm.tools import BaseTool
from agents.extensions.models.litellm_model import LitellmModel
from pydantic import BaseModel, Field, ValidationError

from .slide_file_utils import (
    apply_renames,
    build_slide_name,
    compute_pad_width,
    get_project_dir,
    list_slide_files,
)
from .slide_html_utils import ensure_full_html
from .template_registry import load_template_index


_PLANNER_MODEL_CLAUDE = "anthropic/claude-sonnet-4-6"
_PLANNER_MODEL_OAI = "gpt-5.2-codex"


class _PlanSlide(BaseModel):
    page: int
    title: str
    content: str
    template_key: str | None = None
    template_name: str | None = None
    template_status: Literal["existing", "new"] | None = None
    depends_on: int | None = None


class _PlanResponse(BaseModel):
    slides: list[_PlanSlide]


def _make_planner_agent(caller_model=None) -> Agent:
    """Create a fresh, stateless agent instance for one InsertNewSlides call.

    Model priority:
    1. ANTHROPIC_API_KEY in env → Claude Sonnet 4.6 (best planning quality)
    2. caller_model → inherit from the calling agent (covers /auth TUI flow)
    """
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if anthropic_key:
        model = LitellmModel(model=_PLANNER_MODEL_CLAUDE, api_key=anthropic_key)
    else:
        model = caller_model or _PLANNER_MODEL_OAI
    return Agent(
        name="Slide Planner",
        description="Creates structured slide outline plans.",
        instructions=(
            "You generate JSON plans for slide creation. "
            "Output must be valid JSON only, no markdown fences, no extra text."
        ),
        tools=[],
        model=model,
        model_settings=ModelSettings(
            reasoning=Reasoning(effort="high", summary="auto"),
            verbosity="medium",
        ),
    )


def _run_awaitable(awaitable):
    box: dict[str, object] = {}
    err: dict[str, BaseException] = {}

    def _worker() -> None:
        try:
            box["result"] = asyncio.run(awaitable)
        except BaseException as exc:  # noqa: BLE001
            err["error"] = exc

    thread = threading.Thread(
        target=_worker,
        name="insert-slides-awaitable-worker",
        daemon=True,
    )
    thread.start()
    thread.join(timeout=180)
    if thread.is_alive():
        raise TimeoutError("InsertNewSlides planner timed out after 180s")
    if "error" in err:
        raise err["error"]
    return box.get("result")


def _extract_json_block(text: str) -> str:
    raw = (text or "").strip()
    if not raw:
        return ""
    match = re.search(r"```(?:json)?\s*(.*?)```", raw, flags=re.IGNORECASE | re.DOTALL)
    return (match.group(1) if match else raw).strip()


def _build_planner_prompt(
    task_brief: str,
    count: int,
    insert_position: int,
    existing_templates: dict[str, dict[str, str]],
) -> str:
    template_lines = []
    for key, value in existing_templates.items():
        name = str(value.get("name", key))
        template_lines.append(f'- "{key}": "{name}"')
    template_block = "\n".join(template_lines) if template_lines else "(none)"
    return (
        "Create a structured plan for inserting blank slides. "
        "Return JSON only with shape:\n"
        '{ "slides": [ { "page": int, "title": str, "content": str, "template_key": str|null, "template_name": str|null, "template_status": "existing"|"new"|null, "depends_on": int|null } ] }\n'
        f"Constraints:\n- exactly {count} slides\n"
        f"- pages must be contiguous from {insert_position} to {insert_position + count - 1}\n"
        "- concise titles; content should describe WHAT the slide covers (topic and key points), not HOW it should look — no layout instructions, no column descriptions, no visual prescriptions\n"
        "- (CRITICAL) No inline code snippets or code blocks.\n\n"
        "Template assignment rules (CRITICAL):\n"
        "- A template represents a LAYOUT PATTERN, not an individual slide. By default, assign each slide its own unique template_key.\n"
        "- Only share a template_key across slides when the layout is genuinely identical (e.g. a repeated content card format). Reuse templates only when fitting and do not reuse them often.\n"
        "- Never reuse a template just to save keys. Distinct slides deserve distinct templates.\n"
        "- Never use the same template for adjacent slides.\n"
        "- When multiple slides do share a template_key, only the FIRST slide gets template_status 'new'. All subsequent slides get template_status 'existing'.\n"
        "  Example: slides 2, 5, 9 all use layout 'two_col_content'. Slide 2: template_status 'new'. Slides 5, 9: template_status 'existing'.\n\n"
        "Sequential rule:\n"
        "- depends_on is null by default and should almost always stay null.\n"
        "- Only set it when this slide is a direct continuation of another slide's specific content (e.g. 'Part 2 of X' that cannot be written without knowing what Part 1 said). Narrative flow, thematic progression, or being 'related to' another slide are NOT valid reasons.\n"
        f"Task brief:\n{task_brief.strip()}\n\n"
        f"Existing templates:\n{template_block}\n"
    )


def _infer_template_key(title: str) -> str:
    """Infer a stable template key from full page title text."""
    raw = re.sub(r"[^a-z0-9\s]+", " ", title.lower())
    words = [
        w for w in raw.split() if w and w not in {"and", "the", "of", "to", "for", "in"}
    ]
    if not words:
        return "content_default"
    return "_".join(words)


def _pretty_template_name(template_key: str) -> str:
    return " ".join(part.capitalize() for part in template_key.split("_"))


def _normalize_outline(
    plan: _PlanResponse,
    count: int,
    insert_position: int,
    existing_templates: dict[str, dict[str, str]],
) -> list[dict[str, str | int]]:
    existing_keys = set(existing_templates.keys())
    rows: list[dict[str, str | int]] = []
    for i in range(count):
        page = insert_position + i
        src = (
            plan.slides[i]
            if i < len(plan.slides)
            else _PlanSlide(page=page, title=f"Slide {i + 1}", content="Content")
        )
        title = src.title.strip() if src.title else f"Slide {i + 1}"
        content = src.content.strip() if src.content else title
        key = (src.template_key or "").strip() or _infer_template_key(title)
        if key in existing_keys:
            status = "existing"
            name = existing_templates.get(key, {}).get(
                "name", _pretty_template_name(key)
            )
        else:
            # Respect the planner's intra-batch reuse declaration: if the planner
            # says "existing" for a key not in the registry, it means a previous
            # slide in this batch creates the template and this slide reuses it.
            status = "existing" if src.template_status == "existing" else "new"
            name = (src.template_name or "").strip() or _pretty_template_name(key)
        rows.append(
            {
                "page": page,
                "title": title,
                "content": content,
                "template_key": key,
                "template_name": name,
                "template_status": status,
                "depends_on": src.depends_on,
            }
        )
    return rows


def _build_creation_steps(outline: list[dict]) -> list[list[dict]]:
    """Group outline rows into parallel execution steps via DAG level assignment.

    Each slide's level is the maximum level of its dependencies plus one:
    - Content dependency (depends_on page P) → level ≥ level(P) + 1
    - Template dependency (reuses a template created in this batch by page P)
      → level ≥ level(P) + 1

    Slides with no dependencies go to level 0 (step 1) regardless of their
    position in the outline.  All slides at the same level can run in parallel.
    """
    # Map template_key → page number of the first "new" creator in this batch
    key_creator: dict[str, int] = {}
    for row in outline:
        key = row.get("template_key") or ""
        if row.get("template_status") == "new" and key not in key_creator:
            key_creator[key] = row["page"]

    page_level: dict[int, int] = {}
    for row in outline:
        page = row["page"]
        level = 0

        dep = row.get("depends_on")
        if dep is not None and dep in page_level:
            level = max(level, page_level[dep] + 1)

        key = row.get("template_key") or ""
        if row.get("template_status") == "existing":
            creator = key_creator.get(key)
            if creator is not None and creator in page_level:
                level = max(level, page_level[creator] + 1)

        page_level[page] = level

    max_level = max(page_level.values(), default=0)
    return [
        [row for row in outline if page_level[row["page"]] == lvl]
        for lvl in range(max_level + 1)
        if any(page_level[row["page"]] == lvl for row in outline)
    ]


class InsertNewSlides(BaseTool):
    """
    Insert new slides before a specified page position.

    Uses task_brief to generate an outline/plan while creating blank placeholders.
    For 2+ slides, the outline includes serial vs parallel guidance for ModifySlide calls.
    Do not use this tool in parallel with other tools — call it independently.
    """

    class ToolConfig:
        one_call_at_a_time: bool = True

    project_name: str = Field(
        ...,
        description="Name of the presentation project",
    )
    task_brief: str = Field(
        ...,
        max_length=2000,
        description="Brief description of what content will be created in these new pages. Used for outline/plan generation.",
    )
    approximate_page_count: int = Field(
        ...,
        ge=1,
        le=20,
        description="Number of blank slide placeholders to insert (1-20). Content is added later with ModifySlide.",
    )
    insert_position: int = Field(
        default=1,
        ge=1,
        description="Page number (1-based) before which to insert. insert_position=1 means at the beginning, insert_position=3 means before page 3.",
    )
    file_prefix: str = Field(
        default="slide",
        description="Prefix of the slide file names (e.g. slide_01, slide_02).",
    )

    def run(self):
        """Insert blank placeholders and return a planning-oriented response."""
        project_dir = get_project_dir(self.project_name)
        project_dir.mkdir(parents=True, exist_ok=True)

        slides = list_slide_files(project_dir, self.file_prefix)
        pad_width = compute_pad_width(slides, extra_count=self.approximate_page_count)
        insert_position = self.insert_position
        n = self.approximate_page_count
        existing_templates = load_template_index(project_dir)

        # Rename existing slides that are at or after insert position
        rename_map: dict[Path, Path] = {}
        for s in slides:
            if s.index >= insert_position:
                new_name = build_slide_name(
                    self.file_prefix, s.index + n, pad_width, s.suffix
                )
                rename_map[s.path] = project_dir / new_name
        apply_renames(rename_map)

        planner = _make_planner_agent(caller_model=getattr(self._caller_agent, "model", None))
        prompt = _build_planner_prompt(
            self.task_brief, n, insert_position, existing_templates
        )
        plan_result = _run_awaitable(planner.get_response(prompt))
        plan_text = _extract_json_block(
            str(getattr(plan_result, "final_output", "") or "")
        )
        if not plan_text:
            return "❌ Outline generation failed: planner returned empty output."
        try:
            plan_obj = _PlanResponse.model_validate(json.loads(plan_text))
        except (json.JSONDecodeError, ValidationError) as exc:
            return (
                f"❌ Outline generation failed: planner returned invalid JSON ({exc})."
            )

        # Write blank slide placeholders (no content generation here)
        created: list[str] = []
        outline = _normalize_outline(plan_obj, n, insert_position, existing_templates)
        blank_html, _ = ensure_full_html("")
        for i in range(n):
            idx = insert_position + i
            name = build_slide_name(self.file_prefix, idx, pad_width, "")
            path = project_dir / name
            path.write_text(blank_html, encoding="utf-8")
            created.append(name)

        total_after_insert = len(slides) + n
        lines = [
            "Successfully generated outline",
            "",
            "**Summary:**",
            f"- {n} new blank slide placeholder(s) created",
            f"- {len({row['template_key'] for row in outline})} template key(s) planned",
            f"- Insert positions: Before page {insert_position} (inserted at positions: {insert_position} to {insert_position + n - 1})",
            f"- Total slides in presentation: {total_after_insert} slides",
            "",
            "**Slide Outline:**",
        ]
        for row in outline:
            page = row["page"]
            lines.append(f"**Page {page}:**")
            lines.append(f"- Title: {row['title']}")
            if row["content"] != row["title"]:
                lines.append(f"- Content: {row['content']}")
            lines.append(f"- Template Name: {row['template_name']}")
            lines.append(f"- Template Key: {row['template_key']}")
            lines.append(f"- Template Status: {row['template_status']}")
            lines.append("")

        steps = _build_creation_steps(outline)

        lines.append("**Creation Order:**")
        for step_num, step_rows in enumerate(steps, start=1):
            prev = f" (after Step {step_num - 1} completes)" if step_num > 1 else ""
            pages = ", ".join(str(r["page"]) for r in step_rows)
            if len(step_rows) == 1:
                row = step_rows[0]
                dep = row.get("depends_on")
                note = f" — create after slide {dep} is generated" if dep is not None else ""
                lines.append(f"Step {step_num}: Create page {pages}{prev}{note}")
            else:
                lines.append(f"Step {step_num}: Create pages {pages} IN PARALLEL{prev}")
                lines.append("These pages can be created simultaneously:")
                for row in step_rows:
                    tag = "creates new template" if row["template_status"] == "new" else "uses existing template"
                    lines.append(f"- Page {row['page']}: '{row['template_key']}' ({tag})")
            lines.append("")

        lines.extend(
            [
                "",
                "**Current Status:**",
                f"The presentation now has {total_after_insert} page placeholders.",
                "Use ModifySlide to generate slide HTML according to the creation order above.",
                "Important: insert_new_slides must be called independently (not in parallel).",
            ]
        )
        return "\n".join(lines)

if __name__ == "__main__":
    
    agent = InsertNewSlides(
        project_name="test",
        task_brief="Create a presentation about the benefits of using AI",
        approximate_page_count=7,
        insert_position=1,
        file_prefix="slide",
    )
    print(agent.run())