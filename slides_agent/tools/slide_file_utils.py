"""Utilities for managing HTML slide files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
import re
import uuid


ALLOWED_IMAGE_EXTENSIONS = frozenset(
    {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".svg", ".ico", ".avif"}
)

MAX_IMAGE_BYTES = 15 * 1024 * 1024

IMAGE_CHUNK_SIZE = 64 * 1024

_WINDOWS_DRIVE_RE = re.compile(r"^[a-zA-Z]:")


def validate_project_name(project_name: str) -> str:
    """Validate a presentation project name (single path segment)."""
    if not isinstance(project_name, str) or not project_name.strip():
        raise ValueError("Error: project_name must not be empty.")
    name = project_name.strip()
    if "\x00" in name:
        raise ValueError("Error: invalid project_name (null byte).")
    if "/" in name or "\\" in name:
        raise ValueError(
            f"Error: invalid project_name {name!r}: must be a plain directory name without path separators."
        )
    if Path(name).is_absolute() or _WINDOWS_DRIVE_RE.match(name):
        raise ValueError(f"Error: invalid project_name {name!r}: absolute paths are not allowed.")
    if name in (".", "..") or ".." in Path(name.replace("\\", "/")).parts:
        raise ValueError(f"Error: invalid project_name {name!r}: parent references are not allowed.")
    return name


def sanitize_image_filename(image_name: str, url: str = "") -> str:
    """Validate *image_name* and return a safe basename with an allowlisted extension."""
    if not isinstance(image_name, str) or not image_name.strip():
        raise ValueError("Error: image_name must not be empty.")
    raw = image_name.strip()
    if "\x00" in raw:
        raise ValueError("Error: invalid image_name (null byte).")
    if "/" in raw or "\\" in raw:
        raise ValueError(
            "Error: image_name must be a plain filename without path separators "
            "(blocked possible path traversal)."
        )
    if Path(raw).is_absolute() or _WINDOWS_DRIVE_RE.match(raw):
        raise ValueError("Error: image_name must be a plain filename (absolute paths are not allowed).")
    base = Path(raw.replace("\\", "/")).name
    if not base or base in (".", ".."):
        raise ValueError("Error: image_name must be a plain filename.")
    if ".." in Path(base).parts:
        raise ValueError("Error: image_name must not contain parent references.")
    suffix = Path(base).suffix.lower()
    if suffix:
        if suffix not in ALLOWED_IMAGE_EXTENSIONS:
            allowed = ", ".join(sorted(ALLOWED_IMAGE_EXTENSIONS))
            raise ValueError(
                f"Error: unsupported image extension {suffix!r}. Allowed: {allowed}."
            )
        return base
    url_ext = Path(urlparse(url).path).suffix.lower() if url else ""
    if url_ext in ALLOWED_IMAGE_EXTENSIONS:
        return base + url_ext
    return base + ".png"


_SENTINEL_RE = re.compile(
    r'<!-- css-snapshot:([^:\n]+):start -->\s*<style>(.*?)</style>\s*<!-- css-snapshot:\1:end -->',
    re.DOTALL | re.IGNORECASE,
)


def restore_snapshot_html(html: str) -> tuple[str, dict[str, str]]:
    """Reverse the sentinel blocks written by _inline_theme_css.

    Each ``<!-- css-snapshot:<filename>:start --> <style>…</style>
    <!-- css-snapshot:<filename>:end -->`` block is replaced with
    ``<link rel="stylesheet" href="./<filename>" />`` and the CSS content is
    returned so the caller can write it back to disk.

    Returns:
        (restored_html, {filename: css_content, …})
    """
    extracted: dict[str, str] = {}

    def _replace(match: re.Match) -> str:
        filename = match.group(1)
        css = match.group(2).strip()
        extracted[filename] = css
        return f'<link rel="stylesheet" href="./{filename}" />'

    restored = _SENTINEL_RE.sub(_replace, html)
    return restored, extracted


@dataclass(frozen=True)
class SlideFile:
    index: int
    suffix: str
    path: Path


def get_mnt_dir() -> Path:
    return Path("/app/mnt") if Path("/.dockerenv").is_file() else Path(__file__).parents[2] / "mnt"


def get_project_dir(project_name: str) -> Path:
    return get_mnt_dir() / project_name / "presentations"


def list_slide_files(project_dir: Path, file_prefix: str = "slide") -> list[SlideFile]:
    pattern = re.compile(rf"^{re.escape(file_prefix)}_(\d+)(.*)\.html$", re.IGNORECASE)
    slides: list[SlideFile] = []
    for path in project_dir.glob("*.html"):
        match = pattern.match(path.name)
        if not match:
            continue
        index = int(match.group(1))
        suffix = match.group(2) or ""
        slides.append(SlideFile(index=index, suffix=suffix, path=path))
    return sorted(slides, key=lambda s: s.index)


def compute_pad_width(slides: list[SlideFile], min_width: int = 2, extra_count: int = 0) -> int:
    max_index = max([s.index for s in slides], default=0) + max(0, extra_count)
    return max(min_width, len(str(max_index or 1)))


def build_slide_name(file_prefix: str, index: int, pad_width: int, suffix: str) -> str:
    return f"{file_prefix}_{index:0{pad_width}d}{suffix}.html"


def next_pptx_version(desired: Path) -> Path:
    """Return *desired* if it doesn't exist, otherwise the next free _vN path.

    Strips any existing ``_vN`` suffix before searching so that passing
    ``deck_v2.pptx`` when that file already exists yields ``deck_v3.pptx``
    rather than ``deck_v2_v2.pptx``.
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


def apply_renames(rename_map: dict[Path, Path]) -> None:
    temp_map: dict[Path, Path] = {}
    for src, dest in rename_map.items():
        if src == dest:
            continue
        temp_name = f".__tmp__{uuid.uuid4().hex}{src.suffix}"
        tmp_path = src.with_name(temp_name)
        src.rename(tmp_path)
        temp_map[tmp_path] = dest

    for tmp, dest in temp_map.items():
        if dest.exists():
            dest.unlink()
        tmp.rename(dest)
