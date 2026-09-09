"""Workspace (launch directory) helpers.

Issue #15: users launch OpenSwarm from their codebase root, but some tools
resolved paths relative to the installed package directory instead, so the
agent "looked in a completely different dir".

Rule: the user's launch directory is ``Path.cwd()``. Package-relative paths
(``Path(__file__).parents[...]``) are the install location, not the project.
Tools that browse user files must default to the workspace root and must say
so in their descriptions so the model does not guess the package dir.
"""

from __future__ import annotations

from pathlib import Path


def get_workspace_root() -> Path:
    """Return the directory the user launched OpenSwarm from."""
    return Path.cwd()


def get_package_root() -> Path:
    """Return the installed OpenSwarm package root (this repo checkout)."""
    return Path(__file__).resolve().parents[1]


def resolve_skills_dirs() -> list[Path]:
    """Return candidate ``mnt/skills`` dirs, deduped, workspace first.

    Checks both the launch directory and the package directory so skills are
    found regardless of which cwd the host process started with.
    """
    candidates = [
        get_workspace_root() / "mnt" / "skills",
        get_package_root() / "mnt" / "skills",
    ]
    seen: list[Path] = []
    for candidate in candidates:
        resolved = candidate.resolve() if candidate.exists() else candidate.absolute()
        if all(existing != resolved for existing in seen):
            seen.append(resolved)
    return seen
