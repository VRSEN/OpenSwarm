#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import tarfile
import zipfile
from pathlib import Path

GENERATED_CONFIG = "openswarm_telemetry_config.py"


def contains_generated_config(path: Path) -> bool:
    if not path.exists():
        return False
    if path.is_dir():
        return any(child.name == GENERATED_CONFIG for child in path.rglob(GENERATED_CONFIG))
    if path.name == GENERATED_CONFIG:
        return True
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            return any(Path(name).name == GENERATED_CONFIG for name in archive.namelist())
    if tarfile.is_tarfile(path):
        with tarfile.open(path) as archive:
            return any(Path(member.name).name == GENERATED_CONFIG for member in archive.getmembers())
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Guard against accidentally shipping generated telemetry config.")
    parser.add_argument("paths", nargs="+", help="Artifact files or directories to inspect.")
    parser.add_argument(
        "--allow-generated-config",
        action="store_true",
        help="Allow openswarm_telemetry_config.py. Use only for intentional npm CI injection checks.",
    )
    parser.add_argument(
        "--require-generated-config",
        action="store_true",
        help="Fail unless at least one inspected path contains openswarm_telemetry_config.py.",
    )
    args = parser.parse_args()

    matches = [str(Path(path)) for path in args.paths if contains_generated_config(Path(path))]
    if matches and not args.allow_generated_config:
        print(
            "Refusing to ship generated telemetry config outside the intentional npm CI injection path:\n"
            + "\n".join(f"  - {match}" for match in matches),
            file=sys.stderr,
        )
        return 1
    if args.require_generated_config and not matches:
        print("Expected generated telemetry config, but none was found.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
