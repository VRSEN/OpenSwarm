"""Copy a file from one absolute path to another.

This tool is used by multiple agents. Some agents may emit Linux-style `/mnt/...`
paths even when running on Windows outside Docker. On Windows, `/mnt/...` resolves
to `<drive>:\\mnt\\...`, which is *not* this repo's `./mnt` folder and can create
duplicate artifact trees. We normalize those inputs to the repo-local `./mnt`.
"""

import os
import shutil
from pathlib import Path

from agency_swarm.tools import BaseTool
from pydantic import Field

def _normalize_mnt_path(p: str) -> str:
    raw = (p or "").strip()
    if not raw:
        return raw
    # Only needed for Windows non-docker runs.
    if os.name != "nt":
        return raw
    if Path("/.dockerenv").is_file():
        return raw

    # If the agent provides "/mnt/..." treat it as repo-local "./mnt/...".
    if raw.startswith("/mnt/") or raw == "/mnt":
        mnt = (Path("/app/mnt") if Path("/.dockerenv").is_file() else Path(__file__).parents[1] / "mnt").resolve()
        suffix = raw[len("/mnt/") :] if raw.startswith("/mnt/") else ""
        return str(mnt / suffix)
    return raw


class CopyFile(BaseTool):
    """
    Copy a file from source_path to destination_path.

    Both paths must be absolute. destination_path can be either a full file path
    or a directory path. Destination directories are created automatically. Use
    this to copy uploaded user files into project folders or copy generated files
    to a user-requested output location.
    """

    source_path: str = Field(
        ...,
        description="Absolute path to the file to copy.",
    )
    destination_path: str = Field(
        ...,
        description=(
            "Absolute path where the file should be copied to. Provide either a "
            "full file path including filename, or a directory path to keep the "
            "source filename."
        ),
    )

    def run(self) -> str:
        src = Path(_normalize_mnt_path(self.source_path))
        dst = Path(_normalize_mnt_path(self.destination_path))

        if not src.exists():
            return f"Error: Source file not found: {src}"
        if not src.is_file():
            return f"Error: Source path is not a file: {src}"

        if self.destination_path.endswith(("/", "\\")) or dst.is_dir():
            dst = dst / src.name

        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

        return f"Copied {src.name} to: {dst}"
