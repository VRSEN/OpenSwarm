"""Utilities for managing document project directories."""

import re
from pathlib import Path


_DOCUMENT_SUFFIXES = (".source.html", ".html", ".docx", ".md", ".pdf", ".txt")


def get_mnt_dir() -> Path:
    return Path("/app/mnt") if Path("/.dockerenv").is_file() else Path(__file__).parents[3] / "mnt"


def get_project_dir(project_name: str) -> Path:
    return get_mnt_dir() / validate_path_component(project_name, "project_name") / "documents"


def validate_path_component(value: str, field_name: str) -> str:
    """Return a safe single path component or raise ValueError.

    Document tools accept user-provided project and file names. Keep those names
    inside the managed mnt tree by rejecting separators, absolute paths, parent
    traversal, and NUL bytes before composing paths.
    """
    component = str(value or "").strip()
    if not component:
        raise ValueError(f"{field_name} must not be empty.")
    if "\x00" in component:
        raise ValueError(f"{field_name} must not contain NUL bytes.")
    if "/" in component or "\\" in component:
        raise ValueError(f"{field_name} must be a name, not a path.")
    if component in {".", ".."}:
        raise ValueError(f"{field_name} must not be a relative path marker.")
    if Path(component).is_absolute():
        raise ValueError(f"{field_name} must not be an absolute path.")
    return component


def normalize_document_name(document_name: str) -> str:
    name = validate_path_component(document_name, "document_name")
    for suffix in _DOCUMENT_SUFFIXES:
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break
    return validate_path_component(name, "document_name")


def normalize_docx_filename(docx_filename: str) -> str:
    name = validate_path_component(docx_filename, "docx_filename")
    if not name.endswith(".docx"):
        name = f"{name}.docx"
    stem = name[: -len(".docx")]
    validate_path_component(stem, "docx_filename")
    return name


def next_docx_version(desired: Path) -> Path:
    """Return desired if it doesn't exist, otherwise the next free _vN path.

    Strips any existing _vN suffix before searching so passing report_v2.docx
    when that file already exists yields report_v3.docx, not report_v2_v2.docx.
    """
    if not desired.exists():
        return desired
    base = re.sub(r"_v\d+$", "", desired.stem)
    n = 2
    while True:
        candidate = desired.parent / f"{base}_v{n}{desired.suffix}"
        if not candidate.exists():
            return candidate
        n += 1
