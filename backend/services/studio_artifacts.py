"""List and resolve deliverable files under ./mnt (docs, slides, images, video)."""

from __future__ import annotations

from pathlib import Path

ARTIFACT_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".md",
    ".html",
    ".htm",
    ".txt",
    ".pptx",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".svg",
    ".mp4",
    ".webm",
    ".mov",
}

CATEGORY_DIRS = {
    "document": ("documents",),
    "presentation": ("presentations",),
    "image": ("generated_images", "images", "assets"),
    "video": ("generated_videos", "videos"),
}


def get_mnt_root() -> Path:
    return Path(__file__).resolve().parents[2] / "mnt"


def safe_mnt_path(relative: str) -> Path | None:
    """Resolve a path under mnt/; return None if outside mnt."""
    root = get_mnt_root().resolve()
    if not root.exists():
        return None
    rel = relative.replace("\\", "/").lstrip("/")
    if rel.startswith("mnt/"):
        rel = rel[4:]
    target = (root / rel).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        return None
    if not target.is_file():
        return None
    return target


def _guess_category(path: Path, root: Path) -> str:
    rel_parts = path.relative_to(root).parts
    if len(rel_parts) >= 2:
        folder = rel_parts[1].lower()
        for cat, names in CATEGORY_DIRS.items():
            if folder in names:
                return cat
    ext = path.suffix.lower()
    if ext in {".pptx"}:
        return "presentation"
    if ext in {".mp4", ".webm", ".mov"}:
        return "video"
    if ext in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}:
        return "image"
    return "document"


def _guess_preview_type(path: Path, category: str) -> str | None:
    ext = path.suffix.lower()
    if ext == ".pdf":
        return "pdf"
    if ext in {".html", ".htm"}:
        if category == "presentation" or "pitch" in path.name.lower():
            return "pitch_card"
        return "html"
    if ext in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}:
        return "image"
    if ext in {".md", ".txt"}:
        return "markdown"
    if ext == ".mp4" or ext in {".webm", ".mov"}:
        return "video"
    return None


def _artifact_entry(path: Path, root: Path) -> dict:
    rel = path.relative_to(root).as_posix()
    stat = path.stat()
    category = _guess_category(path, root)
    preview_type = _guess_preview_type(path, category)
    entry = {
        "path": rel,
        "name": path.name,
        "category": category,
        "size_bytes": stat.st_size,
        "modified_at": stat.st_mtime,
        "download_url": f"/studio/files/{rel}",
    }
    if preview_type:
        entry["preview_type"] = preview_type
        entry["preview_url"] = f"/studio/files/{rel}"
    return entry


def list_artifacts(limit: int = 80) -> list[dict]:
    root = get_mnt_root()
    if not root.exists():
        return []

    files: list[tuple[float, dict]] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in ARTIFACT_EXTENSIONS:
            continue
        if path.name.startswith("."):
            continue
        stat = path.stat()
        files.append((stat.st_mtime, _artifact_entry(path, root)))

    files.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in files[:limit]]
