"""Multi-purpose document editing tool supporting targeted search-and-replace and line operations."""

import traceback
from pathlib import Path
from typing import Any, Literal, Optional

from agency_swarm.tools import BaseTool
from pydantic import Field

from .utils.doc_file_utils import get_project_dir, normalize_document_name
from .utils.html_validation import build_unsupported_error, find_unsupported_html


class ModifyDocument(BaseTool):
    """
    Edit a document's HTML source.

    Supports two modes:

    **search_and_replace** (preferred for targeted edits):
    Provide a list of {old_content, new_content} pairs. Each old_content is matched
    exactly against the file — like StrReplace. Use a snippet that is unique enough to
    identify the target (can be short or long). Replacements apply sequentially; if one
    fails, the rest are skipped and the file is not modified.

    **Line operations** (for structural additions/deletions):
    - replace: replace a line range with new content
    - insert: insert content before/after a line
    - delete: remove a line range

    Always call ViewDocument first to see the current content and line numbers.
    The DOCX is not regenerated on edit — call ConvertDocument when ready to export.
    """

    project_name: str = Field(
        ...,
        description="Name of the project folder containing the document.",
    )

    document_name: str = Field(
        ...,
        description="Name of the document to edit (without extension).",
    )

    operation: Literal["search_and_replace", "replace", "insert", "delete"] = Field(
        ...,
        description=(
            "Edit mode:\n"
            "- 'search_and_replace': batch exact-match replacements (preferred)\n"
            "- 'replace': replace lines start_line–end_line with new_content\n"
            "- 'insert': insert new_content before/after start_line\n"
            "- 'delete': delete lines start_line–end_line"
        ),
    )

    # --- search_and_replace fields ---
    replacements: Optional[list[dict[str, Any]]] = Field(
        default=None,
        description=(
            "Required for 'search_and_replace'. List of {old_content, new_content} dicts.\n"
            "Each old_content is matched exactly against the file (like StrReplace).\n"
            "Use a snippet that uniquely identifies the target — any length is fine.\n"
            "Replacements apply in order; the first failure stops the batch.\n\n"
            "Example:\n"
            '  [{"old_content": "#C8102E", "new_content": "#DA291C"},\n'
            '   {"old_content": "<h1>Old Title</h1>", "new_content": "<h1>New Title</h1>"}]'
        ),
    )

    # --- line operation fields ---
    start_line: Optional[int] = Field(
        default=None,
        description="Starting line number (1-based). Required for line operations.",
    )

    end_line: Optional[int] = Field(
        default=None,
        description="Ending line number (inclusive). Required for 'replace' and 'delete'.",
    )

    new_content: Optional[str] = Field(
        default=None,
        description="New HTML content. Required for 'replace' and 'insert'.",
    )

    after: bool = Field(
        default=False,
        description="For 'insert' only: insert AFTER start_line instead of before.",
    )

    def run(self) -> str:
        try:
            project_dir = get_project_dir(self.project_name)
            if not project_dir.exists():
                return f"Error: Project '{self.project_name}' not found."

            doc_name = normalize_document_name(self.document_name)
            source_path = project_dir / f"{doc_name}.source.html"
            md_path = project_dir / f"{doc_name}.md"

            if not source_path.exists() and not md_path.exists():
                return f"Error: Document '{doc_name}' not found in project '{self.project_name}'."

            editing_markdown = not source_path.exists()
            current_content = (
                md_path.read_text(encoding="utf-8")
                if editing_markdown
                else source_path.read_text(encoding="utf-8")
            )

            if self.operation == "search_and_replace":
                return self._search_and_replace(current_content, source_path, md_path, editing_markdown)

            lines = current_content.split("\n")
            total_lines = len(lines)

            if self.operation == "replace":
                return self._replace_lines(lines, total_lines, doc_name, source_path, md_path, editing_markdown)
            if self.operation == "insert":
                return self._insert_lines(lines, total_lines, doc_name, source_path, md_path, editing_markdown)
            if self.operation == "delete":
                return self._delete_lines(lines, total_lines, doc_name, source_path, md_path, editing_markdown)

            return f"Error: Unknown operation '{self.operation}'."

        except Exception as e:
            return f"Error modifying document: {type(e).__name__}: {e}\n{traceback.format_exc()}"

    # ── search_and_replace ────────────────────────────────────────────────────

    def _search_and_replace(self, content: str, source_path: Path, md_path: Path, editing_markdown: bool) -> str:
        if not self.replacements:
            return "Error: 'replacements' is required for search_and_replace operation."

        updated = content
        for i, item in enumerate(self.replacements, start=1):
            old = item.get("old_content", "")
            new = item.get("new_content", "")
            if old not in updated:
                snippet = old[:80].replace("\n", "↵")
                return (
                    f"Error: replacement #{i} — 'old_content' not found in document.\n"
                    f"Snippet: '{snippet}'\n"
                    f"Tip: copy a shorter or more unique fragment directly from ViewDocument output and retry."
                )
            updated = updated.replace(old, new, 1)

        error = self._validate_and_save(updated, source_path, md_path, editing_markdown)
        if error:
            return error

        count = len(self.replacements)
        return f"Applied {count} replacement{'s' if count != 1 else ''} to '{source_path.name}'."

    # ── line operations ───────────────────────────────────────────────────────

    def _replace_lines(self, lines, total_lines, doc_name, source_path, md_path, editing_markdown):
        if not self.new_content:
            return "Error: 'new_content' is required for replace operation."
        if not self.end_line:
            return "Error: 'end_line' is required for replace operation."
        if not self.start_line:
            return "Error: 'start_line' is required for replace operation."

        if self.start_line < 1 or self.start_line > total_lines:
            return f"Error: Invalid start_line {self.start_line}. Document has {total_lines} lines."
        if self.end_line < self.start_line or self.end_line > total_lines:
            return f"Error: Invalid end_line {self.end_line}. Must be >= start_line and <= {total_lines}."

        start_idx, end_idx = self.start_line - 1, self.end_line
        lines_removed = end_idx - start_idx
        del lines[start_idx:end_idx]
        lines.insert(start_idx, self.new_content)

        error = self._validate_and_save("\n".join(lines), source_path, md_path, editing_markdown)
        if error:
            return error

        net = len(lines) - total_lines
        return (
            f"Replaced lines {self.start_line}–{self.end_line} in '{doc_name}'.\n"
            f"Removed {lines_removed} lines, added {len(self.new_content.splitlines())}. "
            f"Net: {'+' if net >= 0 else ''}{net}. Total: {len(lines)} lines."
        )

    def _insert_lines(self, lines, total_lines, doc_name, source_path, md_path, editing_markdown):
        if not self.new_content:
            return "Error: 'new_content' is required for insert operation."
        if not self.start_line:
            return "Error: 'start_line' is required for insert operation."

        if self.start_line < 1 or self.start_line > total_lines + 1:
            return f"Error: Invalid start_line {self.start_line}. Valid range: 1–{total_lines + 1}."

        insert_idx = self.start_line if self.after else self.start_line - 1
        lines.insert(insert_idx, self.new_content)

        error = self._validate_and_save("\n".join(lines), source_path, md_path, editing_markdown)
        if error:
            return error

        position = f"after line {self.start_line}" if self.after else f"before line {self.start_line}"
        return (
            f"Inserted content {position} in '{doc_name}'. "
            f"Added {len(self.new_content.splitlines())} line(s). Total: {len(lines)} lines."
        )

    def _delete_lines(self, lines, total_lines, doc_name, source_path, md_path, editing_markdown):
        if not self.end_line:
            return "Error: 'end_line' is required for delete operation."
        if not self.start_line:
            return "Error: 'start_line' is required for delete operation."

        if self.start_line < 1 or self.start_line > total_lines:
            return f"Error: Invalid start_line {self.start_line}. Document has {total_lines} lines."
        if self.end_line < self.start_line or self.end_line > total_lines:
            return f"Error: Invalid end_line {self.end_line}. Must be >= start_line and <= {total_lines}."

        start_idx, end_idx = self.start_line - 1, self.end_line
        deleted = end_idx - start_idx
        del lines[start_idx:end_idx]

        error = self._validate_and_save("\n".join(lines), source_path, md_path, editing_markdown)
        if error:
            return error

        return (
            f"Deleted lines {self.start_line}–{self.end_line} from '{doc_name}'. "
            f"Removed {deleted} line(s). Total: {len(lines)} lines."
        )

    # ── shared save ──────────────────────────────────────────────────────────

    def _validate_and_save(self, content: str, source_path: Path, md_path: Path, editing_markdown: bool) -> str | None:
        """Write content to disk. Returns an error string on failure, None on success."""
        if editing_markdown:
            md_path.write_text(content, encoding="utf-8")
            return None

        issues = find_unsupported_html(content)
        if issues:
            return build_unsupported_error(issues)

        source_path.write_text(content, encoding="utf-8")
        return None
